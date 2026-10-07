"""End-to-end pipeline runner for the Student Performance project.

This script runs all Part 1 stages in sequence:
  1. Ingestion (source -> raw)
  2. Staging (raw -> staging)
  3. Validation (staging -> valid + rejected)
  4. Cleaning (valid -> cleaned)
  5. Analytics (cleaned -> analytical)
  6. PostgreSQL loading (cleaned + analytical -> database)

Usage:
    python run_pipeline.py
"""
from __future__ import annotations

import sys
import traceback

from config.settings import ensure_directories


def run_full_pipeline() -> None:
    """Run the complete Part 1 pipeline from ingestion to database loading."""
    ensure_directories()
    print("=" * 60)
    print("Student Performance Pipeline - Full Run")
    print("=" * 60)

    # Stage 1: Ingestion
    from ingestion.ingest_data import run_ingestion

    print()
    run_ingestion()

    # Stage 2: Staging
    from transformation.stage_data import run_staging

    print()
    run_staging()

    # Stages 3-6: Validation -> Cleaning -> Analytics
    # create_analytics calls run_cleaning which calls run_validation,
    # so running analytics triggers the full chain.
    from transformation.create_analytics import create_analytics

    print()
    analytics_df = create_analytics()

    # Stage 7: Database loading
    from database.load_data import run_database_load

    print()
    if analytics_df is not None and not analytics_df.empty:
        # Load the cleaned data alongside analytics.
        import pandas as pd

        from config.settings import CLEANED_DIR

        cleaned_path = CLEANED_DIR / "student_all_cleaned.csv"
        cleaned_df = pd.read_csv(cleaned_path) if cleaned_path.exists() else None
        run_database_load(cleaned_df=cleaned_df, analytics_df=analytics_df)
    else:
        print("Skipping database loading: no analytics data available.")

    print()
    print("=" * 60)
    print("Pipeline complete!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        run_full_pipeline()
    except Exception:
        print("Pipeline failed with error:")
        traceback.print_exc()
        sys.exit(1)
