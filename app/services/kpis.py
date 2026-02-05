"""
KPI computation for Hospital Resource Utilization dashboard.
"""
from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def _params_dict(branch_ids, department_ids, date_from, date_to):
    d = {}
    if branch_ids is not None:
        d["branch_ids"] = branch_ids
    if department_ids is not None:
        d["department_ids"] = department_ids
    if date_from is not None:
        d["date_from"] = date_from
    if date_to is not None:
        d["date_to"] = date_to
    return d


def get_kpi_summary(
    db: Session,
    branch_ids: Optional[list] = None,
    department_ids: Optional[list] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    params = _params_dict(branch_ids, department_ids, date_from, date_to)

    branch_clause = " AND a.branch_id = ANY(:branch_ids)" if branch_ids else ""
    dept_clause = " AND a.department_id = ANY(:department_ids)" if department_ids else ""

    date_clause = ""
    if date_from and date_to:
        date_clause = (
            " AND a.admission_at >= :date_from "
            "AND a.admission_at < :date_to + interval '1 day'"
        )

    # Core admissions + LOS
    q = f"""
    WITH adm AS (
        SELECT a.admission_id, a.branch_id, a.department_id,
               a.admission_type, a.admission_at,
               d.discharge_at, d.outcome_code,
               EXTRACT(EPOCH FROM (d.discharge_at - a.admission_at))/86400 AS los_days
        FROM admissions a
        JOIN discharges d ON d.admission_id = a.admission_id
        WHERE 1=1 {date_clause} {branch_clause} {dept_clause}
    )
    SELECT
        COUNT(*) AS total_admissions,
        COUNT(*) AS total_discharges,
        COALESCE(AVG(los_days), 0) AS avg_los_days,
        COUNT(*) FILTER (WHERE outcome_code = 'Recovered') AS outcome_recovered,
        COUNT(*) FILTER (WHERE outcome_code = 'Improved') AS outcome_improved,
        COUNT(*) FILTER (WHERE outcome_code = 'Transferred') AS outcome_transferred,
        COUNT(*) FILTER (WHERE outcome_code = 'Deceased') AS outcome_deceased,
        COUNT(*) FILTER (
            WHERE outcome_code NOT IN ('Recovered','Improved','Transferred','Deceased')
        ) AS outcome_other,
        COUNT(*) FILTER (WHERE admission_type = 'Emergency') AS emergency_cases,
        COUNT(*) FILTER (
            WHERE admission_type IN ('Scheduled','Transfer')
        ) AS scheduled_cases
    FROM adm
    """

    r = db.execute(text(q), params).fetchone()
    if not r or (r.total_admissions or 0) == 0:
        return _empty_kpi()

    # Procedure volume
    try:
        proc_q = f"""
        SELECT COUNT(*) FROM procedures p
        JOIN admissions a ON a.admission_id = p.admission_id
        WHERE 1=1 {date_clause} {branch_clause} {dept_clause}
        """
        proc_count = db.execute(text(proc_q), params).scalar() or 0
    except Exception:
        db.rollback()
        proc_count = 0

    # Readmissions
    try:
        readm_q = f"""
        SELECT COUNT(DISTINCT r.previous_admission_id)
        FROM readmissions r
        JOIN admissions a ON a.admission_id = r.previous_admission_id
        WHERE 1=1 {date_clause} {branch_clause} {dept_clause}
        """
        readm_count = db.execute(text(readm_q), params).scalar() or 0
    except Exception:
        db.rollback()
        readm_count = 0

    total_disch = r.total_discharges or 1
    readm_rate = (readm_count / total_disch) * 100

    # Bed occupancy
    occ_q = """
    SELECT AVG(ra.beds_occupied * 100.0 / NULLIF(b.bed_count, 0))
    FROM resource_allocation ra
    JOIN hospital_branches b ON b.branch_id = ra.branch_id
    WHERE 1=1
    """
    occ_params = {}
    if branch_ids:
        occ_q += " AND ra.branch_id = ANY(:branch_ids)"
        occ_params["branch_ids"] = branch_ids
    if date_from and date_to:
        occ_q += " AND ra.record_date >= :date_from AND ra.record_date <= :date_to"
        occ_params["date_from"] = date_from
        occ_params["date_to"] = date_to

    try:
        bed_occ = float(db.execute(text(occ_q), occ_params).scalar() or 0)
    except Exception:
        db.rollback()
        bed_occ = 0.0

    # Doctor utilisation
    util_q = """
    SELECT COUNT(*) FILTER (WHERE ds.is_booked) * 100.0
           / NULLIF(COUNT(*), 0)
    FROM doctor_schedules ds
    """
    util_params = {}
    where_added = False

    if branch_ids:
        util_q += """
        JOIN doctors d ON d.doctor_id = ds.doctor_id
        JOIN departments dp ON dp.department_id = d.department_id
        WHERE dp.branch_id = ANY(:branch_ids)
        """
        util_params["branch_ids"] = branch_ids
        where_added = True

    if date_from and date_to:
        util_q += (" AND " if where_added else " WHERE ") + \
                  "ds.slot_date >= :date_from AND ds.slot_date <= :date_to"
        util_params["date_from"] = date_from
        util_params["date_to"] = date_to

    try:
        doc_util = float(db.execute(text(util_q), util_params).scalar() or 0)
    except Exception:
        db.rollback()
        doc_util = 0.0

    # Cost per discharge (safe division)
    try:
        cost_q = f"""
        SELECT CASE
                 WHEN COUNT(DISTINCT b.admission_id) = 0 THEN 0
                 ELSE COALESCE(SUM(b.total_amount), 0)
                      / COUNT(DISTINCT b.admission_id)
               END
        FROM billing b
        JOIN admissions a ON a.admission_id = b.admission_id
        WHERE 1=1 {date_clause} {branch_clause} {dept_clause}
        """
        cost_per = db.execute(text(cost_q), params).scalar()
        cost_per = float(cost_per or 0)
    except Exception:
        db.rollback()
        cost_per = 0.0

    return {
        "avg_length_of_stay_days": round(float(r.avg_los_days or 0), 2),
        "bed_occupancy_rate_pct": round(bed_occ, 2),
        "total_admissions": r.total_admissions or 0,
        "total_discharges": r.total_discharges or 0,
        "readmission_rate_30d_pct": round(readm_rate, 2),
        "procedure_volume": proc_count,
        "emergency_cases_count": r.emergency_cases or 0,
        "scheduled_cases_count": r.scheduled_cases or 0,
        "doctor_utilization_pct": round(doc_util, 2),
        "cost_per_discharge_inr": round(cost_per, 2),
        "outcome_recovered": r.outcome_recovered or 0,
        "outcome_improved": r.outcome_improved or 0,
        "outcome_transferred": r.outcome_transferred or 0,
        "outcome_deceased": r.outcome_deceased or 0,
        "outcome_other": r.outcome_other or 0,
    }


def _empty_kpi():
    return {
        "avg_length_of_stay_days": 0,
        "bed_occupancy_rate_pct": 0,
        "total_admissions": 0,
        "total_discharges": 0,
        "readmission_rate_30d_pct": 0,
        "procedure_volume": 0,
        "emergency_cases_count": 0,
        "scheduled_cases_count": 0,
        "doctor_utilization_pct": 0,
        "cost_per_discharge_inr": 0,
        "outcome_recovered": 0,
        "outcome_improved": 0,
        "outcome_transferred": 0,
        "outcome_deceased": 0,
        "outcome_other": 0,
    }