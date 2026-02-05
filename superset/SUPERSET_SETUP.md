# Apache Superset Setup for Hospital Dashboard

## 1. Connect to PostgreSQL

1. In Superset: **Data** → **Databases** → **+ Database**.
2. Select **PostgreSQL**.
3. **Display Name**: `Hospital Analytics`.
4. **SQLAlchemy URI**: `postgresql://postgres:postgres@host.docker.internal:5432/hospital_analytics` (adjust host if Superset runs on same host: use `localhost`).
5. Test connection and Save.

## 2. Create Datasets

Create **SQL-based datasets** (Virtual Datasets) so you can use parameters:

1. **Data** → **Datasets** → **+ Dataset** → **Create a virtual dataset**.
2. Paste SQL from `superset/datasets/*.sql`. Replace placeholders with Superset template variables:
   - In Virtual Dataset **Query**, use `'{{ from_dttm }}'` and `'{{ to_dttm }}'` for date range (map to dashboard filters).
   - Or use literals: `'2024-01-01'::date` and `'2024-12-31'::date` for a fixed range.

For simplicity, you can also create **Tables** from base tables (`admissions`, `discharges`, `departments`, `hospital_branches`, `billing`, `procedures`, `resource_allocation`) and build charts from those with filters.

### Suggested base tables to add as Datasets

- `admissions` (join to `discharges`, `departments`, `hospital_branches`)
- `discharges`
- `departments`
- `hospital_branches`
- `billing`
- `procedures`
- `resource_allocation`
- `patients`

## 3. Charts to Create

| Chart Type   | Dataset / Metric                         | Use Case                          |
|-------------|-------------------------------------------|-----------------------------------|
| Big Number  | KPI Summary (total admissions, ALOS)     | KPIs at top                       |
| Line        | trends_monthly (admissions, avg_los)     | Trend over time                   |
| Bar         | branch_comparison (admissions, cost)      | Branch comparison                 |
| Bar         | department_comparison                    | Department drill-down             |
| Pie         | outcomes_pie                             | Patient outcome classification    |
| Bar         | Peak hours (SQL: group by hour)          | Peak hour insights                |
| Table       | Alerts / bottlenecks (from API or view)  | Operational flags                  |

## 4. Dashboard Layout

1. **Dashboard** → **+ Dashboard** → name: "Hospital Resource Utilization & Patient Outcomes".
2. Add **Filters**: Date range, Branch (multi-select), Department (multi-select).
3. Top row: Big numbers for ALOS, Bed occupancy %, Admissions, Discharges, Readmission rate %, Cost per discharge.
4. Second row: Line chart (monthly trends), Branch comparison bar chart.
5. Third row: Department comparison bar, Outcomes pie, Peak hours bar.
6. Publish and share link.

## 5. SQL for Peak Hours (Staffing)

Use as Virtual Dataset:

```sql
SELECT EXTRACT(HOUR FROM a.admission_at)::int AS hour,
       COUNT(*) AS admissions_count
FROM admissions a
WHERE a.admission_at >= '2024-01-01'
  AND a.admission_at < '2024-12-31'
GROUP BY 1
ORDER BY 1;
```

Replace dates with dashboard filter columns if you map a date filter.

## 6. Bed Occupancy (from resource_allocation)

```sql
SELECT ra.record_date, ra.record_hour,
       b.name AS branch_name,
       ra.beds_occupied, b.bed_count,
       ROUND(100.0 * ra.beds_occupied / NULLIF(b.bed_count, 0), 2) AS occupancy_pct
FROM resource_allocation ra
JOIN hospital_branches b ON b.branch_id = ra.branch_id
ORDER BY ra.record_date, ra.record_hour;
```

Use for time series or heatmap of occupancy by hour/branch.
