-- KPI Summary dataset for Apache Superset
-- Use as "Virtual Dataset" or "SQL Lab" query. Filter by :date_from, :date_to, :branch_ids in Superset.
WITH adm AS (
    SELECT a.admission_id, a.branch_id, a.department_id, a.admission_type, a.admission_at,
           d.discharge_at, d.outcome_code,
           EXTRACT(EPOCH FROM (d.discharge_at - a.admission_at))/86400 AS los_days
    FROM admissions a
    JOIN discharges d ON d.admission_id = a.admission_id
    WHERE a.admission_at >= {{ date_from }}
      AND a.admission_at < {{ date_to }} + interval '1 day'
)
SELECT
    COUNT(*) AS total_admissions,
    COUNT(*) AS total_discharges,
    ROUND(AVG(los_days)::numeric, 2) AS avg_length_of_stay_days,
    COUNT(*) FILTER (WHERE outcome_code = 'Recovered') AS outcome_recovered,
    COUNT(*) FILTER (WHERE outcome_code = 'Improved') AS outcome_improved,
    COUNT(*) FILTER (WHERE outcome_code = 'Transferred') AS outcome_transferred,
    COUNT(*) FILTER (WHERE outcome_code = 'Deceased') AS outcome_deceased,
    COUNT(*) FILTER (WHERE admission_type = 'Emergency') AS emergency_cases,
    COUNT(*) FILTER (WHERE admission_type IN ('Scheduled','Transfer')) AS scheduled_cases
FROM adm;
