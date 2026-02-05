"""
Monthly performance summary (JSON) for dashboards and automation.
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import kpis, trends, predictions

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/monthly-summary")
def monthly_summary(
    branch_ids: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Automated monthly performance summary: KPIs, trends, branch comparison, alerts, bottlenecks."""
    if year and month:
        date_from = date(year, month, 1)
        if month == 12:
            date_to = date(year, 12, 31)
        else:
            date_to = date(year, month + 1, 1) - timedelta(days=1)
    else:
        date_to = date.today()
        date_from = date(date_to.year, date_to.month, 1) if date_to.day > 1 else date(date_to.year, date_to.month - 1, 1) if date_to.month > 1 else date(date_to.year - 1, 12, 1)
        if date_from.month == date_to.month and date_from.year == date_to.year:
            date_to = date_to
        else:
            date_to = date_from + timedelta(days=32)
            date_to = date(date_to.year, date_to.month, 1) - timedelta(days=1)

    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    kpi = kpis.get_kpi_summary(db, branch_ids=b_ids, date_from=date_from, date_to=date_to)
    monthly_trends = trends.get_trends(db, granularity="monthly", branch_ids=b_ids, date_from=date_from, date_to=date_to)
    branch_comparison = trends.get_branch_comparison(db, date_from=date_from, date_to=date_to)
    alerts = predictions.get_resource_alerts(db, branch_ids=b_ids)
    bottlenecks = predictions.get_bottlenecks(db, branch_ids=b_ids, date_from=date_from, date_to=date_to)

    return {
        "period": {"date_from": str(date_from), "date_to": str(date_to)},
        "kpis": kpi,
        "monthly_trends": monthly_trends,
        "branch_comparison": branch_comparison,
        "alerts": alerts,
        "bottlenecks": bottlenecks,
    }
