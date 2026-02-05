"""
Seed script: generates 6–12 months of realistic Indian hospital data for analytics.
Run after schema is applied. Uses env DATABASE_URL or defaults to local PostgreSQL.
"""
import os
import random
from datetime import datetime, timedelta
from decimal import Decimal

import psycopg2
from psycopg2.extras import execute_values

# Config: 6–12 months of data
MONTHS_BACK = 12
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/hospital_analytics")
DEPARTMENTS = [
    ("CARD", "Cardiology"),
    ("ONCO", "Oncology"),
    ("ORTH", "Orthopedics"),
    ("PED", "Pediatrics"),
    ("EMER", "Emergency"),
    ("GMED", "General Medicine"),
]
OUTCOMES = ["Recovered", "Improved", "Transferred", "Deceased", "LAMA"]
OUTCOME_DESCRIPTIONS = [
    ("Recovered", "Recovered", "Full recovery"),
    ("Improved", "Improved", "Condition improved, discharged"),
    ("Transferred", "Transferred", "Transferred to another facility"),
    ("Deceased", "Deceased", "Death during stay"),
    ("LAMA", "LAMA", "Left against medical advice"),
]
INSURANCE_TYPES = ["Cash", "CGHS", "ESI", "Private", "Corporate"]
DIAGNOSIS_CATEGORIES = [
    ("ICD-CARD", "Cardiovascular"),
    ("ICD-ONC", "Neoplasm"),
    ("ICD-ORT", "Musculoskeletal"),
    ("ICD-PED", "Pediatric"),
    ("ICD-EM", "Emergency/Injury"),
    ("ICD-GM", "General/Medical"),
]
PROCEDURE_SAMPLES = [
    ("PROC-001", "ECG", "Diagnostic", 15),
    ("PROC-002", "Echocardiogram", "Diagnostic", 30),
    ("PROC-003", "CABG", "Surgery", 240),
    ("PROC-004", "Chemotherapy Session", "Treatment", 120),
    ("PROC-005", "Knee Replacement", "Surgery", 90),
    ("PROC-006", "Fracture Fixation", "Surgery", 60),
    ("PROC-007", "Pediatric Vaccination", "Preventive", 10),
    ("PROC-008", "Emergency Resuscitation", "Emergency", 45),
    ("PROC-009", "CT Scan", "Diagnostic", 30),
    ("PROC-010", "Dialysis", "Treatment", 240),
    ("PROC-011", "Blood Transfusion", "Treatment", 60),
    ("PROC-012", "Endoscopy", "Diagnostic", 45),
]


def conn():
    return psycopg2.connect(DB_URL)


def seed_branches(cursor):
    branches = [
        ("City General Hospital", "Mumbai", "Maharashtra", 200, 20, 15),
        ("Metro Care Hospital", "Delhi", "Delhi", 150, 15, 12),
        ("South Star Hospital", "Chennai", "Tamil Nadu", 180, 18, 14),
    ]
    execute_values(
        cursor,
        """INSERT INTO hospital_branches (name, city, state, bed_count, icu_beds, ventilator_count)
           VALUES %s ON CONFLICT DO NOTHING""",
        branches,
    )


def seed_departments(cursor):
    cursor.execute("SELECT branch_id FROM hospital_branches ORDER BY branch_id")
    branch_ids = [r[0] for r in cursor.fetchall()]
    rows = []
    for branch_id in branch_ids:
        for code, name in DEPARTMENTS:
            bed_count = random.randint(10, 40) if code != "EMER" else random.randint(15, 25)
            rows.append((code, name, branch_id, bed_count))
    execute_values(
        cursor,
        """INSERT INTO departments (code, name, branch_id, bed_count)
           VALUES %s ON CONFLICT (branch_id, code) DO NOTHING""",
        rows,
    )


def seed_doctors(cursor):
    cursor.execute(
        """SELECT d.department_id, d.code FROM departments d
           JOIN hospital_branches b ON d.branch_id = b.branch_id ORDER BY d.department_id"""
    )
    depts = cursor.fetchall()
    rows = []
    for i, (dept_id, code) in enumerate(depts):
        for j in range(random.randint(2, 5)):
            emp_id = f"DOC-{code}-{1000 + i * 10 + j}"
            spec = dict(DEPARTMENTS).get(code, "General")
            rows.append((emp_id, f"Dr. Doctor {code}-{j}", dept_id, spec))
    execute_values(
        cursor,
        """INSERT INTO doctors (employee_id, full_name, department_id, specialization)
           VALUES %s ON CONFLICT DO NOTHING""",
        rows,
    )


def seed_procedure_codes(cursor):
    execute_values(
        cursor,
        """INSERT INTO procedure_codes (procedure_code, description, category, avg_duration_mins)
           VALUES %s ON CONFLICT (procedure_code) DO NOTHING""",
        PROCEDURE_SAMPLES,
    )


def seed_diagnosis_categories(cursor):
    execute_values(
        cursor,
        """INSERT INTO diagnosis_categories (code, name) VALUES %s ON CONFLICT DO NOTHING""",
        DIAGNOSIS_CATEGORIES,
    )


def seed_outcomes(cursor):
    """Outcomes lookup table (required for normalized outcomes)."""
    rows = [(code, name, desc) for code, name, desc in OUTCOME_DESCRIPTIONS]
    execute_values(
        cursor,
        """INSERT INTO outcomes (code, name, description) VALUES %s ON CONFLICT (code) DO NOTHING""",
        rows,
    )


def seed_beds(cursor):
    """Physical bed inventory per branch/department."""
    cursor.execute("SELECT department_id, branch_id, bed_count FROM departments ORDER BY department_id")
    depts = cursor.fetchall()
    rows = []
    for dept_id, branch_id, bed_count in depts:
        bed_type = "icu" if bed_count <= 8 else "general"
        for i in range(bed_count):
            rows.append((branch_id, dept_id, f"B{i+1:03d}", bed_type))
    if rows:
        execute_values(
            cursor,
            """INSERT INTO beds (branch_id, department_id, bed_number, bed_type) VALUES %s""",
            rows,
        )


def seed_patients(cursor, n=2000):
    start_dob = datetime.now().date() - timedelta(days=365 * 80)
    rows = []
    for i in range(n):
        dob = start_dob + timedelta(days=random.randint(0, 365 * 70))
        gender = random.choice(["Male", "Female"])
        insurance = random.choices(INSURANCE_TYPES, weights=[30, 15, 20, 25, 10])[0]
        rows.append((f"PAT-{10000 + i}", gender, dob, insurance))
    execute_values(
        cursor,
        """INSERT INTO patients (external_id, gender, date_of_birth, insurance_type)
           VALUES %s ON CONFLICT (external_id) DO NOTHING""",
        rows,
    )


def seed_admissions_discharges(cursor, months_back=None):
    months_back = months_back or MONTHS_BACK
    cursor.execute("SELECT patient_id FROM patients ORDER BY random() LIMIT 5000")
    patient_ids = [r[0] for r in cursor.fetchall()]
    if not patient_ids:
        return
    cursor.execute("SELECT admission_id FROM admissions")
    if cursor.fetchone():
        return  # already seeded
    cursor.execute(
        """SELECT a.department_id, a.branch_id FROM departments a"""
    )
    dept_branch = cursor.fetchall()
    cursor.execute("SELECT category_id FROM diagnosis_categories ORDER BY category_id")
    diag_ids = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT doctor_id FROM doctors ORDER BY doctor_id")
    doctor_ids = [r[0] for r in cursor.fetchall()]

    base = datetime.now() - timedelta(days=months_back * 30)
    admissions_rows = []
    discharges_rows = []
    admission_counter = [0]

    def make_admission(patient_id, at_time):
        dept_id, branch_id = random.choice(dept_branch)
        adm_type = random.choices(["Emergency", "Scheduled", "Transfer"], weights=[35, 55, 10])[0]
        diag_id = random.choice(diag_ids) if diag_ids else None
        admission_counter[0] += 1
        aid = admission_counter[0]
        admissions_rows.append((
            patient_id, branch_id, dept_id, adm_type,
            at_time, diag_id, "OPD" if adm_type == "Scheduled" else "Emergency",
        ))
        los_days = random.choices([1, 2, 3, 5, 7, 10, 14], weights=[20, 25, 20, 15, 10, 5, 5])[0]
        disch_at = at_time + timedelta(days=los_days)
        outcome = random.choices(OUTCOMES, weights=[50, 25, 10, 5, 10])[0]
        discharges_rows.append((aid, disch_at, outcome))
        return aid, disch_at

    for _ in range(min(8000, len(patient_ids) * 2)):
        pt = random.choice(patient_ids)
        at = base + timedelta(
            days=random.randint(0, months_back * 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        if at > datetime.now():
            continue
        make_admission(pt, at)

    if not admissions_rows:
        return
    cursor.execute("SELECT COALESCE(MAX(admission_id), 0) FROM admissions")
    start_id = cursor.fetchone()[0]
    execute_values(
        cursor,
        """INSERT INTO admissions (patient_id, branch_id, department_id, admission_type, admission_at, diagnosis_category_id, admission_source)
           VALUES %s""",
        admissions_rows,
    )
    n = len(admissions_rows)
    # New IDs are start_id+1 .. start_id+n (serial order)
    discharge_with_ids = []
    for i in range(n):
        discharge_with_ids.append((start_id + 1 + i, discharges_rows[i][1], discharges_rows[i][2]))
    if discharge_with_ids:
        execute_values(
            cursor,
            """INSERT INTO discharges (admission_id, discharge_at, outcome_code) VALUES %s""",
            discharge_with_ids,
        )


def seed_procedures(cursor, count=5000):
    cursor.execute("SELECT admission_id FROM admissions ORDER BY random() LIMIT 5000")
    adm_ids = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT procedure_code FROM procedure_codes")
    proc_codes = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT doctor_id FROM doctors")
    doc_ids = [r[0] for r in cursor.fetchall()]
    rows = []
    for aid in adm_ids[:count]:
        for _ in range(random.randint(0, 3)):
            code = random.choice(proc_codes)
            doc = random.choice(doc_ids)
            cursor.execute("SELECT a.admission_at FROM admissions a WHERE a.admission_id = %s", (aid,))
            row = cursor.fetchone()
            if not row:
                continue
            adm_at = row[0]
            performed_at = adm_at + timedelta(hours=random.randint(0, 72), minutes=random.randint(0, 59))
            duration = random.randint(10, 120)
            rows.append((aid, code, doc, performed_at, duration))
    if rows:
        execute_values(
            cursor,
            """INSERT INTO procedures (admission_id, procedure_code, doctor_id, performed_at, duration_mins)
               VALUES %s""",
            rows,
        )


def seed_billing(cursor):
    cursor.execute("SELECT admission_id FROM admissions")
    adm_ids = [r[0] for r in cursor.fetchall()]
    rows = []
    for aid in adm_ids:
        total = Decimal(random.randint(20000, 500000))
        ins = Decimal(random.randint(0, int(total * Decimal("0.8"))))
        pat = total - ins
        cursor.execute("SELECT discharge_at FROM discharges WHERE admission_id = %s", (aid,))
        r = cursor.fetchone()
        billed_at = r[0] if r else None
        rows.append((aid, total, ins, pat, "INR", billed_at))
    if rows:
        execute_values(
            cursor,
            """INSERT INTO billing (admission_id, total_amount, insurance_amount, patient_amount, currency, billed_at)
               VALUES %s""",
            rows,
        )


def seed_doctor_schedules(cursor, days_back=365):
    cursor.execute("SELECT doctor_id FROM doctors")
    doc_ids = [r[0] for r in cursor.fetchall()]
    base = datetime.now().date() - timedelta(days=days_back)
    rows = []
    for doc in doc_ids:
        for d in range(days_back):
            dt = base + timedelta(days=d)
            for slot in range(2):  # morning, afternoon
                start_h = 9 + slot * 5
                end_h = start_h + 4
                is_booked = random.random() < 0.75
                slot_type = random.choice(["OPD", "Surgery", "Ward", "Emergency"])
                rows.append((doc, dt, f"{start_h:02d}:00:00", f"{end_h:02d}:00:00", slot_type, is_booked))
    if rows:
        execute_values(
            cursor,
            """INSERT INTO doctor_schedules (doctor_id, slot_date, slot_start, slot_end, slot_type, is_booked)
               VALUES %s""",
            rows,
        )


def seed_resource_allocation(cursor, days_back=90):
    """90 days of hourly allocation; balance between coverage and seed size."""
    cursor.execute("SELECT branch_id FROM hospital_branches")
    branch_ids = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT branch_id, bed_count, icu_beds, ventilator_count FROM hospital_branches")
    branch_caps = {r[0]: (r[1], r[2], r[3]) for r in cursor.fetchall()}
    base = datetime.now().date() - timedelta(days=days_back)
    rows = []
    for branch_id in branch_ids:
        beds, icu, vent = branch_caps[branch_id]
        for d in range(days_back):
            for h in range(24):
                date = base + timedelta(days=d)
                occ_beds = int(beds * (0.5 + 0.4 * (0.8 + 0.2 * (h / 24))))
                occ_beds = min(beds, max(0, occ_beds + random.randint(-10, 10)))
                occ_icu = min(icu, max(0, int(icu * 0.7) + random.randint(-2, 2)))
                occ_vent = min(vent, max(0, int(vent * 0.6) + random.randint(-1, 1)))
                rows.append((branch_id, None, date, h, occ_beds, occ_icu, occ_vent))
    if rows:
        execute_values(
            cursor,
            """INSERT INTO resource_allocation (branch_id, department_id, record_date, record_hour, beds_occupied, icu_occupied, ventilators_used)
               VALUES %s""",
            rows,
        )


def seed_readmissions(cursor, max_count=500):
    cursor.execute("""
        SELECT d.admission_id, d.discharge_at, a.patient_id
        FROM discharges d
        JOIN admissions a ON a.admission_id = d.admission_id
        ORDER BY random()
    """)
    discharged = cursor.fetchall()
    seen_patient_discharge = {}
    readm_rows = []
    for adm_id, disch_at, patient_id in discharged:
        if len(readm_rows) >= max_count:
            break
        key = (patient_id, adm_id)
        if key in seen_patient_discharge:
            continue
        cursor.execute(
            """SELECT a.admission_id, a.admission_at FROM admissions a
               WHERE a.patient_id = %s AND a.admission_id != %s AND a.admission_at > %s
               ORDER BY a.admission_at LIMIT 1""",
            (patient_id, adm_id, disch_at),
        )
        next_adm = cursor.fetchone()
        if not next_adm:
            continue
        new_adm_id, new_adm_at = next_adm
        days = (new_adm_at - disch_at).days
        if 1 <= days <= 30:
            readm_rows.append((adm_id, new_adm_id, days))
            seen_patient_discharge[key] = True
    if readm_rows:
        execute_values(
            cursor,
            """INSERT INTO readmissions (previous_admission_id, new_admission_id, days_since_discharge) VALUES %s""",
            readm_rows,
        )


def main():
    with conn() as c:
        c.autocommit = False
        cur = c.cursor()
        seed_branches(cur)
        seed_departments(cur)
        seed_outcomes(cur)
        seed_doctors(cur)
        seed_procedure_codes(cur)
        seed_diagnosis_categories(cur)
        seed_patients(cur)
        seed_beds(cur)
        seed_admissions_discharges(cur)
        seed_procedures(cur)
        seed_billing(cur)
        seed_doctor_schedules(cur)
        seed_resource_allocation(cur)
        seed_readmissions(cur)
        c.commit()
    print("Seed completed.")


if __name__ == "__main__":
    main()
