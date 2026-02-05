# Hospital Resource Utilization & Patient Outcomes Dashboard

**Production-grade analytics platform for a mid-sized multi-specialty hospital network in India.**

---

## 1. Problem Statement

Hospital operations and administrative teams need a single platform to:

- **Monitor and optimize** resource utilization (beds, ICU, ventilators, doctors) across departments and branches.
- **Gain visibility** into admissions, discharges, bed usage, doctor workloads, procedure volumes, costs, and patient outcomes.
- **Identify bottlenecks** (e.g., high bed occupancy, delayed discharges, emergency surges) and **predict** upcoming resource shortages.
- **Compare performance** across departments (Cardiology, Oncology, Orthopedics, Pediatrics, Emergency, General Medicine) and across hospital branches.
- **Support decisions** with monthly performance summaries, KPIs (cost per discharge, readmission rates, ALOS), and exports (CSV, Excel, PDF) for leadership and audits.

The solution must be **on-premise only**, use **standardized metrics**, and be **interpretable by non-technical staff** via simple visualizations and clear KPIs.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HOSPITAL ANALYTICS PLATFORM                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐     │
│   │  Apache Superset │     │  FastAPI Backend │     │   PostgreSQL     │     │
│   │  (BI Dashboards) │────▶│  (ETL + API)     │────▶│   (Data Store)   │     │
│   │  - Executive     │     │  - ETL / seed    │     │   - Schema       │     │
│   │  - Dept Drill    │     │  - KPI APIs      │     │   - KPI Views    │     │
│   │  - Operations    │     │  - Exports       │     │   - 6–12 mo data │     │
│   └────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘     │
│            │                        │                        │               │
│            │  SQL / connection      │  SQLAlchemy            │  On-premise   │
│            │  to same DB            │  Pandas for exports    │  only         │
│            └───────────────────────┴────────────────────────┘               │
│                                                                               │
│   Exports: CSV, Excel, PDF (monthly summary, department-wise, KPI snapshot)   │
│   No public cloud; no third-party healthcare/EMR APIs.                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Data flow:**

1. **ETL:** Schema and seed script load normalized tables and 6–12 months of synthetic data into PostgreSQL.
2. **KPIs:** Validated SQL views (`v_kpi_*`) compute ALOS, bed occupancy, readmission rate, cost per discharge, etc.
3. **API:** FastAPI exposes read-only KPI, trend, comparison, predictive, and export endpoints.
4. **Superset:** Connects to PostgreSQL; builds three dashboards (Executive, Department Drill-Down, Operations & Bottleneck) from tables and views.
5. **Exports:** Backend generates CSV (KPI, trends, branch/department-wise), Excel (monthly performance), and PDF (KPI snapshot, monthly summary).

---

## 3. Tech Stack (Strict)

| Layer           | Technology        |
|----------------|-------------------|
| Backend / ETL  | FastAPI (Python)  |
| Database       | PostgreSQL        |
| BI Tool        | Apache Superset  |
| Data processing| Pandas, SQLAlchemy|
| Storage        | Local / on-premise simulation only |
| Exports        | CSV, Excel, PDF   |

No public cloud services; no third-party healthcare or EMR APIs.

---

## 4. Data Model

Normalized relational schema with time-based fields (hourly/daily where needed), department and branch mapping, cost attribution, doctor availability vs utilization, emergency vs scheduled cases, and outcome classifications.

### Required Tables

| Table               | Purpose |
|---------------------|--------|
| **patients**        | Demographics: age (date_of_birth), gender, insurance_type (Cash, CGHS, ESI, Private, Corporate). |
| **hospital_branches** | Branches: name, city, state, bed_count, icu_beds, ventilator_count. |
| **departments**     | Departments per branch: code, name, branch_id, bed_count, is_critical_care (Cardiology, Oncology, Orthopedics, Pediatrics, Emergency, General Medicine). |
| **admissions**     | Patient admissions: patient_id, branch_id, department_id, admission_type (Emergency/Scheduled/Transfer), admission_at, diagnosis_category_id, admission_source. |
| **discharges**      | One per admission: admission_id, discharge_at, outcome_id, outcome_code (links to outcomes). |
| **outcomes**        | Lookup: code, name, description (Recovered, Improved, Transferred, Deceased, LAMA). |
| **doctors**         | Doctor master: employee_id, full_name, department_id, specialization. |
| **doctor_schedules**| Availability vs utilization: doctor_id, slot_date, slot_start, slot_end, slot_type, is_booked (hourly/daily). |
| **procedures**      | Procedures during admission: admission_id, procedure_code, doctor_id, performed_at, duration_mins. |
| **billing**         | Cost attribution: admission_id, total_amount, insurance_amount, patient_amount, currency, billed_at. |
| **beds**            | Physical bed inventory: branch_id, department_id, bed_number, bed_type (general/icu/hdu/ventilator). |
| **resource_allocation** | Hourly/daily occupancy: branch_id, department_id, record_date, record_hour, beds_occupied, icu_occupied, ventilators_used. |
| **readmissions**    | 30-day readmissions: previous_admission_id, new_admission_id, days_since_discharge. |

Supporting: **procedure_codes**, **diagnosis_categories**. Indexes on branch_id, department_id, admission_at, discharge_at, record_date/record_hour for analytics.

Synthetic data: **6–12 months** of admissions, discharges, procedures, billing, doctor schedules, resource allocation, and readmissions (see `database/seed_data.py`).

---

## 5. KPI Definitions (SQL Views)

All KPIs are implemented as **SQL views** in `database/schema.sql`. Formulas are documented in comments there and summarized below.

| KPI | View | Formula |
|-----|------|--------|
| **Average Length of Stay (ALOS)** | `v_kpi_alos` | ALOS (days) = AVG(discharge_at − admission_at) per branch/department/period. |
| **Bed Occupancy Rate** | `v_kpi_bed_occupancy` | Occupancy % = (beds_occupied / total_beds) × 100 per branch/department/record_date/record_hour. |
| **Admission & Discharge Counts** | `v_kpi_admission_discharge_counts` | COUNT(admissions) per period/branch/department (one discharge per admission). |
| **30-Day Readmission Rate** | `v_kpi_readmission_rate` | Readmission % = (count of 30-day readmissions / count of discharges) × 100 per branch/period. |
| **Procedure Volume** | `v_kpi_procedure_volume` | COUNT(procedures) per period/branch/department/procedure_code. |
| **Emergency vs Scheduled Ratio** | `v_kpi_emergency_scheduled_ratio` | Emergency % and Scheduled % = COUNT by admission_type / total admissions per period/branch/department. |
| **Doctor Utilization** | `v_kpi_doctor_utilization` | Utilization % = (booked_slots / total_slots) × 100 per doctor/period. |
| **Cost per Discharge** | `v_kpi_cost_per_discharge` | Cost per discharge = SUM(billing.total_amount) / COUNT(discharges) per branch/department/period. |
| **Patient Outcome Distribution** | `v_kpi_outcome_distribution` | COUNT by outcome_code per branch/department/period. |
| **ICU & Critical Care Utilization** | `v_kpi_icu_utilization` | ICU occupancy % = (icu_occupied / icu_beds) × 100; ventilator % = (ventilators_used / ventilator_count) × 100 per branch/record_date/record_hour. |

Executive snapshot: **v_kpi_executive_snapshot** — one row per month with total_admissions, total_discharges, alos_days, emergency_count, scheduled_count.

---

## 6. Analytics Features

- **Trend analysis:** Daily, weekly, monthly, quarterly (API: `GET /api/analytics/trends?granularity=...`).
- **Comparisons:** Cross-department (`/api/analytics/departments`), cross-branch (`/api/analytics/branches`).
- **Bottleneck detection:** High bed occupancy (>85%), delayed discharges (e.g. LOS >14 days), doctor overutilization, emergency surge periods (API: `/api/alerts/bottlenecks`, `/api/alerts/threshold-alerts`).
- **Predictive (simple, no ML):** Moving averages on admissions and occupancy; trend-based forecasts (e.g. 7-day moving avg as next-day estimate); threshold alerts for beds, ICU, doctors (API: `/api/analytics/predictive/trend-with-moving-avg`, `/api/analytics/predictive/occupancy-forecast`, `/api/alerts/threshold-alerts`).

Filters: `branch_ids`, `department_ids`, `date_from`, `date_to` (and department/branch/date in Superset).

---

## 7. Dashboards (Apache Superset)

Three professional dashboards; all simple and suitable for non-technical staff.

### 1. Executive Overview Dashboard

- **KPI cards:** Admissions, Discharges, ALOS, Bed Occupancy %, Readmission Rate %.
- **Admissions & discharges trend:** Line chart by month (from `v_kpi_admission_discharge_counts` or executive snapshot).
- **Bed occupancy by department:** Bar chart (from `v_kpi_bed_occupancy` or resource_allocation + departments).
- **Emergency vs scheduled split:** Pie or bar (from `v_kpi_emergency_scheduled_ratio` or executive snapshot).
- **Filters:** Date range, Branch.

### 2. Department Drill-Down Dashboard

- **Filters:** Department, Branch, Date range.
- **Charts:** Doctor utilization by department; procedure volumes by department; ALOS by department; peak hour and peak day analysis (admissions by hour, by day of week).
- **Table:** Admission/discharge counts by department and date for drill-down.

### 3. Operations & Bottleneck Dashboard

- **Occupancy alerts:** Table of days/branches where bed occupancy > 85%.
- **Delayed discharge analysis:** Bar/table of long-stay (e.g. LOS >14 days) by department/branch.
- **ICU capacity monitoring:** Line chart from `v_kpi_icu_utilization` (ICU and ventilator utilization over time).
- **Resource shortage indicators:** Big number or table (e.g. count of days above occupancy threshold in last 7 days).

Step-by-step chart and SQL definitions: **`superset/DASHBOARDS.md`** and **`superset/SUPERSET_SETUP.md`**.

---

## 8. Backend (FastAPI)

- **ETL:** `POST /api/etl/run-schema` (apply `database/schema.sql`), `POST /api/etl/seed` (run `database/seed_data.py`).
- **KPIs:** `GET /api/analytics/kpis` (computed); `GET /api/analytics/kpis/executive-snapshot`, `.../alos-from-view`, `.../outcome-distribution`, `.../icu-utilization` (from views).
- **Trends & comparisons:** `GET /api/analytics/trends`, `/departments`, `/branches`, `/peak-hours`.
- **Predictive:** `GET /api/analytics/predictive/trend-with-moving-avg`, `.../occupancy-forecast`; `GET /api/alerts/threshold-alerts`, `/resource-alerts`, `/bottlenecks`.
- **Exports:** CSV (KPI summary, trends, branch comparison, **department-wise**); Excel (monthly performance); PDF (**KPI snapshot**, monthly summary).
- **Reports:** `GET /api/reports/monthly-summary` (JSON: KPIs, trends, branch comparison, alerts, bottlenecks).

Config: `app/config.py` (e.g. `DATABASE_URL`). DB session: `app/database.py`. Seed scripts: `database/seed_data.py`.

---

## 9. Reporting & Exports

| Report | Endpoint / Method | Format |
|--------|-------------------|--------|
| Monthly performance summary | `GET /api/reports/monthly-summary?year=&month=` | JSON |
| Department-wise export | `GET /api/exports/csv/department-wise` | CSV |
| KPI snapshot | `GET /api/exports/pdf/kpi-snapshot` | PDF |
| Monthly summary (narrative) | `GET /api/exports/pdf/monthly-summary` | PDF |
| KPI / trends / branch | `GET /api/exports/csv/...` | CSV |
| Monthly performance (multi-sheet) | `GET /api/exports/excel/monthly-performance` | Excel |

---

## 10. Sample Business Insights

- **ALOS by department:** Identify departments with unusually high ALOS (e.g. General Medicine) for process or case-mix review.
- **Bed occupancy >85%:** Trigger capacity or discharge planning; use threshold alerts and Operations dashboard.
- **30-day readmission rate by branch:** Compare branches to target quality improvement and care transitions.
- **Emergency vs scheduled mix:** Use trend and Executive pie to plan staffing and OT schedules.
- **Peak hour/day:** Use Department Drill-Down peak charts to align nursing and front-desk staffing.
- **Cost per discharge by branch/department:** Support pricing and cost containment; use branch comparison and department-wise CSV.
- **ICU/ventilator utilization:** Use Operations dashboard to anticipate shortages and plan backups.

---

## 11. Future Improvements

- **Real ETL pipeline:** Replace synthetic seed with incremental loads from internal EMR/HIS (on-premise), with idempotent and auditable jobs.
- **Role-based access:** Restrict Superset and API by branch/department for data governance.
- **Scheduled reports:** Cron or scheduler to generate monthly PDF/CSV and email to distribution lists.
- **More predictive models:** Simple regression or time-series (e.g. ARIMA) for bed demand and ICU usage, still interpretable and documented.
- **Drill-down to patient list:** Anonymized list views (e.g. long-stay patients) for care teams, with strict access control.
- **Benchmarking:** Compare KPIs to internal targets or external benchmarks (e.g. NABH), with clear definitions.

---

## 12. Setup Instructions

### Prerequisites

- Python 3.10+
- PostgreSQL 15+
- (Optional) Docker and Docker Compose

**Running on MacBook M1 Air?** See **[docs/RUN_ON_MAC_M1.md](docs/RUN_ON_MAC_M1.md)** for step-by-step native and Docker instructions.  
**Deploying to a server?** See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**. **Deploying on Render?** See **[docs/DEPLOY_ON_RENDER.md](docs/DEPLOY_ON_RENDER.md)** for exact steps.

### 1. Clone / open project

```bash
cd "Hospital Management"
```

### 2. Database

```bash
# Create database
createdb hospital_analytics

# Apply schema (creates tables and KPI views)
psql postgresql://postgres:postgres@localhost:5432/hospital_analytics -f database/schema.sql
```

### 3. Backend

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hospital_analytics  # or set in .env
python database/seed_data.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000  
- Swagger: http://localhost:8000/docs  

### 4. Connect Superset to PostgreSQL

1. Install and run Apache Superset (or use Docker: `docker compose up -d superset`).
2. In Superset: **Data → Databases → + Database**.
3. Select **PostgreSQL**.
4. **SQLAlchemy URI:** `postgresql://postgres:postgres@<host>:5432/hospital_analytics`  
   - From same host: `postgresql://postgres:postgres@localhost:5432/hospital_analytics`  
   - From Docker Superset to Docker DB: `postgresql://postgres:postgres@db:5432/hospital_analytics`
5. Test connection and Save.
6. Create **Datasets** from tables (`admissions`, `discharges`, `v_kpi_*` views, etc.) or from Virtual SQL in `superset/datasets/` and `superset/DASHBOARDS.md`.
7. Build the three dashboards (Executive, Department Drill-Down, Operations & Bottleneck) as in **superset/DASHBOARDS.md**.

### 5. Docker (all-in-one)

```bash
docker compose up -d db api
# First time: apply schema and seed
psql postgresql://postgres:postgres@localhost:5432/hospital_analytics -f database/schema.sql
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hospital_analytics python database/seed_data.py
# Optional: Superset
docker compose up -d superset
# Superset: http://localhost:8088 (default admin / admin)
```

---

## 13. Project Structure

```
Hospital Management/
├── app/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings (DATABASE_URL)
│   ├── database.py          # SQLAlchemy engine & session
│   ├── schemas.py           # Pydantic models
│   ├── routers/
│   │   ├── analytics.py     # KPIs, trends, comparisons, KPI views, predictive
│   │   ├── etl.py           # run-schema, seed
│   │   ├── alerts.py       # resource-alerts, bottlenecks, threshold-alerts
│   │   ├── exports.py      # CSV, Excel, PDF
│   │   └── reports.py      # monthly-summary
│   └── services/
│       ├── kpis.py         # KPI computation
│       ├── kpi_views.py    # Data from v_kpi_* views
│       ├── trends.py       # Trends, department/branch comparison, peak hours
│       ├── predictions.py  # Resource alerts, bottlenecks
│       └── predictive.py   # Moving avg, occupancy forecast, threshold alerts
├── database/
│   ├── schema.sql          # Tables, indexes, KPI views
│   └── seed_data.py        # 6–12 months synthetic data
├── superset/
│   ├── SUPERSET_SETUP.md    # DB connection, datasets
│   ├── DASHBOARDS.md        # Three dashboard definitions & SQL
│   └── datasets/            # Sample SQL for virtual datasets
├── docker-compose.yml
├── Dockerfile.api
├── requirements.txt
├── .env.example
└── README.md                # This file
```

---

## 14. Environment Variables

| Variable       | Default |
|----------------|---------|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/hospital_analytics` |

Copy `.env.example` to `.env` and adjust as needed.

---

**License / use:** Internal use only. No third-party healthcare APIs or EMR integrations. Data stored on-premise or internal cloud only.
