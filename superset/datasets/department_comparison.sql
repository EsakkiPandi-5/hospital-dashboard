-- Department comparison (drill-down by department)
SELECT d.code AS department_code, d.name AS department_name, b.name AS branch_name,
       COUNT(a.admission_id) AS admissions,
       ROUND(AVG(EXTRACT(EPOCH FROM (dis.discharge_at - a.admission_at))/86400)::numeric, 2) AS avg_los_days,
       COUNT(*) FILTER (WHERE a.admission_type = 'Emergency') AS emergency_count
FROM departments d
JOIN hospital_branches b ON b.branch_id = d.branch_id
LEFT JOIN admissions a ON a.department_id = d.department_id
    AND a.admission_at >= {{ date_from }}
    AND a.admission_at < {{ date_to }} + interval '1 day'
LEFT JOIN discharges dis ON dis.admission_id = a.admission_id
GROUP BY d.department_id, d.code, d.name, b.name
ORDER BY admissions DESC;
