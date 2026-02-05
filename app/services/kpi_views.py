"""
KPI data from validated SQL views (v_kpi_*). Used by API and Superset.
"""
from datetime import date, timedelta
from typing import Optional, List

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_alos_from_view(
    db: Session,
    branch_ids: Optional[List[int]] = None,
    department_ids: Optional[List[int]] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    group_by: str = "month",
) -> List[dict]:
    """Average Length of Stay from v_kpi_alos."""
    params = {}
    clause = " WHERE 1=1"
    if date_from:
        clause += " AND period_date >= :date_from"
        params["date_from"] = date_from
    if date_to:
        clause += " AND period_date <= :date_to"
        params["date_to"] = date_to
    if branch_ids:
        clause += " AND branch_id = ANY(:branch_ids)"
        params["branch_ids"] = branch_ids
    if department_ids:
        clause += " AND department_id = ANY(:department_ids)"
        params["department_ids"] = department_ids
    period_col = "period_month" if group_by == "month" else "period_date"
    q = f"""
    SELECT branch_name, department_name, {period_col} AS period,
           discharge_count, alos_days
    FROM v_kpi_alos
    {clause}
    ORDER BY {period_col}
    """
    rows = db.execute(text(q), params).fetchall()
    return [{"branch_name": r.branch_name, "department_name": r.department_name, "period": str(r.period), "discharge_count": r.discharge_count, "alos_days": float(r.alos_days or 0)} for r in rows]


def get_bed_occupancy_from_view(
    db: Session,
    branch_ids: Optional[List[int]] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[dict]:
    """Bed occupancy from v_kpi_bed_occupancy."""
    params = {}
    clause = " WHERE 1=1"
    if date_from:
        clause += " AND record_date >= :date_from"
        params["date_from"] = date_from
    if date_to:
        clause += " AND record_date <= :date_to"
        params["date_to"] = date_to
    if branch_ids:
        clause += " AND branch_id = ANY(:branch_ids)"
        params["branch_ids"] = branch_ids
    q = f"""
    SELECT branch_name, record_date, record_hour, beds_occupied, total_beds, occupancy_pct
    FROM v_kpi_bed_occupancy
    {clause}
    ORDER BY record_date, record_hour
    """
    rows = db.execute(text(q), params).fetchall()
    return [{"branch_name": r.branch_name, "record_date": str(r.record_date), "record_hour": r.record_hour, "beds_occupied": r.beds_occupied, "total_beds": r.total_beds, "occupancy_pct": float(r.occupancy_pct or 0)} for r in rows]


def get_executive_snapshot_from_view(db: Session) -> List[dict]:
    """Executive KPI snapshot from v_kpi_executive_snapshot."""
    rows = db.execute(text("SELECT * FROM v_kpi_executive_snapshot")).fetchall()
    return [{"period_month": str(r.period_month), "total_admissions": r.total_admissions, "total_discharges": r.total_discharges, "alos_days": float(r.alos_days or 0), "emergency_count": r.emergency_count, "scheduled_count": r.scheduled_count} for r in rows]


def get_outcome_distribution_from_view(
    db: Session,
    branch_ids: Optional[List[int]] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[dict]:
    """Outcome distribution from v_kpi_outcome_distribution."""
    params = {}
    clause = " WHERE 1=1"
    if date_from:
        clause += " AND period_month >= :date_from"
        params["date_from"] = date_from
    if date_to:
        clause += " AND period_month <= :date_to"
        params["date_to"] = date_to
    if branch_ids:
        clause += " AND branch_id = ANY(:branch_ids)"
        params["branch_ids"] = branch_ids
    q = f"SELECT branch_name, department_name, period_month, outcome_code, outcome_name, outcome_count FROM v_kpi_outcome_distribution {clause} ORDER BY period_month, outcome_count DESC"
    rows = db.execute(text(q), params).fetchall()
    return [{"branch_name": r.branch_name, "department_name": r.department_name, "period_month": str(r.period_month), "outcome_code": r.outcome_code, "outcome_name": r.outcome_name, "outcome_count": r.outcome_count} for r in rows]


def get_icu_utilization_from_view(
    db: Session,
    branch_ids: Optional[List[int]] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[dict]:
    """ICU & ventilator utilization from v_kpi_icu_utilization."""
    params = {}
    clause = " WHERE 1=1"
    if date_from:
        clause += " AND record_date >= :date_from"
        params["date_from"] = date_from
    if date_to:
        clause += " AND record_date <= :date_to"
        params["date_to"] = date_to
    if branch_ids:
        clause += " AND branch_id = ANY(:branch_ids)"
        params["branch_ids"] = branch_ids
    q = f"SELECT branch_name, record_date, record_hour, icu_occupied, icu_beds, ventilators_used, ventilator_count, icu_occupancy_pct, ventilator_utilization_pct FROM v_kpi_icu_utilization {clause} ORDER BY record_date, record_hour"
    rows = db.execute(text(q), params).fetchall()
    return [{"branch_name": r.branch_name, "record_date": str(r.record_date), "record_hour": r.record_hour, "icu_occupied": r.icu_occupied, "icu_beds": r.icu_beds, "ventilators_used": r.ventilators_used, "ventilator_count": r.ventilator_count, "icu_occupancy_pct": float(r.icu_occupancy_pct or 0), "ventilator_utilization_pct": float(r.ventilator_utilization_pct or 0)} for r in rows]
