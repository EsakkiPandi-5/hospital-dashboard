# Apache Superset — Three Professional Dashboards

Connect Superset to PostgreSQL using **Data → Databases → + Database → PostgreSQL** with URI:
`postgresql://postgres:postgres@<host>:5432/hospital_analytics`.

Create **Datasets** from tables: `admissions`, `discharges`, `departments`, `hospital_branches`, `billing`, `procedures`, `doctor_schedules`, `resource_allocation`, `readmissions`, `outcomes`, `beds`. Also add **Virtual (SQL) Datasets** from the SQL in `superset/datasets/` for filtered views.

---

## 1. Executive Overview Dashboard

**Purpose:** High-level KPIs and trends for leadership. Simple and interpretable.

### Charts to Create

| # | Chart Type | Dataset / Source | Metrics | Filters |
|---|------------|-----------------|---------|---------|
| 1 | **Big Number** | `v_kpi_executive_snapshot` or API | `total_admissions` (last month) | — |
| 2 | **Big Number** | Same | `total_discharges` | — |
| 3 | **Big Number** | Same | `alos_days` | — |
| 4 | **Big Number** | KPI summary query | Bed occupancy % (from `v_kpi_bed_occupancy` avg) | — |
| 5 | **Big Number** | KPI summary query | 30-day readmission rate % | — |
| 6 | **Line** | `v_kpi_admission_discharge_counts` or custom SQL | X: `period_month`, Y: `admissions`, `discharges` | Date range, Branch |
| 7 | **Bar** | `v_kpi_bed_occupancy` (aggregate by department) or `resource_allocation` + departments | Bed occupancy by department (avg occupancy_pct by department_name) | Date range, Branch |
| 8 | **Pie** | `v_kpi_emergency_scheduled_ratio` or `v_kpi_executive_snapshot` | Emergency vs Scheduled (emergency_count, scheduled_count) | Period |

### Layout (suggested)

- **Row 1:** 5 Big Number cards (Admissions, Discharges, ALOS, Bed Occupancy %, Readmission Rate %).
- **Row 2:** Line chart — Admissions & Discharges trend (monthly).
- **Row 3:** Bar chart — Bed occupancy by department; Pie chart — Emergency vs Scheduled split.

### Dashboard Filters

- **Date range** (temporal) — map to `period_month` or `record_date` where applicable.
- **Branch** (dropdown) — map to `branch_id` / `branch_name`.

---

## 2. Department Drill-Down Dashboard

**Purpose:** Department-level metrics for operations: doctor utilization, procedure volumes, ALOS, peak hours.

### Charts to Create

| # | Chart Type | Dataset / Source | Metrics | Notes |
|---|------------|-----------------|---------|--------|
| 1 | **Bar** | `v_kpi_doctor_utilization` | X: department_name (or doctor_name), Y: utilization_pct | Filter by branch, date range |
| 2 | **Bar** | `v_kpi_procedure_volume` (aggregate by department) | X: department_name, Y: procedure_count | Filter by branch, date range |
| 3 | **Bar** | `v_kpi_alos` | X: department_name, Y: alos_days | Filter by branch, date range |
| 4 | **Bar** | Custom SQL: admissions by hour | X: hour (0–23), Y: admissions_count | Peak hour analysis |
| 5 | **Bar** | Custom SQL: admissions by day of week | X: day_of_week, Y: admissions_count | Peak day analysis |
| 6 | **Table** | `v_kpi_admission_discharge_counts` + department | period_date, department_name, admissions, discharges | Drill-down detail |

### SQL for Peak Hour (Virtual Dataset)

```sql
SELECT
  EXTRACT(HOUR FROM a.admission_at)::int AS hour,
  COUNT(*) AS admissions_count
FROM admissions a
WHERE a.admission_at >= '{{ from_dttm }}'::timestamp
  AND a.admission_at < '{{ to_dttm }}'::timestamp
  {% if filter_branch %} AND a.branch_id = {{ filter_branch }} {% endif %}
  {% if filter_department %} AND a.department_id = {{ filter_department }} {% endif %}
GROUP BY 1
ORDER BY 1;
```

### Dashboard Filters

- **Department** (dropdown) — map to `department_id` / `department_name`.
- **Branch** (dropdown) — map to `branch_id` / `branch_name`.
- **Date range** — map to `period_date` / `period_month` / `admission_at`.

### Layout

- **Row 1:** Filters (Department, Branch, Date range).
- **Row 2:** Doctor utilization by department (bar); Procedure volume by department (bar).
- **Row 3:** ALOS by department (bar); Peak hour bar; Peak day bar.
- **Row 4:** Table — admission/discharge counts by department and date.

---

## 3. Operations & Bottleneck Dashboard

**Purpose:** Occupancy alerts, delayed discharges, ICU capacity, resource shortage indicators.

### Charts to Create

| # | Chart Type | Dataset / Source | Metrics | Notes |
|---|------------|-----------------|---------|--------|
| 1 | **Table** | Custom SQL or API-sourced | Occupancy alerts: branch_name, record_date, occupancy_pct, threshold | Days where occupancy > 85% |
| 2 | **Bar** | Custom SQL: long-stay admissions | X: department_name or branch_name, Y: long_stay_count | Discharges with LOS > 14 days (delayed discharge proxy) |
| 3 | **Line** | `v_kpi_icu_utilization` | X: record_date, Y: icu_occupancy_pct, ventilator_utilization_pct | ICU capacity monitoring |
| 4 | **Big Number** | Custom SQL | Count of days in last 7 days where bed occupancy > 85% | Resource shortage indicator |
| 5 | **Table** | Custom SQL: bottleneck summary | flag_type, root_cause, branch_name, department_name, count | Delayed discharge + peak hour surplus |

### SQL for Occupancy Alerts (Virtual Dataset)

```sql
SELECT b.name AS branch_name, ra.record_date,
       ROUND(AVG(ra.beds_occupied * 100.0 / NULLIF(b.bed_count, 0))::numeric, 2) AS occupancy_pct,
       85 AS threshold_pct
FROM resource_allocation ra
JOIN hospital_branches b ON b.branch_id = ra.branch_id
WHERE ra.record_date >= CURRENT_DATE - 30
  AND (ra.beds_occupied * 100.0 / NULLIF(b.bed_count, 0)) >= 85
GROUP BY b.name, ra.record_date
ORDER BY ra.record_date DESC, occupancy_pct DESC;
```

### SQL for Delayed Discharge Analysis (Virtual Dataset)

```sql
SELECT b.name AS branch_name, d.name AS department_name,
       COUNT(*) AS long_stay_count,
       ROUND(AVG(EXTRACT(EPOCH FROM (dis.discharge_at - a.admission_at))/86400)::numeric, 2) AS avg_los_days
FROM admissions a
JOIN discharges dis ON dis.admission_id = a.admission_id
JOIN hospital_branches b ON b.branch_id = a.branch_id
JOIN departments d ON d.department_id = a.department_id
WHERE a.admission_at >= CURRENT_DATE - 90
  AND EXTRACT(EPOCH FROM (dis.discharge_at - a.admission_at))/86400 > 14
GROUP BY b.name, d.name
ORDER BY long_stay_count DESC;
```

### SQL for ICU Capacity (use view)

Use dataset from **v_kpi_icu_utilization**: X = `record_date`, Y = `icu_occupancy_pct`, `ventilator_utilization_pct`. Filter by branch and date range.

### Dashboard Filters

- **Branch** (dropdown).
- **Date range**.

### Layout

- **Row 1:** Big Number — “Days with occupancy > 85%” (last 7 days); Table — Occupancy alerts.
- **Row 2:** Bar — Delayed discharge analysis (long-stay count by dept/branch); Line — ICU & ventilator utilization over time.
- **Row 3:** Table — Bottleneck summary (from API or SQL above).

---

## Summary

| Dashboard | Main KPIs / Content | Filters |
|-----------|---------------------|---------|
| **Executive Overview** | KPI cards, admissions/discharges trend, bed occupancy by dept, emergency vs scheduled | Date range, Branch |
| **Department Drill-Down** | Doctor utilization, procedure volume, ALOS by dept, peak hour/day | Department, Branch, Date range |
| **Operations & Bottleneck** | Occupancy alerts, delayed discharge analysis, ICU capacity, shortage indicators | Branch, Date range |

All dashboards are designed to be **simple, interpretable, and suitable for non-technical administrative staff**.
