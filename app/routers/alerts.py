"""
Predictive alerts and bottleneck identification.
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import predictions, predictive

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/resource-alerts")
def resource_alerts(
    branch_ids: Optional[str] = Query(None),
    days_ahead: int = Query(7, ge=1, le=30),
    occupancy_threshold_pct: float = Query(85, ge=50, le=100),
    utilization_threshold_pct: float = Query(90, ge=50, le=100),
    db: Session = Depends(get_db),
):
    """Predictive alerts for resource shortages (beds, ICU, ventilators)."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    return predictions.get_resource_alerts(
        db,
        branch_ids=b_ids,
        days_ahead=days_ahead,
        occupancy_threshold_pct=occupancy_threshold_pct,
        utilization_threshold_pct=utilization_threshold_pct,
    )


@router.get("/bottlenecks")
def bottlenecks(
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Bottleneck identification: delayed discharges, peak-hour surplus."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    df = date.fromisoformat(date_from) if date_from else None
    dt = date.fromisoformat(date_to) if date_to else None
    return predictions.get_bottlenecks(db, branch_ids=b_ids, date_from=df, date_to=dt)


@router.get("/threshold-alerts")
def threshold_alerts(
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    bed_occupancy_threshold_pct: float = Query(85, ge=50, le=100),
    icu_occupancy_threshold_pct: float = Query(90, ge=50, le=100),
    doctor_utilization_threshold_pct: float = Query(95, ge=50, le=100),
    db: Session = Depends(get_db),
):
    """Threshold alerts: high bed occupancy (>85%), ICU, doctor overutilization."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=7)
    return predictive.get_threshold_alerts(
        db,
        branch_ids=b_ids,
        date_from=date_from,
        date_to=date_to,
        bed_occupancy_threshold_pct=bed_occupancy_threshold_pct,
        icu_occupancy_threshold_pct=icu_occupancy_threshold_pct,
        doctor_utilization_threshold_pct=doctor_utilization_threshold_pct,
    )
