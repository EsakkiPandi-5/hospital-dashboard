"""
Predictive insights: moving averages, trend-based forecasts, threshold alerts.
No complex ML; simple and interpretable.
"""
from datetime import date, timedelta
from typing import Optional, List

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_admission_trend_with_moving_avg(
    db: Session,
    branch_ids: Optional[List[int]] = None,
    days: int = 90,
    window_days: int = 7,
) -> List[dict]:
    """
    Daily admission count with N-day moving average for trend visualization.
    Forecast: simple linear extrapolation of last window_days moving average.
    """
    params = {"days": days, "window_days": window_days}
    branch_clause = " AND a.branch_id = ANY(:branch_ids)" if branch_ids else ""
    if branch_ids:
        params["branch_ids"] = branch_ids
    q = f"""
    WITH daily AS (
        SELECT date_trunc('day', a.admission_at)::date AS dt,
               COUNT(*) AS admissions
        FROM admissions a
        WHERE a.admission_at >= CURRENT_DATE - :days
        {branch_clause}
        GROUP BY 1
    ),
    with_ma AS (
        SELECT dt, admissions,
               AVG(admissions) OVER (ORDER BY dt ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS moving_avg
        FROM daily
    )
    SELECT dt, admissions, ROUND(moving_avg::numeric, 2) AS moving_avg
    FROM with_ma
    ORDER BY dt
    """
    rows = db.execute(text(q), params).fetchall()
    return [{"date": str(r.dt), "admissions": r.admissions, "moving_avg_7d": float(r.moving_avg or 0)} for r in rows]


def get_occupancy_forecast_simple(
    db: Session,
    branch_id: Optional[int] = None,
    days_lookback: int = 14,
    occupancy_threshold_pct: float = 85,
) -> List[dict]:
    """
    Recent daily avg occupancy and flag when above threshold.
    Forecast: use last 7-day average as next-day estimate (simple trend).
    """
    params = {"days_lookback": days_lookback, "threshold": occupancy_threshold_pct}
    branch_clause = " AND ra.branch_id = :branch_id" if branch_id else ""
    if branch_id:
        params["branch_id"] = branch_id
    q = f"""
    WITH daily_occ AS (
        SELECT ra.branch_id, b.name AS branch_name, ra.record_date,
               AVG(ra.beds_occupied * 100.0 / NULLIF(b.bed_count, 0)) AS avg_occupancy_pct
        FROM resource_allocation ra
        JOIN hospital_branches b ON b.branch_id = ra.branch_id
        WHERE ra.record_date >= CURRENT_DATE - :days_lookback
        {branch_clause}
        GROUP BY ra.branch_id, b.name, ra.record_date
    ),
    with_ma AS (
        SELECT branch_id, branch_name, record_date, avg_occupancy_pct,
               AVG(avg_occupancy_pct) OVER (PARTITION BY branch_id ORDER BY record_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma_7d
        FROM daily_occ
    )
    SELECT branch_name, record_date, ROUND(avg_occupancy_pct::numeric, 2) AS occupancy_pct,
           ROUND(ma_7d::numeric, 2) AS moving_avg_7d,
           CASE WHEN avg_occupancy_pct >= :threshold THEN true ELSE false END AS above_threshold
    FROM with_ma
    ORDER BY branch_id, record_date
    """
    rows = db.execute(text(q), params).fetchall()
    return [
        {
            "branch_name": r.branch_name,
            "record_date": str(r.record_date),
            "occupancy_pct": float(r.occupancy_pct or 0),
            "moving_avg_7d": float(r.moving_avg_7d or 0),
            "above_threshold": r.above_threshold,
        }
        for r in rows
    ]


def get_threshold_alerts(
    db: Session,
    branch_ids: Optional[List[int]] = None,
    bed_occupancy_threshold_pct: float = 85,
    icu_occupancy_threshold_pct: float = 90,
    doctor_utilization_threshold_pct: float = 95,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[dict]:
    """
    Alerts when KPIs exceed thresholds: high bed occupancy, ICU, doctor overutilization.
    Uses recent data (e.g. last 7 days) for current-state alerts.
    """
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=7)
    params = {"date_from": date_from, "date_to": date_to, "bed_threshold": bed_occupancy_threshold_pct, "icu_threshold": icu_occupancy_threshold_pct, "doc_threshold": doctor_utilization_threshold_pct}
    branch_clause_ra = " AND ra.branch_id = ANY(:branch_ids)" if branch_ids else ""
    branch_clause_doc = " AND d.branch_id = ANY(:branch_ids)" if branch_ids else ""
    if branch_ids:
        params["branch_ids"] = branch_ids

    alerts = []

    # Bed occupancy alert
    q_bed = f"""
    SELECT ra.branch_id, b.name AS branch_name, ra.record_date,
           AVG(ra.beds_occupied * 100.0 / NULLIF(b.bed_count, 0)) AS occ_pct
    FROM resource_allocation ra
    JOIN hospital_branches b ON b.branch_id = ra.branch_id
    WHERE ra.record_date >= :date_from AND ra.record_date <= :date_to
    {branch_clause_ra}
    GROUP BY ra.branch_id, b.name, ra.record_date
    HAVING AVG(ra.beds_occupied * 100.0 / NULLIF(b.bed_count, 0)) >= :bed_threshold
    ORDER BY occ_pct DESC
    """
    for r in db.execute(text(q_bed), params).fetchall():
        alerts.append({"alert_type": "high_bed_occupancy", "severity": "warning", "branch_id": r.branch_id, "branch_name": r.branch_name, "record_date": str(r.record_date), "value_pct": float(r.occ_pct), "threshold_pct": bed_occupancy_threshold_pct, "message": f"Bed occupancy at {r.branch_name} on {r.record_date} was {float(r.occ_pct):.1f}% (threshold {bed_occupancy_threshold_pct}%)."})

    # ICU utilization alert
    q_icu = f"""
    SELECT ra.branch_id, b.name AS branch_name, ra.record_date,
           AVG(ra.icu_occupied * 100.0 / NULLIF(b.icu_beds, 0)) AS icu_pct
    FROM resource_allocation ra
    JOIN hospital_branches b ON b.branch_id = ra.branch_id
    WHERE ra.record_date >= :date_from AND ra.record_date <= :date_to
    AND b.icu_beds > 0
    {branch_clause_ra}
    GROUP BY ra.branch_id, b.name, ra.record_date
    HAVING AVG(ra.icu_occupied * 100.0 / NULLIF(b.icu_beds, 0)) >= :icu_threshold
    """
    for r in db.execute(text(q_icu), params).fetchall():
        alerts.append({"alert_type": "high_icu_utilization", "severity": "warning", "branch_id": r.branch_id, "branch_name": r.branch_name, "record_date": str(r.record_date), "value_pct": float(r.icu_pct), "threshold_pct": icu_occupancy_threshold_pct, "message": f"ICU utilization at {r.branch_name} on {r.record_date} was {float(r.icu_pct):.1f}%."})

    # Doctor overutilization (avg utilization > threshold in period)
    q_doc = f"""
    SELECT d.branch_id, b.name AS branch_name,
           AVG(util.util_pct) AS avg_util_pct
    FROM (
        SELECT doc.department_id, COUNT(*) FILTER (WHERE ds.is_booked) * 100.0 / NULLIF(COUNT(*), 0) AS util_pct
        FROM doctor_schedules ds
        JOIN doctors doc ON doc.doctor_id = ds.doctor_id
        WHERE ds.slot_date >= :date_from AND ds.slot_date <= :date_to
        GROUP BY doc.doctor_id, doc.department_id
    ) util
    JOIN departments d ON d.department_id = util.department_id
    JOIN hospital_branches b ON b.branch_id = d.branch_id
    WHERE 1=1 {branch_clause_doc}
    GROUP BY d.branch_id, b.name
    HAVING AVG(util.util_pct) >= :doc_threshold
    """
    for r in db.execute(text(q_doc), params).fetchall():
        alerts.append({"alert_type": "doctor_overutilization", "severity": "info", "branch_id": r.branch_id, "branch_name": r.branch_name, "value_pct": float(r.avg_util_pct), "threshold_pct": doctor_utilization_threshold_pct, "message": f"Doctor utilization at {r.branch_name} averaged {float(r.avg_util_pct):.1f}% (threshold {doctor_utilization_threshold_pct}%)."})

    return alerts
