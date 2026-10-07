"""Stage 3 - Data Validation.

Validates staged data for quality issues and produces:
  - ``logs/validation_report.csv``  (summary report per source file)
  - ``data/rejected/rejected_records.csv`` (invalid rows with rejection reason)

Validation rules
----------------
1. Duplicate records - duplicate student_id + subject combinations
2. Missing critical identifiers - null or empty student_id
3. Invalid numeric values - non-numeric entries in numeric columns
4. Invalid mark ranges - G1, G2, G3 must be between 0 and 20
5. Invalid attendance ranges - absences must be between 0 and 93
6. Invalid categorical values - known categorical columns must contain
   only their allowed values
7. Data type issues - numeric columns must be numeric after coercion

Each invalid row is tagged with one or more rejection reasons and written
to the rejected records file.  Valid rows are returned for the cleaning stage.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config.settings import (
    REJECTED_DIR,
    STAGING_DIR,
    VALIDATION_REPORT_FILE,
    ensure_directories,
)

# Allowed values for categorical columns (from the UCI dataset description).
CATEGORICAL_VALID_VALUES: dict[str, set[str]] = {
    "school": {"GP", "MS"},
    "sex": {"F", "M"},
    "address": {"U", "R"},
    "famsize": {"LE3", "GT3"},
    "Pstatus": {"T", "A"},
    "Mjob": {"teacher", "health", "services", "at_home", "other"},
    "Fjob": {"teacher", "health", "services", "at_home", "other"},
    "reason": {"home", "reputation", "course", "other"},
    "guardian": {"mother", "father", "other"},
    "schoolsup": {"yes", "no"},
    "famsup": {"yes", "no"},
    "paid": {"yes", "no"},
    "activities": {"yes", "no"},
    "nursery": {"yes", "no"},
    "higher": {"yes", "no"},
    "internet": {"yes", "no"},
    "romantic": {"yes", "no"},
}

# Valid ranges for numeric columns: (min, max).
NUMERIC_VALID_RANGES: dict[str, tuple[int, int]] = {
    "age": (15, 22),
    "Medu": (0, 4),
    "Fedu": (0, 4),
    "traveltime": (1, 4),
    "studytime": (1, 4),
    "failures": (0, 4),
    "famrel": (1, 5),
    "freetime": (1, 5),
    "goout": (1, 5),
    "Dalc": (1, 5),
    "Walc": (1, 5),
    "health": (1, 5),
    "absences": (0, 93),
    "G1": (0, 20),
    "G2": (0, 20),
    "G3": (0, 20),
}

# Columns that are critical - a missing/null value means rejection.
CRITICAL_COLUMNS = ["student_id", "subject"]

# Columns for the validation report.
REPORT_COLUMNS = [
    "source_file",
    "validation_timestamp",
    "total_records",
    "valid_records",
    "invalid_records",
    "duplicate_records",
    "missing_values_found",
    "validation_errors",
]


def _check_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Flag duplicate student_id + subject rows.  Returns a boolean mask."""
    dup_mask = df.duplicated(subset=["student_id", "subject"], keep=False)
    return dup_mask


def _check_missing_critical(df: pd.DataFrame) -> pd.DataFrame:
    """Flag rows with missing critical identifiers.  Returns boolean mask."""
    mask = pd.Series(False, index=df.index)
    for col in CRITICAL_COLUMNS:
        if col in df.columns:
            col_mask = df[col].isna() | (df[col].astype(str).str.strip() == "")
            mask = mask | col_mask
    return mask


def _check_numeric_ranges(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Check each numeric column for out-of-range or null values.

    Returns a dict mapping column name to a boolean mask of invalid rows.
    """
    results: dict[str, pd.Series] = {}
    for col, (min_val, max_val) in NUMERIC_VALID_RANGES.items():
        if col not in df.columns:
            continue
        col_data = pd.to_numeric(df[col], errors="coerce")
        invalid = col_data.isna() | (col_data < min_val) | (col_data > max_val)
        results[col] = invalid
    return results


def _check_categorical_values(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Check categorical columns for invalid values.  Returns boolean masks."""
    results: dict[str, pd.Series] = {}
    for col, valid_set in CATEGORICAL_VALID_VALUES.items():
        if col not in df.columns:
            continue
        invalid = ~df[col].astype(str).str.strip().isin(valid_set)
        # Also flag NaN/empty as invalid for categoricals.
        invalid = invalid | df[col].isna() | (df[col].astype(str).str.strip() == "")
        results[col] = invalid
    return results


def validate_single_file(staged_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate a single staged file.

    Returns:
        valid_df: rows that passed all validation checks.
        rejected_df: rows that failed, with rejection_reason and source_file.
    """
    print(f"  [validate] Processing {staged_path.name} ...")
    df = pd.read_csv(staged_path)
    timestamp = datetime.now(timezone.utc).isoformat()

    # Track rejection reasons per row.
    reasons: pd.Series = pd.Series([""] * len(df), index=df.index)

    # 1. Duplicates
    dup_mask = _check_duplicates(df)
    dup_count = int(dup_mask.sum())
    reasons[dup_mask] = reasons[dup_mask] + "duplicate_record; "

    # 2. Missing critical identifiers
    missing_mask = _check_missing_critical(df)
    reasons[missing_mask] = reasons[missing_mask] + "missing_critical_id; "

    # 3 & 4 & 5. Numeric range checks
    numeric_issues = _check_numeric_ranges(df)
    missing_values_found = 0
    for col, mask in numeric_issues.items():
        invalid_count = int(mask.sum())
        if invalid_count > 0:
            reasons[mask] = reasons[mask] + f"invalid_{col}; "
            missing_values_found += invalid_count

    # 6. Categorical value checks
    cat_issues = _check_categorical_values(df)
    for col, mask in cat_issues.items():
        invalid_count = int(mask.sum())
        if invalid_count > 0:
            reasons[mask] = reasons[mask] + f"invalid_{col}; "

    # 7. Data type issues are implicitly caught by numeric coercion above.

    # Build rejected DataFrame.
    invalid_mask = reasons.str.strip().str.len() > 0
    rejected_df = df[invalid_mask].copy()
    rejected_df["rejection_reason"] = reasons[invalid_mask].str.strip().str.rstrip("; ")
    rejected_df["source_file"] = staged_path.name
    rejected_df["rejection_timestamp"] = timestamp

    valid_df = df[~invalid_mask].copy()

    # Write validation report row.
    report_row = pd.DataFrame(
        [
            {
                "source_file": staged_path.name,
                "validation_timestamp": timestamp,
                "total_records": len(df),
                "valid_records": len(valid_df),
                "invalid_records": len(rejected_df),
                "duplicate_records": dup_count,
                "missing_values_found": missing_values_found,
                "validation_errors": "; ".join(
                    sorted(set(reasons[invalid_mask].str.split("; ").explode())
                           - {""})
                ),
            }
        ],
        columns=REPORT_COLUMNS,
    )
    write_header = not VALIDATION_REPORT_FILE.exists()
    report_row.to_csv(VALIDATION_REPORT_FILE, mode="a", header=write_header, index=False)

    print(
        f"  [validate] {staged_path.name}: total={len(df)}, "
        f"valid={len(valid_df)}, invalid={len(rejected_df)}, "
        f"duplicates={dup_count}"
    )
    return valid_df, rejected_df


def run_validation() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate all staged files and save rejected records.

    Returns:
        combined_valid: all valid rows across all files.
        combined_rejected: all rejected rows with reasons.
    """
    ensure_directories()
    print("=== Stage 3: Data Validation ===")

    # Clear previous validation report for a fresh run.
    if VALIDATION_REPORT_FILE.exists():
        VALIDATION_REPORT_FILE.unlink()

    staged_files = sorted(STAGING_DIR.glob("*.csv"))
    if not staged_files:
        print("  [validate] No staged files found in data/staging/")
        return pd.DataFrame(), pd.DataFrame()

    all_valid: list[pd.DataFrame] = []
    all_rejected: list[pd.DataFrame] = []

    for staged_path in staged_files:
        valid_df, rejected_df = validate_single_file(staged_path)
        all_valid.append(valid_df)
        all_rejected.append(rejected_df)

    combined_valid = pd.concat(all_valid, ignore_index=True) if all_valid else pd.DataFrame()
    combined_rejected = (
        pd.concat(all_rejected, ignore_index=True) if all_rejected else pd.DataFrame()
    )

    # Save rejected records (Stage 4).
    if not combined_rejected.empty:
        rejected_path = REJECTED_DIR / "rejected_records.csv"
        combined_rejected.to_csv(rejected_path, index=False)
        print(f"  [validate] Rejected records saved: {rejected_path} ({len(combined_rejected)} rows)")
    else:
        print("  [validate] No rejected records to save.")

    print(f"  [validate] Validation report: {VALIDATION_REPORT_FILE}")
    print(
        f"  [validate] Totals: valid={len(combined_valid)}, "
        f"rejected={len(combined_rejected)}"
    )
    return combined_valid, combined_rejected


if __name__ == "__main__":
    run_validation()
