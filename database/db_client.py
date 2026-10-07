"""Database client for the Supabase PostgreSQL data warehouse.

Uses the Supabase REST API (PostgREST) via urllib so no extra pip packages
are needed beyond what is in the standard library.  The connection details
are read from environment variables (VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY)
which are pre-populated in the project .env file.

For a traditional PostgreSQL deployment (e.g. a local Postgres instance),
the same schema can be loaded via ``database/schema.sql`` and the loader
can be switched to use SQLAlchemy + psycopg2 by setting the POSTGRES_*
environment variables and using ``postgres_connection_string()`` from
``config.settings``.  See the README for details.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("VITE_SUPABASE_ANON_KEY", "")


def _headers() -> dict[str, str]:
    """Return the standard headers required by the PostgREST API."""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _handle_error(error: urllib.error.HTTPError, context: str) -> None:
    """Raise a readable error from an HTTPError response."""
    body = error.read().decode("utf-8", errors="replace")[:500]
    raise RuntimeError(f"Database error during {context}: HTTP {error.code} - {body}")


def upsert_rows(
    table: str,
    rows: list[dict[str, Any]],
    on_conflict: str = "",
    batch_size: int = 500,
) -> int:
    """Upsert rows into a table via the REST API.

    Args:
        table: target table name.
        rows: list of row dictionaries to insert/update.
        on_conflict: comma-separated column names for the conflict target
                     (e.g. "student_id" or "student_id,subject").  If empty,
                     rows are inserted without upsert semantics.
        batch_size: number of rows per API call (PostgREST limit is ~1000).

    Returns the total number of rows upserted.
    """
    if not rows:
        return 0

    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        headers = _headers()
        if on_conflict:
            headers["Prefer"] = f"return=representation,resolution=merge-duplicates"
            url += f"?on_conflict={on_conflict}"

        payload = json.dumps(batch).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            total += len(batch)
        except urllib.error.HTTPError as exc:
            _handle_error(exc, f"upsert into {table}")
    return total


def fetch_all(table: str, columns: str = "*", filters: str = "", page_size: int = 1000) -> list[dict]:
    """Fetch all rows from a table via the REST API with pagination.

    PostgREST returns at most `page_size` rows per request (default 1000).
    This function paginates using Range headers to retrieve every row.

    Args:
        table: table name.
        columns: comma-separated column names (default "*").
        filters: optional query string starting with "&" (e.g. "&risk_category=eq.High Risk").
        page_size: number of rows per API call.

    Returns a list of row dictionaries.
    """
    all_rows: list[dict] = []
    offset = 0

    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={columns}"
        if filters:
            url += filters

        headers = _headers()
        # Range header: request rows offset to offset+page_size-1 (inclusive).
        headers["Range"] = f"{offset}-{offset + page_size - 1}"
        # Ask for a count so we know when to stop.
        headers["Prefer"] = "count=exact"

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            batch = json.loads(resp.read())
            all_rows.extend(batch)
            # Check Content-Range header for total count.
            content_range = resp.headers.get("Content-Range", "")
            # Format: "offset-end/total" or "offset-end/*"
            if "/" in content_range:
                total_str = content_range.split("/")[-1]
                if total_str != "*":
                    total = int(total_str)
                    if offset + len(batch) >= total:
                        break
                else:
                    # Unknown total — stop if we got fewer than page_size.
                    if len(batch) < page_size:
                        break
            offset += page_size
        except urllib.error.HTTPError as exc:
            _handle_error(exc, f"fetch from {table}")
            return all_rows
    return all_rows


def delete_all(table: str) -> int:
    """Delete all rows from a table (used for re-running the pipeline).

    Returns the number of rows deleted.
    """
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = _headers()
    headers["Prefer"] = "return=representation"

    req = urllib.request.Request(url, headers=headers, method="DELETE")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        deleted = json.loads(resp.read())
        return len(deleted) if isinstance(deleted, list) else 0
    except urllib.error.HTTPError as exc:
        _handle_error(exc, f"delete from {table}")
        return 0


def test_connection() -> bool:
    """Return True if the database connection is working."""
    try:
        result = fetch_all("dim_subject", "subject_name")
        return len(result) > 0
    except Exception:
        return False
