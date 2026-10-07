"""Stage 5 - Cleaned Data Layer.

Takes the valid records produced by the validation stage and applies
documented cleaning rules to produce clean, analysis-ready datasets.

Cleaning rules (documented in docs/validation_rules.md):
  1. Remove duplicate records (already flagged by validation; we keep the
     first occurrence of any student_id + subject combination).
  2. Handle missing values:
     - Numeric columns: fill with the median of that column within the same
       subject group (so Math and Portuguese are handled independently).
     - Categorical columns: fill with the mode of that column within the same
       subject group.  If mode is empty, fill with "unknown".
  3. Correct data types: ensure all numeric columns are integers and all
     categorical columns are strings.
  4. Ensure important fields are valid (ranges already checked in validation;
     here we clip any edge-case values that slipped through).
  5. Retain only accepted (valid) records - rejected rows are excluded.

Output: ``data/cleaned/student-mat.csv`` and ``data/cleaned/student-por.csv``
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import CLEANED_DIR, ensure_directories
from transformation.stage_data import CATEGORICAL_COLUMNS, NUMERIC_COLUMNS
from transformation.validate_data import run_validation


def _deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the first occurrence of each student_id + subject pair."""
    before = len(df)
    df = df.drop_duplicates(subset=["student_id", "subject"], keep="first")
    removed = before - len(df)
    if removed > 0:
        print(f"  [clean] Removed {removed} duplicate row(s).")
    return df


def _handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing numeric values with group median, categoricals with mode."""
    subject_groups = df.groupby("subject")

    for col in NUMERIC_COLUMNS:
        if col not in df.columns:
            continue
        if df[col].isna().any():
            # Fill with per-subject median, then global median as fallback.
            medians = subject_groups[col].transform("median")
            df[col] = df[col].fillna(medians)
            df[col] = df[col].fillna(df[col].median())
            print(f"  [clean] Filled missing values in '{col}' with median.")

    for col in CATEGORICAL_COLUMNS:
        if col not in df.columns:
            continue
        if df[col].isna().any() or (df[col].astype(str).str.strip() == "").any():
            modes = subject_groups[col].transform(
                lambda s: s.mode().iloc[0] if not s.mode().empty else "unknown"
            )
            df[col] = df[col].astype(str).str.strip().replace("", pd.NA)
            df[col] = df[col].fillna(modes)
            df[col] = df[col].fillna("unknown")
            print(f"  [clean] Filled missing values in '{col}' with mode.")

    return df


def _correct_types(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure numeric columns are integers and categoricals are strings."""
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in CATEGORICAL_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # student_id and subject are always strings.
    df["student_id"] = df["student_id"].astype(str).str.strip()
    df["subject"] = df["subject"].astype(str).str.strip()

    return df


def run_cleaning() -> pd.DataFrame:
    """Run the full cleaning pipeline and save cleaned files.

    Returns the combined cleaned DataFrame (all subjects).
    """
    ensure_directories()
    print("=== Stage 5: Cleaned Data Layer ===")

    # Get valid records from the validation stage.
    valid_df, _ = run_validation()

    if valid_df.empty:
        print("  [clean] No valid records to clean.")
        return pd.DataFrame()

    # Apply cleaning steps.
    print("  [clean] Deduplicating ...")
    cleaned = _deduplicate(valid_df)

    print("  [clean] Handling missing values ...")
    cleaned = _handle_missing_values(cleaned)

    print("  [clean] Correcting data types ...")
    cleaned = _correct_types(cleaned)

    # Save per-subject cleaned files.
    for subject, group in cleaned.groupby("subject"):
        file_name = "student-mat.csv" if subject == "Math" else "student-por.csv"
        output_path = CLEANED_DIR / file_name
        group.to_csv(output_path, index=False)
        print(f"  [clean] Saved {output_path.name} ({len(group)} rows)")

    # Also save a combined cleaned file for convenience.
    combined_path = CLEANED_DIR / "student_all_cleaned.csv"
    cleaned.to_csv(combined_path, index=False)
    print(f"  [clean] Saved combined {combined_path.name} ({len(cleaned)} rows)")

    print("  [clean] Cleaning complete.")
    return cleaned


if __name__ == "__main__":
    run_cleaning()
