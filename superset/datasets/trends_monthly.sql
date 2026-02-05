-- Monthly trends for Superset (time series)
WITH adm AS (
    SELECT a.admission_id, a.admission_at,
           d.discharge_at,
           EXTRACT(EPOCH FROM (d.discharge_at - a.admission_at))/86400 AS los_days
    FROM admissions a
    JOIN discharges d ON d.admission_id = a.admission_id
    WHERE a.admission_at >= {{ date_from }}
      AND a.admission_at < {{ date_to }} + interval '1 day'
),
by_month AS (
    SELECT date_trunc('month', admission_at)::date AS period,
           COUNT(*) AS admissions,
           ROUND(AVG(los_days)::numeric, 2) AS avg_los_days
    FROM adm
    GROUP BY 1
)
SELECT period, admissions, avg_los_days FROM by_month ORDER BY period;
