"""Stage 1 - Data Ingestion and Raw Layer.

This module reads CSV files from ``data/source/`` and copies them, untouched,
into ``data/raw/``.  For every ingestion attempt (success or failure) a row is
appended to ``logs/ingestion_metadata.csv`` with the following columns:

    source_name, source_file_name, extraction_timestamp,
    ingestion_status, row_count, column_count,
    output_raw_file, error_message

The ingestion is fault-tolerant: if one source file fails, the error is logged
and processing continues with the next available source.
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config.settings import (
    INGESTION_METADATA_FILE,
    LOGS_DIR,
    RAW_DIR,
    SOURCE_DIR,
    ensure_directories,
)

# Columns written to the ingestion metadata log.
METADATA_COLUMNS = [
    "source_name",
    "source_file_name",
    "extraction_timestamp",
    "ingestion_status",
    "row_count",
    "column_count",
    "output_raw_file",
    "error_message",
]


def _discover_source_files() -> list[Path]:
    """Return a sorted list of CSV files in the source directory."""
    if not SOURCE_DIR.exists():
        return []
    return sorted(SOURCE_DIR.glob("*.csv"))


def _append_metadata(record: dict) -> None:
    """Append a single metadata record to the ingestion metadata CSV."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([record], columns=METADATA_COLUMNS)
    write_header = not INGESTION_METADATA_FILE.exists()
    df.to_csv(INGESTION_METADATA_FILE, mode="a", header=write_header, index=False)


def ingest_single_file(source_path: Path) -> dict:
    """Ingest one CSV file: read it with pandas, copy it raw, log metadata.

    Returns the metadata record dictionary.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    source_name = source_path.stem  # e.g. "student-mat"
    raw_file_name = f"{source_name}.csv"
    raw_path = RAW_DIR / raw_file_name

    record: dict = {
        "source_name": source_name,
        "source_file_name": source_path.name,
        "extraction_timestamp": timestamp,
        "ingestion_status": "failed",
        "row_count": 0,
        "column_count": 0,
        "output_raw_file": "",
        "error_message": "",
    }

    try:
        print(f"  [ingest] Reading {source_path.name} ...")
        # Read with semicolon separator (UCI student dataset uses ';').
        df = pd.read_csv(source_path, sep=";")

        # Preserve an untouched raw copy - copy the file directly so the raw
        # layer is byte-for-byte identical to the source.
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, raw_path)

        record.update(
            ingestion_status="success",
            row_count=len(df),
            column_count=len(df.columns),
            output_raw_file=str(raw_path.relative_to(Path.cwd()))
            if raw_path.is_absolute() and str(Path.cwd()) in str(raw_path)
            else str(raw_path),
        )
        print(
            f"  [ingest] OK  {source_path.name} -> "
            f"{record['row_count']} rows, {record['column_count']} columns"
        )
    except Exception as exc:  # noqa: BLE001
        record["error_message"] = str(exc)
        print(f"  [ingest] FAIL {source_path.name}: {exc}")

    _append_metadata(record)
    return record


def run_ingestion() -> list[dict]:
    """Ingest all CSV files found in ``data/source/``.

    Returns the list of metadata records (one per source file).
    """
    ensure_directories()
    print("=== Stage 1: Data Ingestion ===")
    source_files = _discover_source_files()

    if not source_files:
        print("  [ingest] No CSV files found in data/source/")
        return []

    print(f"  [ingest] Found {len(source_files)} source file(s):")
    for f in source_files:
        print(f"         - {f.name}")

    results = []
    for source_path in source_files:
        results.append(ingest_single_file(source_path))

    successes = sum(1 for r in results if r["ingestion_status"] == "success")
    failures = sum(1 for r in results if r["ingestion_status"] == "failed")
    print(f"  [ingest] Ingestion complete: {successes} succeeded, {failures} failed")
    print(f"  [ingest] Metadata log: {INGESTION_METADATA_FILE}")
    return results


if __name__ == "__main__":
    run_ingestion()
