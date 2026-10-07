-- ============================================================
-- Student Performance Data Warehouse Schema
-- ============================================================
-- This file documents the PostgreSQL schema for the Student Performance
-- and Dropout-Risk Prediction project (Part 1).
--
-- The actual schema is applied to the Supabase PostgreSQL database via
-- the Supabase MCP apply_migration tool. This file is for reference and
-- documentation purposes.
--
-- Design: star-schema-inspired
--   dim_student  --> fact_student_performance <-- dim_subject
--   student_performance_analytics (analytical data mart)
--   pipeline_metadata_log (pipeline execution tracking)
-- ============================================================

-- ============================================================
-- dim_subject: simple subject dimension (Math, Portuguese)
-- ============================================================
CREATE TABLE IF NOT EXISTS dim_subject (
    subject_id   SERIAL PRIMARY KEY,
    subject_name TEXT UNIQUE NOT NULL
);

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
    pass_fail         TEXT,
    risk_score        INTEGER,
    risk_category     TEXT,
    schoolsup         TEXT,
    famsup            TEXT,
    higher            TEXT,
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

-- ============================================================
-- pipeline_metadata_log: tracks pipeline execution
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_metadata_log (
    id                SERIAL PRIMARY KEY,
    stage_name        TEXT NOT NULL,
    status            TEXT NOT NULL,
    records_processed INTEGER,
    error_message     TEXT,
    run_timestamp     TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE pipeline_metadata_log ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- RLS Policies (single-tenant, no-auth application)
-- All tables allow anon + authenticated full CRUD because the data
-- is intentionally shared/public within the analytics project.
-- ============================================================

-- dim_student policies
CREATE POLICY "anon_select_dim_student" ON dim_student FOR SELECT
    TO anon, authenticated USING (true);
CREATE POLICY "anon_insert_dim_student" ON dim_student FOR INSERT
    TO anon, authenticated WITH CHECK (true);
CREATE POLICY "anon_update_dim_student" ON dim_student FOR UPDATE
    TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "anon_delete_dim_student" ON dim_student FOR DELETE
    TO anon, authenticated USING (true);

-- fact_student_performance policies
CREATE POLICY "anon_select_fact" ON fact_student_performance FOR SELECT
    TO anon, authenticated USING (true);
CREATE POLICY "anon_insert_fact" ON fact_student_performance FOR INSERT
    TO anon, authenticated WITH CHECK (true);
CREATE POLICY "anon_update_fact" ON fact_student_performance FOR UPDATE
    TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "anon_delete_fact" ON fact_student_performance FOR DELETE
    TO anon, authenticated USING (true);

-- student_performance_analytics policies
CREATE POLICY "anon_select_analytics" ON student_performance_analytics FOR SELECT
    TO anon, authenticated USING (true);
CREATE POLICY "anon_insert_analytics" ON student_performance_analytics FOR INSERT
    TO anon, authenticated WITH CHECK (true);
CREATE POLICY "anon_update_analytics" ON student_performance_analytics FOR UPDATE
    TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "anon_delete_analytics" ON student_performance_analytics FOR DELETE
    TO anon, authenticated USING (true);

-- pipeline_metadata_log policies
CREATE POLICY "anon_select_pipeline_log" ON pipeline_metadata_log FOR SELECT
    TO anon, authenticated USING (true);
CREATE POLICY "anon_insert_pipeline_log" ON pipeline_metadata_log FOR INSERT
    TO anon, authenticated WITH CHECK (true);
CREATE POLICY "anon_update_pipeline_log" ON pipeline_metadata_log FOR UPDATE
    TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "anon_delete_pipeline_log" ON pipeline_metadata_log FOR DELETE
    TO anon, authenticated USING (true);
