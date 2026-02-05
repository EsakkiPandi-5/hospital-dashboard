"""
Trend analysis (daily, weekly, monthly, quarterly) for dashboard.
"""
from datetime import date, timedelta
from typing import Optional, List

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_trends(
    db: Session,
    granularity: str,  # daily, weekly, monthly, quarterly
    branch_ids: Optional[List[int]] = None,
    department_ids: Optional[List[int]] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[dict]:
    if not date_from:
        date_from = date.today() - timedelta(days=90)
    if not date_to:
        date_to = date.today()

    params = {"date_from": date_from, "date_to": date_to}

    branch_clause = " AND a.branch_id = ANY(:branch_ids)" if branch_ids else ""
    dept_clause = " AND a.department_id = ANY(:department_ids)" if department_ids else ""

    if branch_ids:
        params["branch_ids"] = branch_ids
    if department_ids:
        params["department_ids"] = department_ids

    # Period grouping for admissions
    if granularity == "daily":
        period_expr = "date_trunc('day', adm.admission_at)::date"
        period_label = "to_char(adm.admission_at, 'YYYY-MM-DD')"
    elif granularity == "weekly":
        period_expr = "date_trunc('week', adm.admission_at)::date"
        period_label = "to_char(date_trunc('week', adm.admission_at), 'YYYY-MM-DD')"
    elif granularity == "monthly":
        period_expr = "date_trunc('month', adm.admission_at)::date"
        period_label = "to_char(date_trunc('month', adm.admission_at), 'YYYY-MM')"
    else:  # quarterly
        period_expr = "date_trunc('quarter', adm.admission_at)::date"
        period_label = "to_char(date_trunc('quarter', adm.admission_at), 'YYYY-Q')"

    q = f"""
    WITH adm AS (
        SELECT a.admission_id, a.admission_at,
               d.discharge_at,
               EXTRACT(EPOCH FROM (d.discharge_at - a.admission_at))/86400 AS los_days
        FROM admissions a
        JOIN discharges d ON d.admission_id = a.admission_id
        WHERE a.admission_at >= :date_from
          AND a.admission_at < :date_to + interval '1 day'
          {branch_clause} {dept_clause}
    ),
    by_period AS (
        SELECT {period_expr} AS period_dt,
               {period_label} AS period_label,
               COUNT(*) AS admissions,
               AVG(los_days) AS avg_los
        FROM adm
        GROUP BY 1, 2
    )
    SELECT period_label, period_dt, admissions, avg_los
    FROM by_period
    ORDER BY period_dt
    """

    rows = db.execute(text(q), params).fetchall()

    # Occupancy by period (from resource_allocation)
    try:
        if granularity == "daily":
            occ_label = "to_char(ra.record_date, 'YYYY-MM-DD')"
        elif granularity == "weekly":
            occ_label = "to_char(date_trunc('week', ra.record_date), 'YYYY-MM-DD')"
        elif granularity == "monthly":
            occ_label = "to_char(date_trunc('month', ra.record_date), 'YYYY-MM')"
        else:  # quarterly
            occ_label = "to_char(date_trunc('quarter', ra.record_date), 'YYYY-Q')"

        occ_q = f"""
        SELECT {occ_label} AS period_label,
               AVG(ra.beds_occupied * 100.0 / NULLIF(b.bed_count, 0)) AS occ_pct
        FROM resource_allocation ra
        JOIN hospital_branches b ON b.branch_id = ra.branch_id
        WHERE ra.record_date >= :date_from
          AND ra.record_date <= :date_to
          {" AND ra.branch_id = ANY(:branch_ids)" if branch_ids else ""}
        GROUP BY 1
        ORDER BY 1
        """

        occ_rows = {
            r.period_label: float(r.occ_pct or 0)
            for r in db.execute(text(occ_q), params).fetchall()
        }
    except Exception:
        occ_rows = {}

    result = []
    for r in rows:
        result.append({
            "period": r.period_label,
            "period_dt": str(r.period_dt) if r.period_dt else None,
            "admissions": r.admissions,
            "discharges": r.admissions,  # same count for now
            "avg_los_days": round(float(r.avg_los or 0), 2),
            "occupancy_pct": round(occ_rows.get(r.period_label, 0), 2),
        })

    return result


def get_department_comparison(
    db: Session,
    branch_ids: Optional[List[int]] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[dict]:
    if not date_from:
        date_from = date.today() - timedelta(days=365)
    if not date_to:
        date_to = date.today()

    params = {"date_from": date_from, "date_to": date_to}

    branch_clause = " AND a.branch_id = ANY(:branch_ids)" if branch_ids else ""
    if branch_ids:
        params["branch_ids"] = branch_ids

    q = f"""
    SELECT d.code,
           d.name AS department_name,
           b.name AS branch_name,
           COUNT(a.admission_id) AS admissions,
           AVG(EXTRACT(EPOCH FROM (dis.discharge_at - a.admission_at))/86400) AS avg_los,
           (
             SELECT COUNT(*)
             FROM procedures p
             JOIN admissions a2 ON a2.admission_id = p.admission_id
             WHERE a2.department_id = d.department_id
               AND a2.admission_at >= :date_from
               AND a2.admission_at < :date_to + interval '1 day'
               {branch_clause.replace('a.', 'a2.')}
           ) AS procedure_volume,
           COUNT(*) FILTER (WHERE a.admission_type = 'Emergency') AS emergency_count
    FROM departments d
    JOIN hospital_branches b ON b.branch_id = d.branch_id
    LEFT JOIN admissions a
           ON a.department_id = d.department_id
          AND a.admission_at >= :date_from
          AND a.admission_at < :date_to + interval '1 day'
          {branch_clause}
    LEFT JOIN discharges dis ON dis.admission_id = a.admission_id
    GROUP BY d.department_id, d.code, d.name, b.name
    ORDER BY admissions DESC
    """

    rows = db.execute(text(q), params).fetchall()

    return [
        {
            "department_code": r.code,
            "department_name": r.department_name,
            "branch_name": r.branch_name,
            "admissions": r.admissions,
            "discharges": r.admissions,
            "avg_los_days": round(float(r.avg_los or 0), 2),
            "procedure_volume": r.procedure_volume or 0,
            "emergency_count": r.emergency_count or 0,
        }
        for r in rows
    ]


def get_branch_comparison(
    db: Session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[dict]:
    if not date_from:
        date_from = date.today() - timedelta(days=365)
    if not date_to:
        date_to = date.today()

    params = {"date_from": date_from, "date_to": date_to}

    q = """
    SELECT b.branch_id,
           b.name AS branch_name,
           b.city,
           COUNT(a.admission_id) AS admissions,
           AVG(EXTRACT(EPOCH FROM (d.discharge_at - a.admission_at))/86400) AS avg_los,
           (
             SELECT COALESCE(SUM(bill.total_amount), 0)
                    / NULLIF(COUNT(DISTINCT bill.admission_id), 0)
             FROM billing bill
             JOIN admissions a2 ON a2.admission_id = bill.admission_id
             WHERE a2.branch_id = b.branch_id
               AND a2.admission_at >= :date_from
               AND a2.admission_at < :date_to + interval '1 day'
           ) AS cost_per_discharge,
           (
             SELECT COUNT(DISTINCT r.previous_admission_id)
             FROM readmissions r
             JOIN admissions a3 ON a3.admission_id = r.previous_admission_id
             WHERE a3.branch_id = b.branch_id
               AND a3.admission_at >= :date_from
               AND a3.admission_at < :date_to + interval '1 day'
           ) AS readm_count,
           (
             SELECT COUNT(*)
             FROM admissions a4
             WHERE a4.branch_id = b.branch_id
               AND a4.admission_at >= :date_from
               AND a4.admission_at < :date_to + interval '1 day'
           ) AS total_adm
    FROM hospital_branches b
    LEFT JOIN admissions a
           ON a.branch_id = b.branch_id
          AND a.admission_at >= :date_from
          AND a.admission_at < :date_to + interval '1 day'
    LEFT JOIN discharges d ON d.admission_id = a.admission_id
    GROUP BY b.branch_id, b.name, b.city
    ORDER BY b.branch_id
    """

    rows = db.execute(text(q), params).fetchall()

    occ_q = """
    SELECT ra.branch_id,
           AVG(ra.beds_occupied * 100.0 / NULLIF(b.bed_count, 0)) AS occ_pct
    FROM resource_allocation ra
    JOIN hospital_branches b ON b.branch_id = ra.branch_id
    WHERE ra.record_date >= :date_from
      AND ra.record_date <= :date_to
    GROUP BY ra.branch_id
    """

    occ_map = {
        r.branch_id: float(r.occ_pct or 0)
        for r in db.execute(text(occ_q), params).fetchall()
    }

    result = []
    for r in rows:
        total_adm = r.total_adm or 1
        readm_rate = (r.readm_count or 0) / total_adm * 100
        cost = float(r.cost_per_discharge or 0)

        result.append({
            "branch_id": r.branch_id,
            "branch_name": r.branch_name,
            "city": r.city,
            "admissions": r.admissions,
            "discharges": r.admissions,
            "avg_los_days": round(float(r.avg_los or 0), 2),
            "cost_per_discharge_inr": round(cost, 2),
            "readmission_rate_pct": round(readm_rate, 2),
            "bed_occupancy_pct": round(occ_map.get(r.branch_id, 0), 2),
        })

    return result


def get_peak_hours(
    db: Session,
    branch_ids: Optional[List[int]] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    by_day_of_week: bool = False,
) -> List[dict]:
    if not date_from:
        date_from = date.today() - timedelta(days=30)
    if not date_to:
        date_to = date.today()

    params = {"date_from": date_from, "date_to": date_to}

    branch_clause = " AND a.branch_id = ANY(:branch_ids)" if branch_ids else ""
    if branch_ids:
        params["branch_ids"] = branch_ids

    if by_day_of_week:
        q = f"""
        SELECT EXTRACT(DOW FROM a.admission_at)::int AS day_of_week,
               EXTRACT(HOUR FROM a.admission_at)::int AS hour,
               COUNT(*) AS admissions_count
        FROM admissions a
        WHERE a.admission_at >= :date_from
          AND a.admission_at < :date_to + interval '1 day'
          {branch_clause}
        GROUP BY 1, 2
        ORDER BY admissions_count DESC
        """
    else:
        q = f"""
        SELECT EXTRACT(HOUR FROM a.admission_at)::int AS hour,
               COUNT(*) AS admissions_count
        FROM admissions a
        WHERE a.admission_at >= :date_from
          AND a.admission_at < :date_to + interval '1 day'
          {branch_clause}
        GROUP BY 1
        ORDER BY admissions_count DESC
        """

    rows = db.execute(text(q), params).fetchall()

    return [
        {
            "hour": r.hour,
            "day_of_week": getattr(r, "day_of_week", None),
            "admissions_count": r.admissions_count,
        }
        for r in rows
    ]