"""Apache Airflow DAG for the Student Performance Pipeline.

This DAG orchestrates the complete Part 1 + Part 2 pipeline:

Part 1 (data engineering):
  1. ingest_source_data  - read CSVs from data/source/
  2. store_raw_data       - copy to data/raw/ (done inside ingestion)
  3. create_staging_data  - standardize and add student_id
  4. validate_data        - check quality rules, flag invalid rows
  5. save_rejected_records - write rejected rows to data/rejected/
  6. create_cleaned_data  - clean and deduplicate valid rows
  7. create_analytical_data - feature engineering + rule-based risk
  8. load_postgresql      - load cleaned + analytics into PostgreSQL
  9. create_or_refresh_analytics_data_mart - refresh the analytics table

Part 2 (ML/MLOps):
  10. train_ml_models     - train LR/RF/XGBoost, log to MLflow, register best
  11. save_training_profile - save training data profile for drift monitoring
  12. monitor_ml_model    - compute drift, quality, latency, failure metrics

The DAG reuses the existing Python functions from the pipeline modules
rather than duplicating logic.  Each task is a thin wrapper that calls the
corresponding module function.

Schedule: runs daily at 2:00 AM (suitable for demonstration).
Can also be triggered manually from the Airflow UI.

Setup:
  1. Set AIRFLOW_HOME to a directory of your choice.
  2. Copy or symlink this file to $AIRFLOW_HOME/dags/.
  3. Ensure the project root is on PYTHONPATH so imports resolve.
  4. Start Airflow:  airflow standalone  (or scheduler + webserver separately)
"""
from __future__ import annotations

import sys
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

# Add the project root to sys.path so pipeline modules can be imported
# when the DAG file is loaded by the Airflow scheduler.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Default arguments applied to every task in the DAG.
default_args = {
    "owner": "student-performance-project",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "email_on_failure": False,
    "email_on_retry": False,
}

dag = DAG(
    dag_id="student_performance_pipeline",
    description="Student Performance and Dropout-Risk Prediction - Part 1 Pipeline",
    default_args=default_args,
    start_date=datetime(2025, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["student", "performance", "analytics", "part1", "part2", "mlops"],
    doc_md=__doc__,
)


# --- Task functions (thin wrappers around existing pipeline modules) ---

def _ingest_source_data():
    """Stage 1: Read CSVs from data/source/ and copy to data/raw/."""
    from ingestion.ingest_data import run_ingestion
    run_ingestion()


def _store_raw_data():
    """Stage 1b: Raw copies are created inside run_ingestion; this task
    verifies the raw files exist and logs the count."""
    from config.settings import RAW_DIR
    raw_files = list(RAW_DIR.glob("*.csv"))
    if not raw_files:
        raise ValueError("No raw files found after ingestion")
    print(f"Verified {len(raw_files)} raw file(s) in {RAW_DIR}")


def _create_staging_data():
    """Stage 2: Standardize columns, types, and add student_id."""
    from transformation.stage_data import run_staging
    run_staging()


def _validate_data():
    """Stage 3: Validate staged data and produce validation report."""
    from transformation.validate_data import run_validation
    run_validation()


def _save_rejected_records():
    """Stage 4: Save rejected records (done inside run_validation).
    This task verifies the rejected file exists."""
    from config.settings import REJECTED_DIR
    rejected_path = REJECTED_DIR / "rejected_records.csv"
    if rejected_path.exists():
        import pandas as pd
        df = pd.read_csv(rejected_path)
        print(f"Rejected records: {len(df)} rows in {rejected_path}")
    else:
        print("No rejected records file (no invalid rows found).")


def _create_cleaned_data():
    """Stage 5: Clean and deduplicate valid records."""
    from transformation.clean_data import run_cleaning
    run_cleaning()


def _create_analytical_data():
    """Stage 6: Feature engineering and rule-based risk categorization."""
    from transformation.create_analytics import create_analytics
    create_analytics()


def _load_postgresql():
    """Stage 7: Load cleaned and analytical data into PostgreSQL."""
    from database.load_data import run_database_load
    run_database_load()


def _create_or_refresh_analytics_data_mart():
    """Stage 8: Refresh the analytics data mart table.
    The analytics table is loaded during _load_postgresql; this task
    verifies the data is present in the database."""
    from database.db_client import fetch_all
    rows = fetch_all("student_performance_analytics", "student_id")
    if not rows:
        raise ValueError("Analytics data mart is empty after loading")
    print(f"Analytics data mart verified: {len(rows)} rows retrieved")


# --- Task definitions ---

ingest_task = PythonOperator(
    task_id="ingest_source_data",
    python_callable=_ingest_source_data,
    dag=dag,
)

raw_task = PythonOperator(
    task_id="store_raw_data",
    python_callable=_store_raw_data,
    dag=dag,
)

staging_task = PythonOperator(
    task_id="create_staging_data",
    python_callable=_create_staging_data,
    dag=dag,
)

validate_task = PythonOperator(
    task_id="validate_data",
    python_callable=_validate_data,
    dag=dag,
)

rejected_task = PythonOperator(
    task_id="save_rejected_records",
    python_callable=_save_rejected_records,
    dag=dag,
)

clean_task = PythonOperator(
    task_id="create_cleaned_data",
    python_callable=_create_cleaned_data,
    dag=dag,
)

analytics_task = PythonOperator(
    task_id="create_analytical_data",
    python_callable=_create_analytical_data,
    dag=dag,
)

db_task = PythonOperator(
    task_id="load_postgresql",
    python_callable=_load_postgresql,
    dag=dag,
)

mart_task = PythonOperator(
    task_id="create_or_refresh_analytics_data_mart",
    python_callable=_create_or_refresh_analytics_data_mart,
    dag=dag,
)

# --- Part 2: ML / MLOps tasks ---


def _train_ml_models():
    """Part 2 Stage 1: Train ML models, log to MLflow, register best model."""
    from models.train import train_all
    train_all()


def _save_training_profile():
    """Part 2 Stage 2: Save training data profile for drift monitoring."""
    from monitoring.drift_monitor import save_training_profile
    save_training_profile()


def _monitor_ml_model():
    """Part 2 Stage 3: Compute monitoring metrics (drift, quality, latency)."""
    from monitoring.drift_monitor import write_monitoring_metrics
    write_monitoring_metrics()


train_task = PythonOperator(
    task_id="train_ml_models",
    python_callable=_train_ml_models,
    dag=dag,
)

profile_task = PythonOperator(
    task_id="save_training_profile",
    python_callable=_save_training_profile,
    dag=dag,
)

monitor_task = PythonOperator(
    task_id="monitor_ml_model",
    python_callable=_monitor_ml_model,
    dag=dag,
)


# --- Task dependencies (linear flow) ---
ingest_task >> raw_task >> staging_task >> validate_task >> rejected_task
rejected_task >> clean_task >> analytics_task >> db_task >> mart_task

# Part 2: ML training after data pipeline, then monitoring
mart_task >> train_task >> profile_task >> monitor_task
