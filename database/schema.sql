-- =============================================================================
-- Hospital Resource Utilization & Patient Outcomes - PostgreSQL Schema
-- Multi-specialty hospital network (India), on-premise. Production-grade.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- REFERENCE / LOOKUP TABLES
-- -----------------------------------------------------------------------------

-- Hospital branches (locations)
CREATE TABLE IF NOT EXISTS hospital_branches (
    branch_id         SERIAL PRIMARY KEY,
    name              VARCHAR(200) NOT NULL,
    city              VARCHAR(100) NOT NULL,
    state             VARCHAR(100) NOT NULL,
    bed_count         INT NOT NULL DEFAULT 0,
    icu_beds          INT NOT NULL DEFAULT 0,
    ventilator_count  INT NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Outcome classification lookup (normalized)
CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id    SERIAL PRIMARY KEY,
    code          VARCHAR(30) UNIQUE NOT NULL,
    name          VARCHAR(100) NOT NULL,
    description   VARCHAR(500),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Departments (per branch)
CREATE TABLE IF NOT EXISTS departments (
    department_id   SERIAL PRIMARY KEY,
    code            VARCHAR(20) NOT NULL,
    name            VARCHAR(200) NOT NULL,
    branch_id       INT NOT NULL REFERENCES hospital_branches(branch_id),
    bed_count       INT NOT NULL DEFAULT 0,
    is_critical_care BOOLEAN DEFAULT FALSE,  -- ICU/critical care dept
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(branch_id, code)
);

-- Doctors
CREATE TABLE IF NOT EXISTS doctors (
    doctor_id       SERIAL PRIMARY KEY,
    employee_id     VARCHAR(50) UNIQUE NOT NULL,
    full_name       VARCHAR(200) NOT NULL,
    department_id   INT NOT NULL REFERENCES departments(department_id),
    specialization  VARCHAR(200),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Procedure codes (ICD / hospital procedure codes)
CREATE TABLE IF NOT EXISTS procedure_codes (
    procedure_code   VARCHAR(50) PRIMARY KEY,
    description      VARCHAR(500) NOT NULL,
    category         VARCHAR(100),
    avg_duration_mins INT
);

-- Diagnosis categories
CREATE TABLE IF NOT EXISTS diagnosis_categories (
    category_id   SERIAL PRIMARY KEY,
    code          VARCHAR(20) UNIQUE NOT NULL,
    name          VARCHAR(300) NOT NULL
);

-- -----------------------------------------------------------------------------
-- CORE TRANSACTION TABLES
-- -----------------------------------------------------------------------------

-- Patients (demographics)
CREATE TABLE IF NOT EXISTS patients (
    patient_id     SERIAL PRIMARY KEY,
    external_id    VARCHAR(50) UNIQUE,
    gender         VARCHAR(20) NOT NULL,
    date_of_birth  DATE NOT NULL,
    insurance_type VARCHAR(50) NOT NULL,  -- Cash, CGHS, ESI, Private, Corporate
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Beds (physical bed inventory; occupancy time-series in resource_allocation)
CREATE TABLE IF NOT EXISTS beds (
    bed_id         SERIAL PRIMARY KEY,
    branch_id      INT NOT NULL REFERENCES hospital_branches(branch_id),
    department_id  INT REFERENCES departments(department_id),
    bed_number     VARCHAR(20) NOT NULL,
    bed_type       VARCHAR(30) NOT NULL,  -- general, icu, hdu, ventilator
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Admissions
CREATE TABLE IF NOT EXISTS admissions (
    admission_id    SERIAL PRIMARY KEY,
    patient_id      INT NOT NULL REFERENCES patients(patient_id),
    branch_id       INT NOT NULL REFERENCES hospital_branches(branch_id),
    department_id   INT NOT NULL REFERENCES departments(department_id),
    admission_type  VARCHAR(30) NOT NULL,   -- Emergency, Scheduled, Transfer
    admission_at    TIMESTAMPTZ NOT NULL,
    diagnosis_category_id INT REFERENCES diagnosis_categories(category_id),
    admission_source VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Discharges (one per admission)
CREATE TABLE IF NOT EXISTS discharges (
    discharge_id   SERIAL PRIMARY KEY,
    admission_id    INT NOT NULL UNIQUE REFERENCES admissions(admission_id),
    discharge_at    TIMESTAMPTZ NOT NULL,
    outcome_id     INT REFERENCES outcomes(outcome_id),
    outcome_code    VARCHAR(30) NOT NULL,  -- denormalized for queries; matches outcomes.code
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Procedures performed (during admission)
CREATE TABLE IF NOT EXISTS procedures (
    procedure_record_id SERIAL PRIMARY KEY,
    admission_id    INT NOT NULL REFERENCES admissions(admission_id),
    procedure_code VARCHAR(50) NOT NULL REFERENCES procedure_codes(procedure_code),
    doctor_id      INT REFERENCES doctors(doctor_id),
    performed_at   TIMESTAMPTZ NOT NULL,
    duration_mins  INT,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Doctor schedules (availability vs utilization)
CREATE TABLE IF NOT EXISTS doctor_schedules (
    schedule_id    SERIAL PRIMARY KEY,
    doctor_id      INT NOT NULL REFERENCES doctors(doctor_id),
    slot_date      DATE NOT NULL,
    slot_start     TIME NOT NULL,
    slot_end       TIME NOT NULL,
    slot_type      VARCHAR(50),  -- OPD, Surgery, Ward, Emergency
    is_booked      BOOLEAN DEFAULT FALSE,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Billing (cost attribution)
CREATE TABLE IF NOT EXISTS billing (
    billing_id      SERIAL PRIMARY KEY,
    admission_id    INT NOT NULL REFERENCES admissions(admission_id),
    total_amount    NUMERIC(12,2) NOT NULL,
    insurance_amount NUMERIC(12,2) DEFAULT 0,
    patient_amount  NUMERIC(12,2) DEFAULT 0,
    currency        VARCHAR(5) DEFAULT 'INR',
    billed_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Resource allocation (aggregate hourly/daily by branch/department)
CREATE TABLE IF NOT EXISTS resource_allocation (
    allocation_id   SERIAL PRIMARY KEY,
    branch_id      INT NOT NULL REFERENCES hospital_branches(branch_id),
    department_id  INT REFERENCES departments(department_id),
    record_date    DATE NOT NULL,
    record_hour    INT NOT NULL CHECK (record_hour >= 0 AND record_hour <= 23),
    beds_occupied  INT NOT NULL DEFAULT 0,
    icu_occupied   INT NOT NULL DEFAULT 0,
    ventilators_used INT NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Readmissions (30-day window)
CREATE TABLE IF NOT EXISTS readmissions (
    readmission_id  SERIAL PRIMARY KEY,
    previous_admission_id INT NOT NULL REFERENCES admissions(admission_id),
    new_admission_id INT NOT NULL REFERENCES admissions(admission_id),
    days_since_discharge INT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Optional: FK from beds to admissions (add after admissions exists)
-- ALTER TABLE beds ADD CONSTRAINT fk_beds_admission FOREIGN KEY (admission_id) REFERENCES admissions(admission_id);

-- -----------------------------------------------------------------------------
-- INDEXES FOR ANALYTICS
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_admissions_branch ON admissions(branch_id);
CREATE INDEX IF NOT EXISTS idx_admissions_department ON admissions(department_id);
CREATE INDEX IF NOT EXISTS idx_admissions_admission_at ON admissions(admission_at);
CREATE INDEX IF NOT EXISTS idx_admissions_patient ON admissions(patient_id);
CREATE INDEX IF NOT EXISTS idx_admissions_type ON admissions(admission_type);
CREATE INDEX IF NOT EXISTS idx_discharges_discharge_at ON discharges(discharge_at);
CREATE INDEX IF NOT EXISTS idx_discharges_outcome ON discharges(outcome_code);
CREATE INDEX IF NOT EXISTS idx_procedures_performed_at ON procedures(performed_at);
CREATE INDEX IF NOT EXISTS idx_procedures_admission ON procedures(admission_id);
CREATE INDEX IF NOT EXISTS idx_billing_admission ON billing(admission_id);
CREATE INDEX IF NOT EXISTS idx_doctor_schedules_doctor_date ON doctor_schedules(doctor_id, slot_date);
CREATE INDEX IF NOT EXISTS idx_resource_allocation_branch_date ON resource_allocation(branch_id, record_date, record_hour);
CREATE INDEX IF NOT EXISTS idx_beds_branch_dept ON beds(branch_id, department_id);

-- =============================================================================
-- KPI VIEWS (Validated definitions for reporting and API)
-- Formulas documented in comments and README.
-- =============================================================================

-- View: Average Length of Stay (ALOS)
-- Formula: ALOS = SUM(discharge_at - admission_at) / COUNT(discharges) in days
CREATE OR REPLACE VIEW v_kpi_alos AS
SELECT
    a.branch_id,
    b.name AS branch_name,
    a.department_id,
    d.name AS department_name,
    date_trunc('day', a.admission_at)::date AS period_date,
    date_trunc('month', a.admission_at)::date AS period_month,
    COUNT(*) AS discharge_count,
    ROUND((AVG(EXTRACT(EPOCH FROM (dis.discharge_at - a.admission_at)) / 86400))::numeric, 2) AS alos_days
FROM admissions a
JOIN discharges dis ON dis.admission_id = a.admission_id
JOIN hospital_branches b ON b.branch_id = a.branch_id
JOIN departments d ON d.department_id = a.department_id
GROUP BY a.branch_id, b.name, a.department_id, d.name,
         date_trunc('day', a.admission_at)::date,
         date_trunc('month', a.admission_at)::date;

-- View: Bed Occupancy Rate
-- Formula: Occupancy % = (beds_occupied / total_beds) * 100 per branch/department/period
CREATE OR REPLACE VIEW v_kpi_bed_occupancy AS
SELECT
    ra.branch_id,
    b.name AS branch_name,
    ra.department_id,
    d.name AS department_name,
    ra.record_date,
    ra.record_hour,
    ra.beds_occupied,
    COALESCE(d.bed_count, b.bed_count) AS total_beds,
    ROUND((ra.beds_occupied * 100.0 / NULLIF(COALESCE(d.bed_count, b.bed_count), 0))::numeric, 2) AS occupancy_pct
FROM resource_allocation ra
JOIN hospital_branches b ON b.branch_id = ra.branch_id
LEFT JOIN departments d ON d.department_id = ra.department_id AND d.branch_id = ra.branch_id;

-- View: Admission & Discharge Counts (daily/monthly, by branch/department)
CREATE OR REPLACE VIEW v_kpi_admission_discharge_counts AS
SELECT
    a.branch_id,
    b.name AS branch_name,
    a.department_id,
    d.name AS department_name,
    date_trunc('day', a.admission_at)::date AS period_date,
    date_trunc('month', a.admission_at)::date AS period_month,
    COUNT(*) AS admissions,
    COUNT(*) AS discharges  -- one discharge per admission in our model
FROM admissions a
JOIN discharges dis ON dis.admission_id = a.admission_id
JOIN hospital_branches b ON b.branch_id = a.branch_id
JOIN departments d ON d.department_id = a.department_id
GROUP BY a.branch_id, b.name, a.department_id, d.name,
         date_trunc('day', a.admission_at)::date,
         date_trunc('month', a.admission_at)::date;

-- View: 30-Day Readmission Rate
-- Formula: Readmission Rate % = (count of 30-day readmissions / count of discharges) * 100
CREATE OR REPLACE VIEW v_kpi_readmission_rate AS
SELECT
    a.branch_id,
    b.name AS branch_name,
    date_trunc('month', dis.discharge_at)::date AS period_month,
    COUNT(DISTINCT dis.admission_id) AS total_discharges,
    COUNT(DISTINCT r.previous_admission_id) AS readmissions_30d,
    ROUND((COUNT(DISTINCT r.previous_admission_id) * 100.0 / NULLIF(COUNT(DISTINCT dis.admission_id), 0))::numeric, 2) AS readmission_rate_pct
FROM admissions a
JOIN discharges dis ON dis.admission_id = a.admission_id
JOIN hospital_branches b ON b.branch_id = a.branch_id
LEFT JOIN readmissions r ON r.previous_admission_id = dis.admission_id
GROUP BY a.branch_id, b.name, date_trunc('month', dis.discharge_at)::date;

-- View: Procedure Volume (by period, branch, department)
CREATE OR REPLACE VIEW v_kpi_procedure_volume AS
SELECT
    a.branch_id,
    b.name AS branch_name,
    a.department_id,
    d.name AS department_name,
    date_trunc('day', p.performed_at)::date AS period_date,
    date_trunc('month', p.performed_at)::date AS period_month,
    COUNT(*) AS procedure_count,
    p.procedure_code,
    pc.description AS procedure_description
FROM procedures p
JOIN admissions a ON a.admission_id = p.admission_id
JOIN hospital_branches b ON b.branch_id = a.branch_id
JOIN departments d ON d.department_id = a.department_id
JOIN procedure_codes pc ON pc.procedure_code = p.procedure_code
GROUP BY a.branch_id, b.name, a.department_id, d.name,
         date_trunc('day', p.performed_at)::date,
         date_trunc('month', p.performed_at)::date,
         p.procedure_code, pc.description;

-- View: Emergency vs Scheduled Ratio
CREATE OR REPLACE VIEW v_kpi_emergency_scheduled_ratio AS
SELECT
    a.branch_id,
    b.name AS branch_name,
    a.department_id,
    d.name AS department_name,
    date_trunc('month', a.admission_at)::date AS period_month,
    COUNT(*) FILTER (WHERE a.admission_type = 'Emergency') AS emergency_count,
    COUNT(*) FILTER (WHERE a.admission_type IN ('Scheduled', 'Transfer')) AS scheduled_count,
    COUNT(*) AS total_admissions,
    ROUND((COUNT(*) FILTER (WHERE a.admission_type = 'Emergency') * 100.0 / NULLIF(COUNT(*), 0))::numeric, 2) AS emergency_pct,
    ROUND((COUNT(*) FILTER (WHERE a.admission_type IN ('Scheduled', 'Transfer')) * 100.0 / NULLIF(COUNT(*), 0))::numeric, 2) AS scheduled_pct
FROM admissions a
JOIN hospital_branches b ON b.branch_id = a.branch_id
JOIN departments d ON d.department_id = a.department_id
GROUP BY a.branch_id, b.name, a.department_id, d.name,
         date_trunc('month', a.admission_at)::date;

-- View: Doctor Utilization (% booked time)
-- Formula: Utilization % = (booked_slots / total_slots) * 100 per doctor/period
CREATE OR REPLACE VIEW v_kpi_doctor_utilization AS
SELECT
    ds.doctor_id,
    doc.full_name AS doctor_name,
    doc.department_id,
    d.name AS department_name,
    d.branch_id,
    b.name AS branch_name,
    ds.slot_date AS period_date,
    date_trunc('month', ds.slot_date)::date AS period_month,
    COUNT(*) AS total_slots,
    COUNT(*) FILTER (WHERE ds.is_booked) AS booked_slots,
    ROUND((COUNT(*) FILTER (WHERE ds.is_booked) * 100.0 / NULLIF(COUNT(*), 0))::numeric, 2) AS utilization_pct
FROM doctor_schedules ds
JOIN doctors doc ON doc.doctor_id = ds.doctor_id
JOIN departments d ON d.department_id = doc.department_id
JOIN hospital_branches b ON b.branch_id = d.branch_id
GROUP BY ds.doctor_id, doc.full_name, doc.department_id, d.name, d.branch_id, b.name,
         ds.slot_date, date_trunc('month', ds.slot_date)::date;

-- View: Cost per Discharge
-- Formula: Cost per discharge = SUM(billing.total_amount) / COUNT(discharges)
CREATE OR REPLACE VIEW v_kpi_cost_per_discharge AS
SELECT
    a.branch_id,
    b.name AS branch_name,
    a.department_id,
    d.name AS department_name,
    date_trunc('month', dis.discharge_at)::date AS period_month,
    COUNT(DISTINCT dis.admission_id) AS discharge_count,
    SUM(bill.total_amount) AS total_billing_inr,
    ROUND((SUM(bill.total_amount) / NULLIF(COUNT(DISTINCT dis.admission_id), 0))::numeric, 2) AS cost_per_discharge_inr
FROM admissions a
JOIN discharges dis ON dis.admission_id = a.admission_id
JOIN billing bill ON bill.admission_id = a.admission_id
JOIN hospital_branches b ON b.branch_id = a.branch_id
JOIN departments d ON d.department_id = a.department_id
GROUP BY a.branch_id, b.name, a.department_id, d.name,
         date_trunc('month', dis.discharge_at)::date;

-- View: Patient Outcome Distribution
CREATE OR REPLACE VIEW v_kpi_outcome_distribution AS
SELECT
    a.branch_id,
    b.name AS branch_name,
    a.department_id,
    d.name AS department_name,
    date_trunc('month', dis.discharge_at)::date AS period_month,
    dis.outcome_code,
    o.name AS outcome_name,
    COUNT(*) AS outcome_count
FROM admissions a
JOIN discharges dis ON dis.admission_id = a.admission_id
LEFT JOIN outcomes o ON o.code = dis.outcome_code
JOIN hospital_branches b ON b.branch_id = a.branch_id
JOIN departments d ON d.department_id = a.department_id
GROUP BY a.branch_id, b.name, a.department_id, d.name,
         date_trunc('month', dis.discharge_at)::date,
         dis.outcome_code, o.name;

-- View: ICU & Critical Care Utilization
-- Formula: ICU occupancy % = icu_occupied / icu_beds * 100
CREATE OR REPLACE VIEW v_kpi_icu_utilization AS
SELECT
    ra.branch_id,
    b.name AS branch_name,
    ra.record_date,
    ra.record_hour,
    ra.icu_occupied,
    b.icu_beds,
    ra.ventilators_used,
    b.ventilator_count,
    ROUND((ra.icu_occupied * 100.0 / NULLIF(b.icu_beds, 0))::numeric, 2) AS icu_occupancy_pct,
    ROUND((ra.ventilators_used * 100.0 / NULLIF(b.ventilator_count, 0))::numeric, 2) AS ventilator_utilization_pct
FROM resource_allocation ra
JOIN hospital_branches b ON b.branch_id = ra.branch_id
WHERE ra.department_id IS NULL  -- branch-level ICU
   OR EXISTS (SELECT 1 FROM departments d WHERE d.department_id = ra.department_id AND d.is_critical_care);

-- View: Executive KPI Snapshot (single row per period for dashboards)
CREATE OR REPLACE VIEW v_kpi_executive_snapshot AS
WITH adm AS (
    SELECT a.admission_id, a.branch_id, a.department_id, a.admission_type, a.admission_at,
           dis.discharge_at, dis.outcome_code,
           EXTRACT(EPOCH FROM (dis.discharge_at - a.admission_at))/86400 AS los_days
    FROM admissions a
    JOIN discharges dis ON dis.admission_id = a.admission_id
)
SELECT
    date_trunc('month', admission_at)::date AS period_month,
    COUNT(*) AS total_admissions,
    COUNT(*) AS total_discharges,
    ROUND(AVG(los_days)::numeric, 2) AS alos_days,
    COUNT(*) FILTER (WHERE admission_type = 'Emergency') AS emergency_count,
    COUNT(*) FILTER (WHERE admission_type IN ('Scheduled', 'Transfer')) AS scheduled_count
FROM adm
GROUP BY date_trunc('month', admission_at)::date
ORDER BY 1;
