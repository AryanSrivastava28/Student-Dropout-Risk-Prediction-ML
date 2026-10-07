/*
# Create ml_monitoring_metrics table (Part 2 - ML Monitoring)

1. New Tables
- `ml_monitoring_metrics`: stores ML monitoring snapshots computed by
  monitoring/drift_monitor.py. One row per monitoring run.
  Columns:
    - id (serial, PK)
    - computed_at (timestamptz, when metrics were computed)
    - drift_detected (boolean, whether feature drift was detected)
    - num_predictions (integer, number of recent predictions analyzed)
    - latency_mean_ms (numeric, mean prediction latency)
    - latency_p95_ms (numeric, 95th percentile latency)
    - error_rate (numeric, percentage of failed predictions)
    - input_quality_score (numeric, 0-100 input quality percentage)
    - at_risk_pct (numeric, percentage of predictions classified as at-risk)
    - metrics_json (jsonb, full metrics breakdown including per-feature drift)

2. Security
- RLS enabled on ml_monitoring_metrics.
- All tables use TO anon, authenticated with USING (true) / WITH CHECK (true)
  because this is a single-tenant analytics application with no sign-in screen.
  The data is intentionally public/shared within the project (same pattern as
  all other Part 1 tables).

3. Important Notes
- This table is written to by monitoring/drift_monitor.py via the REST API
  database client. If the database is unavailable, monitoring falls back to
  CSV so prediction is never broken.
- Idempotent: uses IF NOT EXISTS and DROP POLICY IF EXISTS.
*/

CREATE TABLE IF NOT EXISTS ml_monitoring_metrics (
    id                  SERIAL PRIMARY KEY,
    computed_at         TIMESTAMPTZ DEFAULT now(),
    drift_detected      BOOLEAN DEFAULT false,
    num_predictions     INTEGER DEFAULT 0,
    latency_mean_ms     NUMERIC(10,2) DEFAULT 0,
    latency_p95_ms      NUMERIC(10,2) DEFAULT 0,
    error_rate          NUMERIC(5,2) DEFAULT 0,
    input_quality_score NUMERIC(5,2) DEFAULT 100,
    at_risk_pct         NUMERIC(5,2) DEFAULT 0,
    metrics_json        JSONB DEFAULT '{}'::jsonb
);

ALTER TABLE ml_monitoring_metrics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_ml_monitoring" ON ml_monitoring_metrics;
CREATE POLICY "anon_select_ml_monitoring" ON ml_monitoring_metrics FOR SELECT
    TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_ml_monitoring" ON ml_monitoring_metrics;
CREATE POLICY "anon_insert_ml_monitoring" ON ml_monitoring_metrics FOR INSERT
    TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_ml_monitoring" ON ml_monitoring_metrics;
CREATE POLICY "anon_update_ml_monitoring" ON ml_monitoring_metrics FOR UPDATE
    TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_ml_monitoring" ON ml_monitoring_metrics;
CREATE POLICY "anon_delete_ml_monitoring" ON ml_monitoring_metrics FOR DELETE
    TO anon, authenticated USING (true);
