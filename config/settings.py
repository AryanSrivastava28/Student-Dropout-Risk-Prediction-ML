"""Central configuration for the student-performance pipeline.

All paths are resolved relative to the project root so the project is
portable across machines.  Database credentials come from environment
variables loaded via python-dotenv.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a local .env file if one is present.
load_dotenv()

# Project root: allow override via env var, otherwise use this file's location.
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[1]))

# Directory paths for each data layer.
DATA_DIR = PROJECT_ROOT / "data"
SOURCE_DIR = DATA_DIR / "source"
RAW_DIR = DATA_DIR / "raw"
STAGING_DIR = DATA_DIR / "staging"
CLEANED_DIR = DATA_DIR / "cleaned"
REJECTED_DIR = DATA_DIR / "rejected"
ANALYTICAL_DIR = DATA_DIR / "analytical"

LOGS_DIR = PROJECT_ROOT / "logs"

# Metadata log file paths.
INGESTION_METADATA_FILE = LOGS_DIR / "ingestion_metadata.csv"
VALIDATION_REPORT_FILE = LOGS_DIR / "validation_report.csv"
PIPELINE_METADATA_FILE = LOGS_DIR / "pipeline_metadata.csv"

# PostgreSQL connection parameters (read from environment).
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "student_performance")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change_me")


def postgres_connection_string() -> str:
    """Return a SQLAlchemy connection URL for the PostgreSQL warehouse."""
    return (
        f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )


def ensure_directories() -> None:
    """Create every data and log directory if it does not already exist."""
    for directory in (
        SOURCE_DIR,
        RAW_DIR,
        STAGING_DIR,
        CLEANED_DIR,
        REJECTED_DIR,
        ANALYTICAL_DIR,
        LOGS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
