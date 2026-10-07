/*
# Student Performance Data Warehouse Schema

1. Overview
This migration creates the PostgreSQL data warehouse for the Student Performance
and Dropout-Risk Prediction project (Part 1). It is a star-schema-inspired design
with dimension tables for students and subjects, a fact table for per-student
per-subject performance, an analytical data mart table, and a pipeline metadata
log table. This is a single-tenant, no-auth analytics application — there is no
sign-in screen, so all policies allow anon + authenticated access.

2. New Tables
- dim_student: one row per unique student (identified by the reproducible student_id).
  Columns: student_id (text, PK), school, sex, age, address, famsize, pstatus,
  medu, fedu, mjob, fjob, reason, guardian, traveltime, studytime, schoolsup,
  famsup, activities, nursery, higher, internet, romantic, famrel, freetime,
  goout, dalc, walc, health.
- dim_subject: two rows — Math and Portuguese.
  Columns: subject_id (serial, PK), subject_name (text, unique).
- fact_student_performance: one row per student per subject with raw academic
  grades and absences.
  Columns: id (serial, PK), student_id (FK to dim_student), subject_id (FK to
  dim_subject), failures, absences, g1_grade, g2_grade, g3_grade,
  loaded_at (timestamp).
- student_performance_analytics: the analytical data mart — one row per student
  per subject with engineered features and the rule-based risk category.
  Columns: student_id, subject, studytime, failures, absences, attendance_pct,
  g1_grade, g2_grade, g3_grade, academic_average, pass_fail, risk_score,
  risk_category, plus demographic context columns.
- pipeline_metadata_log: tracks each pipeline run (stage name, status, timestamp,
  row counts, error message).

3. Security
- RLS enabled on every table.
- All tables use TO anon, authenticated with USING (true) / WITH CHECK (true)
  because this is a single-tenant analytics application with no sign-in screen.
  The data is intentionally public/shared within the project.

4. Important Notes
- The schema is idempotent: uses IF NOT EXISTS and DROP POLICY IF EXISTS.
- UPSERT patterns in the Python loader use ON CONFLICT to avoid duplicate rows
  when the pipeline is re-run.
*/

-- ============================================================
-- dim_subject: simple subject dimension (Math, Portuguese)
-- ============================================================
CREATE TABLE IF NOT EXISTS dim_subject (
    subject_id   SERIAL PRIMARY KEY,
    subject_name TEXT UNIQUE NOT NULL
);

-- Seed the two subjects (idempotent via ON CONFLICT).
INSERT INTO dim_subject (subject_name)
VALUES ('Math'), ('Portuguese')
ON CONFLICT (subject_name) DO NOTHING;

-- ============================================================
-- dim_student: one row per unique student
-- ============================================================
CREATE TABLE IF NOT EXISTS dim_student (
    student_id    TEXT PRIMARY KEY,
    school        TEXT,
    sex           TEXT,
    age           INTEGER,
    address       TEXT,
    famsize       TEXT,
    pstatus       TEXT,
    medu          INTEGER,
    fedu          INTEGER,
    mjob          TEXT,
    fjob          TEXT,
    reason        TEXT,
    guardian      TEXT,
    traveltime    INTEGER,
    studytime     INTEGER,
    schoolsup     TEXT,
    famsup        TEXT,
    activities    TEXT,
    nursery       TEXT,
    higher        TEXT,
    internet      TEXT,
    romantic      TEXT,
    famrel        INTEGER,
    freetime      INTEGER,
    goout         INTEGER,
    dalc          INTEGER,
    walc          INTEGER,
    health        INTEGER
);

ALTER TABLE dim_student ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_dim_student" ON dim_student;
CREATE POLICY "anon_select_dim_student" ON dim_student FOR SELECT
    TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_dim_student" ON dim_student;
CREATE POLICY "anon_insert_dim_student" ON dim_student FOR INSERT
    TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_dim_student" ON dim_student;
CREATE POLICY "anon_update_dim_student" ON dim_student FOR UPDATE
    TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_dim_student" ON dim_student;
CREATE POLICY "anon_delete_dim_student" ON dim_student FOR DELETE
    TO anon, authenticated USING (true);

-- ============================================================
-- fact_student_performance: per-student per-subject grades
-- ============================================================
CREATE TABLE IF NOT EXISTS fact_student_performance (
    id          SERIAL PRIMARY KEY,
    student_id  TEXT NOT NULL REFERENCES dim_student(student_id) ON DELETE CASCADE,
    subject_id  INTEGER NOT NULL REFERENCES dim_subject(subject_id),
    failures    INTEGER,
    absences    INTEGER,
    g1_grade    INTEGER,
    g2_grade    INTEGER,
    g3_grade    INTEGER,
    loaded_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE(student_id, subject_id)
);

ALTER TABLE fact_student_performance ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_fact" ON fact_student_performance;
CREATE POLICY "anon_select_fact" ON fact_student_performance FOR SELECT
    TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_fact" ON fact_student_performance;
CREATE POLICY "anon_insert_fact" ON fact_student_performance FOR INSERT
    TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_fact" ON fact_student_performance;
CREATE POLICY "anon_update_fact" ON fact_student_performance FOR UPDATE
    TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_fact" ON fact_student_performance;
CREATE POLICY "anon_delete_fact" ON fact_student_performance FOR DELETE
    TO anon, authenticated USING (true);

-- ============================================================
-- student_performance_analytics: analytical data mart
-- ============================================================
CREATE TABLE IF NOT EXISTS student_performance_analytics (
    student_id        TEXT NOT NULL,
    subject           TEXT NOT NULL,
    school            TEXT,
    sex               TEXT,
    age               INTEGER,
    studytime         INTEGER,
    failures          INTEGER,
    absences          INTEGER,
    attendance_pct    NUMERIC(5,2),
    g1_grade          INTEGER,
    g2_grade          INTEGER,
    g3_grade          INTEGER,
    academic_average  NUMERIC(5,2),
    pass_fail          TEXT,
    risk_score        INTEGER,
    risk_category     TEXT,
    schoolsup        TEXT,
    famsup           TEXT,
    higher           TEXT,
    internet          TEXT,
    famrel            INTEGER,
    goout             INTEGER,
    dalc              INTEGER,
    walc              INTEGER,
    health            INTEGER,
    loaded_at         TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (student_id, subject)
);

ALTER TABLE student_performance_analytics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_analytics" ON student_performance_analytics;
CREATE POLICY "anon_select_analytics" ON student_performance_analytics FOR SELECT
    TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_analytics" ON student_performance_analytics;
CREATE POLICY "anon_insert_analytics" ON student_performance_analytics FOR INSERT
    TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_analytics" ON student_performance_analytics;
CREATE POLICY "anon_update_analytics" ON student_performance_analytics FOR UPDATE
    TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_analytics" ON student_performance_analytics;
CREATE POLICY "anon_delete_analytics" ON student_performance_analytics FOR DELETE
    TO anon, authenticated USING (true);

-- ============================================================
-- pipeline_metadata_log: tracks pipeline execution
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_metadata_log (
    id              SERIAL PRIMARY KEY,
    stage_name      TEXT NOT NULL,
    status          TEXT NOT NULL,
    records_processed INTEGER,
    error_message   TEXT,
    run_timestamp   TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE pipeline_metadata_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_pipeline_log" ON pipeline_metadata_log;
CREATE POLICY "anon_select_pipeline_log" ON pipeline_metadata_log FOR SELECT
    TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_pipeline_log" ON pipeline_metadata_log;
CREATE POLICY "anon_insert_pipeline_log" ON pipeline_metadata_log FOR INSERT
    TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_pipeline_log" ON pipeline_metadata_log;
CREATE POLICY "anon_update_pipeline_log" ON pipeline_metadata_log FOR UPDATE
    TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_pipeline_log" ON pipeline_metadata_log;
CREATE POLICY "anon_delete_pipeline_log" ON pipeline_metadata_log FOR DELETE
    TO anon, authenticated USING (true);
