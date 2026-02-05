from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel


class KPISummary(BaseModel):
    avg_length_of_stay_days: float
    bed_occupancy_rate_pct: float
    total_admissions: int
    total_discharges: int
    readmission_rate_30d_pct: float
    procedure_volume: int
    emergency_cases_count: int
    scheduled_cases_count: int
    doctor_utilization_pct: float
    cost_per_discharge_inr: float
    outcome_recovered: int
    outcome_improved: int
    outcome_transferred: int
    outcome_deceased: int
    outcome_other: int


class TrendPoint(BaseModel):
    period: str  # day, week, month label
    admissions: int
    discharges: int
    avg_los_days: float
    occupancy_pct: float


class DepartmentComparison(BaseModel):
    department_code: str
    department_name: str
    branch_name: str
    admissions: int
    discharges: int
    avg_los_days: float
    procedure_volume: int
    emergency_count: int


class BranchComparison(BaseModel):
    branch_id: int
    branch_name: str
    city: str
    admissions: int
    discharges: int
    avg_los_days: float
    cost_per_discharge_inr: float
    readmission_rate_pct: float
    bed_occupancy_pct: float


class PeakHourInsight(BaseModel):
    hour: int
    day_of_week: Optional[int]
    admissions_count: int
    branch_name: Optional[str] = None


class Alert(BaseModel):
    alert_type: str
    severity: str
    message: str
    branch_id: Optional[int] = None
    department_id: Optional[int] = None
    predicted_shortage: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None


class ExportRequest(BaseModel):
    format: str  # csv, excel, pdf
    report_type: str  # kpi_summary, monthly_performance, trends, branch_comparison
    branch_ids: Optional[List[int]] = None
    department_ids: Optional[List[int]] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
