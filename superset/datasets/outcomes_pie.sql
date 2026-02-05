-- Patient outcome classification (pie chart)
SELECT d.outcome_code AS outcome,
       COUNT(*) AS count
FROM discharges d
JOIN admissions a ON a.admission_id = d.admission_id
WHERE a.admission_at >= {{ date_from }}
  AND a.admission_at < {{ date_to }} + interval '1 day'
GROUP BY d.outcome_code
ORDER BY count DESC;
