"""Stage 2 - Staging Layer.

Reads **only** from the raw layer (``data/raw/``), standardizes column names and
data types, adds a reproducible student identifier, and writes staged CSV files
to ``data/staging/``.

Student ID generation rule
--------------------------
The UCI dataset does not include a real student identifier. We generate a
reproducible ``student_id`` by hashing the combination of demographic and
family attributes that uniquely identify a student across the two course
datasets (Math and Portuguese). The attributes used are exactly those listed
in the dataset's ``student-merge.R`` file as the join key:

    school, sex, age, address, famsize, Pstatus, Medu, Fedu,
    Mjob, Fjob, reason, guardian, traveltime, studytime

A SHA-256 hash of these concatenated field values (lowercased, stripped)
produces a stable 12-character hex identifier such as
``STU_A3F2B1C9D8E7``. The same student appearing in both the Math and
Portuguese files will receive the same ``student_id``, enabling later
linking of subject records.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from config.settings import RAW_DIR, STAGING_DIR, ensure_directories


# Columns that identify a unique student (from the UCI student-merge.R key).
STUDENT_KEY_COLUMNS = [
    "school",
    "sex",
    "age",
    "address",
    "famsize",
    "Pstatus",
    "Medu",
    "Fedu",
    "Mjob",
    "Fjob",
    "reason",
    "guardian",
    "traveltime",
    "studytime",
]


# Mapping of original column names to standardized lowercase names.
# The UCI dataset already uses consistent names, so this mainly lowercases them
# and documents the expected types.
NUMERIC_COLUMNS = [
    "age",
    "Medu",
    "Fedu",
    "traveltime",
    "studytime",
    "failures",
    "famrel",
    "freetime",
    "goout",
    "Dalc",
    "Walc",
    "health",
    "absences",
    "G1",
    "G2",
    "G3",
]


CATEGORICAL_COLUMNS = [
    "school",
    "sex",
    "address",
    "famsize",
    "Pstatus",
    "Mjob",
    "Fjob",
    "reason",
    "guardian",
    "schoolsup",
    "famsup",
    "paid",
    "activities",
    "nursery",
    "higher",
    "internet",
    "romantic",
]


def _generate_student_id(row: pd.Series) -> str:
    """Generate a reproducible student_id from demographic key columns."""
    key_string = "|".join(
        str(row[col]).strip().lower() for col in STUDENT_KEY_COLUMNS
    )

    digest = hashlib.sha256(
        key_string.encode("utf-8")
    ).hexdigest()[:12]

    return f"STU_{digest.upper()}"


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase all column names and strip whitespace from string values."""

    df.columns = [c.strip() for c in df.columns]

    # Strip whitespace from all object (string) columns.
    # Only "object" is used here for compatibility with the installed
    # Pandas version.
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).str.strip()

    return df


def _standardize_types(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce known numeric columns to integers and validate ranges later."""

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            # Use to_numeric first to catch non-numeric junk, then to Int64
            # so missing values are preserved as <NA>.
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            ).astype("Int64")

    return df


def stage_single_file(raw_path: Path) -> Path | None:
    """Stage a single raw CSV file: standardize, add student_id, save."""

    print(f"  [stage] Processing {raw_path.name} ...")

    try:
        df = pd.read_csv(raw_path, sep=";")
    except Exception as exc:  # noqa: BLE001
        print(f"  [stage] ERROR reading {raw_path.name}: {exc}")
        return None

    df = _standardize_columns(df)
    df = _standardize_types(df)

    # Add the reproducible student_id before any other column.
    df.insert(
        0,
        "student_id",
        df.apply(_generate_student_id, axis=1)
    )

    # Add a subject column derived from the file name
    # (mat -> Math, por -> Portuguese).
    subject = "Math" if "mat" in raw_path.stem else "Portuguese"

    df.insert(1, "subject", subject)

    output_path = STAGING_DIR / raw_path.name

    df.to_csv(output_path, index=False)

    print(
        f"  [stage] OK  {raw_path.name} -> {output_path.name}  "
        f"({len(df)} rows, {len(df.columns)} columns)"
    )

    return output_path


def run_staging() -> list[Path]:
    """Stage all raw CSV files into ``data/staging/``."""

    ensure_directories()

    print("=== Stage 2: Staging Layer ===")

    raw_files = sorted(RAW_DIR.glob("*.csv"))

    if not raw_files:
        print("  [stage] No raw files found in data/raw/")
        return []

    print(f"  [stage] Found {len(raw_files)} raw file(s).")

    staged_paths: list[Path] = []

    for raw_path in raw_files:
        result = stage_single_file(raw_path)

        if result is not None:
            staged_paths.append(result)

    print(
        f"  [stage] Staging complete: "
        f"{len(staged_paths)} file(s) staged."
    )

    return staged_paths


if __name__ == "__main__":
    run_staging()