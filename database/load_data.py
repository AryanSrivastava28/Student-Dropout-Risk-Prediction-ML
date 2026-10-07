"""Stage 7 - Load cleaned and analytical data into PostgreSQL.

Loads the cleaned and analytical CSV data into the Supabase PostgreSQL data
warehouse.  The loading is idempotent: existing rows are upserted (merged) so
re-running the pipeline does not create duplicate records.

Tables loaded:
  - dim_student          : unique students from cleaned data
  - fact_student_performance : per-student per-subject grades
  - student_performance_analytics : analytical data mart
  - pipeline_metadata_log     : pipeline execution tracking
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from config.settings import ANALYTICAL_DIR, CLEANED_DIR, ensure_directories
from database.db_client import delete_all, test_connection, upsert_rows


def _load_dim_students(cleaned_df: pd.DataFrame) -> int:
    """Extract unique students and load into dim_student."""
    student_cols = [
        "student_id", "school", "sex", "age", "address", "famsize",
        "Pstatus", "Medu", "Fedu", "Mjob", "Fjob", "reason", "guardian",
        "traveltime", "studytime", "schoolsup", "famsup", "activities",
        "nursery", "higher", "internet", "romantic", "famrel", "freetime",
        "goout", "Dalc", "Walc", "health",
    ]
    available_cols = [c for c in student_cols if c in cleaned_df.columns]
    students = cleaned_df[available_cols].drop_duplicates(subset=["student_id"])

    # Rename columns to lowercase to match the database schema.
    students.columns = [c.lower() for c in students.columns]

    rows = students.to_dict(orient="records")
    # Convert NaN to None for JSON serialization.
    for row in rows:
        for k, v in row.items():
            if pd.isna(v):
                row[k] = None

    count = upsert_rows("dim_student", rows, on_conflict="student_id")
    print(f"  [db] dim_student: {count} rows upserted")
    return count


def _load_fact_performance(cleaned_df: pd.DataFrame) -> int:
    """Load per-student per-subject grades into fact_student_performance."""
    # Map subject names to subject_ids (Math=1, Portuguese=2).
    subject_map = {"Math": 1, "Portuguese": 2}

    fact_rows = []
    for _, row in cleaned_df.iterrows():
        subject_id = subject_map.get(row.get("subject", ""), None)
        if subject_id is None:
            continue
        fact_rows.append(
            {
                "student_id": row["student_id"],
                "subject_id": subject_id,
                "failures": int(row["failures"]) if pd.notna(row["failures"]) else None,
                "absences": int(row["absences"]) if pd.notna(row["absences"]) else None,
                "g1_grade": int(row["G1"]) if pd.notna(row.get("G1")) else None,
                "g2_grade": int(row["G2"]) if pd.notna(row.get("G2")) else None,
                "g3_grade": int(row["G3"]) if pd.notna(row.get("G3")) else None,
            }
        )

    count = upsert_rows(
        "fact_student_performance", fact_rows, on_conflict="student_id,subject_id"
    )
    print(f"  [db] fact_student_performance: {count} rows upserted")
    return count


def _load_analytics(analytics_df: pd.DataFrame) -> int:
    """Load the analytical data mart into student_performance_analytics."""
    # Lowercase column names to match the database schema.
    analytics_df = analytics_df.copy()
    analytics_df.columns = [c.lower() for c in analytics_df.columns]

    rows = analytics_df.to_dict(orient="records")

    # Convert NaN to None and ensure correct types.
    for row in rows:
        for k, v in row.items():
            if pd.isna(v):
                row[k] = None
            elif k in ("attendance_pct", "academic_average") and v is not None:
                row[k] = float(v)
            elif k in ("age", "studytime", "failures", "absences",
                       "g1_grade", "g2_grade", "g3_grade",
                       "risk_score", "famrel", "goout", "Dalc", "Walc", "health") and v is not None:
                row[k] = int(v)

    count = upsert_rows(
        "student_performance_analytics", rows, on_conflict="student_id,subject"
    )
    print(f"  [db] student_performance_analytics: {count} rows upserted")
    return count


def _log_pipeline_metadata(stage: str, status: str, records: int, error: str = "") -> None:
    """Write a pipeline metadata log entry."""
    row = {
        "stage_name": stage,
        "status": status,
        "records_processed": records,
        "error_message": error,
    }
    upsert_rows("pipeline_metadata_log", [row])


def run_database_load(
    cleaned_df: pd.DataFrame | None = None,
    analytics_df: pd.DataFrame | None = None,
) -> bool:
    """Load cleaned and analytical data into PostgreSQL.

    Args:
        cleaned_df: optional pre-loaded cleaned DataFrame.
        analytics_df: optional pre-loaded analytics DataFrame.

    Returns True on success, False on failure.
    """
    ensure_directories()
    print("=== Stage 7: PostgreSQL Database Loading ===")

    if not test_connection():
        print("  [db] ERROR: Cannot connect to the database.")
        _log_pipeline_metadata("load_postgresql", "failed", 0, "Connection failed")
        return False

    print("  [db] Connection OK.")

    # Load data from files if DataFrames not provided.
    if cleaned_df is None:
        cleaned_path = CLEANED_DIR / "student_all_cleaned.csv"
        if not cleaned_path.exists():
            print("  [db] ERROR: Cleaned data not found. Run the pipeline first.")
            return False
        cleaned_df = pd.read_csv(cleaned_path)

    if analytics_df is None:
        analytics_path = ANALYTICAL_DIR / "student_analytics.csv"
        if not analytics_path.exists():
            print("  [db] ERROR: Analytics data not found. Run the pipeline first.")
            return False
        analytics_df = pd.read_csv(analytics_path)

    try:
        _load_dim_students(cleaned_df)
        _load_fact_performance(cleaned_df)
        _load_analytics(analytics_df)
        _log_pipeline_metadata("load_postgresql", "success", len(analytics_df))
        print("  [db] Database loading complete.")
        return True
    except Exception as exc:
        print(f"  [db] ERROR: {exc}")
        _log_pipeline_metadata("load_postgresql", "failed", 0, str(exc))
        return False


if __name__ == "__main__":
    run_database_load()
