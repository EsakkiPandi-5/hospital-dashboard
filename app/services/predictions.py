"""
Predictive alerts for resource shortages and bottleneck identification.
"""
from datetime import date, timedelta
from typing import Optional, List

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_resource_alerts(
    db: Session,
    branch_ids: Optional[List[int]] = None,
    days_ahead: int = 7,
    occupancy_threshold_pct: float = 85,
    utilization_threshold_pct: float = 90,
) -> List[dict]:
    """
    Predict upcoming resource needs (ICU beds, ventilators) and flag high occupancy.
    Uses recent resource_allocation and admission trends.
    """
    params = {
        "date_from": date.today() - timedelta(days=14),
        "date_to": date.today(),
        "occupancy_threshold": occupancy_threshold_pct,
        "utilization_threshold": utilization_threshold_pct,
    }
    branch_clause = " AND ra.branch_id = ANY(:branch_ids)" if branch_ids else ""
    if branch_ids:
        params["branch_ids"] = branch_ids

    alerts = []

    # Current bed occupancy by branch (from resource_allocation)
    occ_q = f"""
    SELECT ra.branch_id, b.name, b.bed_count, b.icu_beds, b.ventilator_count,
           AVG(ra.beds_occupied) AS avg_beds_occ,
           AVG(ra.icu_occupied) AS avg_icu_occ,
           AVG(ra.ventilators_used) AS avg_vent_used,
           AVG(ra.beds_occupied * 100.0 / NULLIF(b.bed_count, 0)) AS bed_occ_pct,
           AVG(ra.icu_occupied * 100.0 / NULLIF(b.icu_beds, 0)) AS icu_occ_pct,
           AVG(ra.ventilators_used * 100.0 / NULLIF(b.ventilator_count, 0)) AS vent_occ_pct
    FROM resource_allocation ra
    JOIN hospital_branches b ON b.branch_id = ra.branch_id
    WHERE ra.record_date >= :date_from AND ra.record_date <= :date_to
    {branch_clause}
    GROUP BY ra.branch_id, b.name, b.bed_count, b.icu_beds, b.ventilator_count
    """
    rows = db.execute(text(occ_q), params).fetchall()
    for r in rows:
        if r.bed_occ_pct and float(r.bed_occ_pct) >= occupancy_threshold_pct:
            alerts.append({
                "alert_type": "high_bed_occupancy",
                "severity": "warning" if float(r.bed_occ_pct) < 95 else "critical",
                "message": f"Bed occupancy at {r.name} is {float(r.bed_occ_pct):.1f}% (threshold {occupancy_threshold_pct}%). Consider capacity or discharge planning.",
                "branch_id": r.branch_id,
                "department_id": None,
                "predicted_shortage": "general beds",
                "period_start": date.today(),
                "period_end": date.today() + timedelta(days=days_ahead),
            })
        if r.icu_occ_pct and float(r.icu_occ_pct) >= utilization_threshold_pct:
            alerts.append({
                "alert_type": "icu_shortage_risk",
                "severity": "warning",
                "message": f"ICU utilization at {r.name} is {float(r.icu_occ_pct):.1f}%. Risk of shortage in next {days_ahead} days.",
                "branch_id": r.branch_id,
                "department_id": None,
                "predicted_shortage": "ICU beds",
                "period_start": date.today(),
                "period_end": date.today() + timedelta(days=days_ahead),
            })
        if r.vent_occ_pct and float(r.vent_occ_pct) >= utilization_threshold_pct:
            alerts.append({
                "alert_type": "ventilator_shortage_risk",
                "severity": "warning",
                "message": f"Ventilator utilization at {r.name} is {float(r.vent_occ_pct):.1f}%. Consider backup capacity.",
                "branch_id": r.branch_id,
                "department_id": None,
                "predicted_shortage": "ventilators",
                "period_start": date.today(),
                "period_end": date.today() + timedelta(days=days_ahead),
            })

    return alerts


def get_bottlenecks(
    db: Session,
    branch_ids: Optional[List[int]] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[dict]:
    """
    Identify operational bottlenecks: delayed discharges, peak-hour surplus.
    """
    if not date_from:
        date_from = date.today() - timedelta(days=30)
    if not date_to:
        date_to = date.today()
    params = {"date_from": date_from, "date_to": date_to}
    branch_clause = " AND a.branch_id = ANY(:branch_ids)" if branch_ids else ""
    if branch_ids:
        params["branch_ids"] = branch_ids

    bottlenecks = []

    # Discharge turnaround: admissions that stayed longer than 14 days (flag as potential delayed discharge)
    delay_q = f"""
    SELECT a.branch_id, b.name AS branch_name, a.department_id, dp.name AS dept_name,
           COUNT(*) AS long_stay_count,
           AVG(EXTRACT(EPOCH FROM (dis.discharge_at - a.admission_at))/86400) AS avg_los
    FROM admissions a
    JOIN discharges dis ON dis.admission_id = a.admission_id
    JOIN hospital_branches b ON b.branch_id = a.branch_id
    JOIN departments dp ON dp.department_id = a.department_id
    WHERE a.admission_at >= :date_from AND a.admission_at < :date_to + interval '1 day'
    AND EXTRACT(EPOCH FROM (dis.discharge_at - a.admission_at))/86400 > 14
    {branch_clause}
    GROUP BY a.branch_id, b.name, a.department_id, dp.name
    HAVING COUNT(*) >= 5
    ORDER BY long_stay_count DESC
    """
    try:
        for r in db.execute(text(delay_q), params).fetchall():
            bottlenecks.append({
                "flag_type": "delayed_discharge",
                "root_cause": "High proportion of long-stay (>14 days) patients.",
                "branch_id": r.branch_id,
                "branch_name": r.branch_name,
                "department_id": r.department_id,
                "department_name": r.dept_name,
                "count": r.long_stay_count,
                "avg_los_days": round(float(r.avg_los or 0), 2),
            })
    except Exception:
        pass

    # Peak hour surplus: hours with admission count > 2x daily average
    peak_q = f"""
    WITH hourly AS (
        SELECT EXTRACT(HOUR FROM a.admission_at)::int AS hour,
               COUNT(*) AS cnt
        FROM admissions a
        WHERE a.admission_at >= :date_from AND a.admission_at < :date_to + interval '1 day'
        {branch_clause}
        GROUP BY 1
    ),
    avg_daily AS (SELECT SUM(cnt) / 24.0 AS avg_per_hour FROM hourly)
    SELECT h.hour, h.cnt, (SELECT avg_per_hour FROM avg_daily) AS avg_hr
    FROM hourly h
    WHERE h.cnt > 2 * (SELECT avg_per_hour FROM avg_daily)
    ORDER BY h.cnt DESC
    """
    try:
        for r in db.execute(text(peak_q), params).fetchall():
            bottlenecks.append({
                "flag_type": "peak_hour_surplus",
                "root_cause": f"Hour {int(r.hour)} has {r.cnt} admissions (2x average). Consider staffing.",
                "branch_id": None,
                "department_id": None,
                "hour": int(r.hour),
                "admissions_count": r.cnt,
            })
    except Exception:
        pass

    return bottlenecks
