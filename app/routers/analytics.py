"""
Analytics API: KPIs, trends, department/branch comparison, peak hours.
"""
from datetime import date, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import kpis, trends, kpi_views, predictive

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/kpis")
def get_kpis(
    branch_ids: Optional[str] = Query(None, description="Comma-separated branch IDs"),
    department_ids: Optional[str] = Query(None, description="Comma-separated department IDs"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Core KPIs: ALOS, bed occupancy, admissions/discharges, readmission rate, procedure volume, outcomes, cost per discharge."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    d_ids = [int(x) for x in department_ids.split(",")] if department_ids else None
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=90)
    return kpis.get_kpi_summary(db, branch_ids=b_ids, department_ids=d_ids, date_from=date_from, date_to=date_to)


@router.get("/trends")
def get_trends(
    granularity: str = Query("monthly", enum=["daily", "weekly", "monthly", "quarterly"]),
    branch_ids: Optional[str] = Query(None),
    department_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Trend analysis by period (daily/weekly/monthly/quarterly)."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    d_ids = [int(x) for x in department_ids.split(",")] if department_ids else None
    return trends.get_trends(db, granularity=granularity, branch_ids=b_ids, department_ids=d_ids, date_from=date_from, date_to=date_to)


@router.get("/departments")
def department_comparison(
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Cross-department comparison (admissions, ALOS, procedure volume, emergency count)."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    return trends.get_department_comparison(db, branch_ids=b_ids, date_from=date_from, date_to=date_to)


@router.get("/branches")
def branch_comparison(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Branch comparison: admissions, ALOS, cost per discharge, readmission rate, bed occupancy."""
    return trends.get_branch_comparison(db, date_from=date_from, date_to=date_to)


@router.get("/peak-hours")
def peak_hours(
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    by_day_of_week: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Peak hour/day insights for staffing optimization."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    return trends.get_peak_hours(db, branch_ids=b_ids, date_from=date_from, date_to=date_to, by_day_of_week=by_day_of_week)


# ---------- KPI data from validated SQL views ----------
@router.get("/kpis/executive-snapshot")
def kpis_executive_snapshot(db: Session = Depends(get_db)):
    """Executive KPI snapshot from v_kpi_executive_snapshot (monthly)."""
    return kpi_views.get_executive_snapshot_from_view(db)


@router.get("/kpis/alos-from-view")
def kpis_alos_from_view(
    branch_ids: Optional[str] = Query(None),
    department_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    group_by: str = Query("month", enum=["day", "month"]),
    db: Session = Depends(get_db),
):
    """ALOS from v_kpi_alos."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    d_ids = [int(x) for x in department_ids.split(",")] if department_ids else None
    return kpi_views.get_alos_from_view(db, branch_ids=b_ids, department_ids=d_ids, date_from=date_from, date_to=date_to, group_by=group_by)


@router.get("/kpis/outcome-distribution")
def kpis_outcome_distribution(
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Outcome distribution from v_kpi_outcome_distribution."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    return kpi_views.get_outcome_distribution_from_view(db, branch_ids=b_ids, date_from=date_from, date_to=date_to)


@router.get("/kpis/icu-utilization")
def kpis_icu_utilization(
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """ICU & ventilator utilization from v_kpi_icu_utilization."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    return kpi_views.get_icu_utilization_from_view(db, branch_ids=b_ids, date_from=date_from, date_to=date_to)


# ---------- Predictive (moving averages, forecasts, threshold alerts) ----------
@router.get("/predictive/trend-with-moving-avg")
def predictive_trend_moving_avg(
    branch_ids: Optional[str] = Query(None),
    days: int = Query(90, ge=7, le=365),
    window_days: int = Query(7, ge=3, le=30),
    db: Session = Depends(get_db),
):
    """Daily admissions with N-day moving average for trend visualization."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    return predictive.get_admission_trend_with_moving_avg(db, branch_ids=b_ids, days=days, window_days=window_days)


@router.get("/predictive/occupancy-forecast")
def predictive_occupancy_forecast(
    branch_id: Optional[int] = Query(None),
    days_lookback: int = Query(14, ge=7, le=90),
    occupancy_threshold_pct: float = Query(85, ge=50, le=100),
    db: Session = Depends(get_db),
):
    """Recent daily occupancy with 7-day moving avg and above-threshold flag."""
    return predictive.get_occupancy_forecast_simple(db, branch_id=branch_id, days_lookback=days_lookback, occupancy_threshold_pct=occupancy_threshold_pct)


# --- KPI data from validated SQL views ---

@router.get("/views/executive-snapshot")
def executive_snapshot_from_view(db: Session = Depends(get_db)):
    """Executive KPI snapshot from v_kpi_executive_snapshot (monthly)."""
    return kpi_views.get_executive_snapshot_from_view(db)


@router.get("/views/alos")
def alos_from_view(
    branch_ids: Optional[str] = Query(None),
    department_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    group_by: str = Query("month", enum=["day", "month"]),
    db: Session = Depends(get_db),
):
    """ALOS from v_kpi_alos."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    d_ids = [int(x) for x in department_ids.split(",")] if department_ids else None
    return kpi_views.get_alos_from_view(db, branch_ids=b_ids, department_ids=d_ids, date_from=date_from, date_to=date_to, group_by=group_by)


@router.get("/views/bed-occupancy")
def bed_occupancy_from_view(
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Bed occupancy from v_kpi_bed_occupancy."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    return kpi_views.get_bed_occupancy_from_view(db, branch_ids=b_ids, date_from=date_from, date_to=date_to)


@router.get("/views/outcome-distribution")
def outcome_distribution_from_view(
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Outcome distribution from v_kpi_outcome_distribution."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    return kpi_views.get_outcome_distribution_from_view(db, branch_ids=b_ids, date_from=date_from, date_to=date_to)


@router.get("/views/icu-utilization")
def icu_utilization_from_view(
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """ICU & ventilator utilization from v_kpi_icu_utilization."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    return kpi_views.get_icu_utilization_from_view(db, branch_ids=b_ids, date_from=date_from, date_to=date_to)
