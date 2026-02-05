-- Branch comparison for Superset (bar chart)
SELECT b.branch_id, b.name AS branch_name, b.city,
       COUNT(a.admission_id) AS admissions,
       ROUND(AVG(EXTRACT(EPOCH FROM (d.discharge_at - a.admission_at))/86400)::numeric, 2) AS avg_los_days,
       (SELECT COALESCE(SUM(bill.total_amount), 0) / NULLIF(COUNT(DISTINCT bill.admission_id), 0)
        FROM billing bill
        JOIN admissions a2 ON a2.admission_id = bill.admission_id
        WHERE a2.branch_id = b.branch_id
          AND a2.admission_at >= {{ date_from }}
          AND a2.admission_at < {{ date_to }} + interval '1 day') AS cost_per_discharge_inr
FROM hospital_branches b
LEFT JOIN admissions a ON a.branch_id = b.branch_id
    AND a.admission_at >= {{ date_from }}
    AND a.admission_at < {{ date_to }} + interval '1 day'
LEFT JOIN discharges d ON d.admission_id = a.admission_id
GROUP BY b.branch_id, b.name, b.city
ORDER BY admissions DESC;
