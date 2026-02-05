"""
Export API: CSV, Excel, PDF reports.
"""
from datetime import date, timedelta
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse, Response
import pandas as pd
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import kpis, trends, predictions

router = APIRouter(prefix="/api/exports", tags=["exports"])


def _parse_filters(branch_ids: Optional[str], department_ids: Optional[str], date_from: Optional[date], date_to: Optional[date]):
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    d_ids = [int(x) for x in department_ids.split(",")] if department_ids else None
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=90)
    return b_ids, d_ids, date_from, date_to


@router.get("/csv/kpi-summary")
def export_kpi_csv(
    branch_ids: Optional[str] = Query(None),
    department_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Export KPI summary as CSV."""
    b_ids, d_ids, df, dt = _parse_filters(branch_ids, department_ids, date_from, date_to)
    data = kpis.get_kpi_summary(db, branch_ids=b_ids, department_ids=d_ids, date_from=df, date_to=dt)
    dframe = pd.DataFrame([data])
    buf = BytesIO()
    dframe.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=kpi_summary.csv"})


@router.get("/csv/trends")
def export_trends_csv(
    granularity: str = Query("monthly", enum=["daily", "weekly", "monthly", "quarterly"]),
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Export trend data as CSV."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=365)
    data = trends.get_trends(db, granularity=granularity, branch_ids=b_ids, date_from=date_from, date_to=date_to)
    dframe = pd.DataFrame(data)
    buf = BytesIO()
    dframe.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=trends_{granularity}.csv"})


@router.get("/csv/department-wise")
def export_department_wise_csv(
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Department-wise CSV: admissions, discharges, ALOS, procedure volume, emergency count per department."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=365)
    data = trends.get_department_comparison(db, branch_ids=b_ids, date_from=date_from, date_to=date_to)
    dframe = pd.DataFrame(data)
    buf = BytesIO()
    dframe.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=department_wise.csv"})


@router.get("/csv/branch-comparison")
def export_branch_comparison_csv(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Export branch comparison as CSV."""
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=365)
    data = trends.get_branch_comparison(db, date_from=date_from, date_to=date_to)
    dframe = pd.DataFrame(data)
    buf = BytesIO()
    dframe.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=branch_comparison.csv"})


@router.get("/excel/monthly-performance")
def export_monthly_performance_excel(
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Export monthly performance (KPIs + trends + branch comparison) as Excel."""
    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=365)
    kpi = kpis.get_kpi_summary(db, branch_ids=b_ids, date_from=date_from, date_to=date_to)
    trend_data = trends.get_trends(db, granularity="monthly", branch_ids=b_ids, date_from=date_from, date_to=date_to)
    branch_data = trends.get_branch_comparison(db, date_from=date_from, date_to=date_to)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame([kpi]).to_excel(writer, sheet_name="KPI Summary", index=False)
        pd.DataFrame(trend_data).to_excel(writer, sheet_name="Monthly Trends", index=False)
        pd.DataFrame(branch_data).to_excel(writer, sheet_name="Branch Comparison", index=False)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=monthly_performance.xlsx"},
    )


@router.get("/pdf/kpi-snapshot")
def export_kpi_snapshot_pdf(
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """KPI snapshot PDF: key metrics and outcome distribution for leadership."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    kpi = kpis.get_kpi_summary(db, branch_ids=b_ids, date_from=date_from, date_to=date_to)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("Hospital Resource Utilization & Patient Outcomes — KPI Snapshot", styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"Period: {date_from} to {date_to}", styles["Heading2"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("Key Performance Indicators", styles["Heading3"]))
    kpi_rows = [["Metric", "Value"]] + [[k.replace("_", " ").title(), str(v)] for k, v in kpi.items()]
    t = Table(kpi_rows, colWidths=[3 * inch, 2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    story.append(t)
    doc.build(story)
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=kpi_snapshot.pdf"})


@router.get("/pdf/monthly-summary")
def export_monthly_summary_pdf(
    branch_ids: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Generate monthly performance summary as PDF (using reportlab)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

    b_ids = [int(x) for x in branch_ids.split(",")] if branch_ids else None
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    kpi = kpis.get_kpi_summary(db, branch_ids=b_ids, date_from=date_from, date_to=date_to)
    alerts = predictions.get_resource_alerts(db, branch_ids=b_ids)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("Hospital Resource Utilization & Patient Outcomes", styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"Monthly Performance Summary: {date_from} to {date_to}", styles["Heading2"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("Key Performance Indicators", styles["Heading3"]))
    kpi_rows = [["Metric", "Value"]] + [[k, str(v)] for k, v in kpi.items()]
    t = Table(kpi_rows, colWidths=[3 * inch, 2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * inch))
    if alerts:
        story.append(Paragraph("Resource Alerts", styles["Heading3"]))
        alert_rows = [["Type", "Severity", "Message"]] + [[a.get("alert_type", ""), a.get("severity", ""), a.get("message", "")[:80]] for a in alerts[:10]]
        t2 = Table(alert_rows, colWidths=[1.5 * inch, 0.8 * inch, 3.2 * inch])
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(t2)
    doc.build(story)
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=monthly_summary.pdf"})
