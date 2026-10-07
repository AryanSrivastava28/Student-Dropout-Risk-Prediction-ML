"""Part 2 - Model Monitoring: Drift, Quality, Performance, Latency, Failures.

Monitors the following aspects of the ML system:
  1. Input quality — missing/invalid values in prediction requests
  2. Feature drift — numerical (KS-test) and categorical (chi-square) drift
     between training data and recent prediction inputs
  3. Class distribution — predicted class balance over time
  4. Model performance — rolling accuracy/precision/recall/F1 when ground
     truth is available (via feedback)
  5. Latency — prediction response time tracking
  6. Failures — error count and rate

Metrics are written to the `ml_monitoring_metrics` table in PostgreSQL
and also to a local CSV file for offline analysis. If the database is
unavailable, monitoring silently falls back to CSV so prediction is never
broken.

Usage:
    from monitoring.drift_monitor import log_prediction, compute_drift
"""
from __future__ import annotations

import json
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import ANALYTICAL_DIR, LOGS_DIR, PROJECT_ROOT

MONITORING_CSV = LOGS_DIR / "ml_monitoring_metrics.csv"
PREDICTION_LOG_CSV = LOGS_DIR / "prediction_log.csv"
TRAINING_PROFILE_PATH = PROJECT_ROOT / "models" / "metadata" / "training_profile.json"

_recent_predictions: deque[dict] = deque(maxlen=500)


def _ensure_dirs():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _load_training_profile() -> dict:
    """Load the training data profile for drift comparison."""
    if TRAINING_PROFILE_PATH.exists():
        return json.loads(TRAINING_PROFILE_PATH.read_text())
    return {}


def save_training_profile() -> None:
    """Compute and save the training data profile (feature statistics)."""
    _ensure_dirs()
    csv_path = ANALYTICAL_DIR / "student_analytics.csv"
    if not csv_path.exists():
        return

    df = pd.read_csv(csv_path)

    numeric_cols = [
        "age", "studytime", "failures", "absences", "attendance_pct",
        "g1_grade", "g2_grade", "g3_grade", "academic_average",
        "famrel", "goout", "Dalc", "Walc", "health",
    ]
    categorical_cols = [
        "school", "sex", "schoolsup", "famsup", "higher", "internet", "subject",
    ]

    profile: dict[str, Any] = {"numeric": {}, "categorical": {}, "target_distribution": {}}

    for col in numeric_cols:
        if col in df.columns:
            profile["numeric"][col] = {
                "mean": float(df[col].mean()),
                "std": float(df[col].std()),
                "min": float(df[col].min()),
                "max": float(df[col].max()),
                "p25": float(df[col].quantile(0.25)),
                "p50": float(df[col].quantile(0.50)),
                "p75": float(df[col].quantile(0.75)),
            }

    for col in categorical_cols:
        if col in df.columns:
            profile["categorical"][col] = df[col].value_counts(normalize=True).to_dict()

    risk_dist = df["risk_category"].value_counts(normalize=True).to_dict()
    profile["target_distribution"] = risk_dist
    profile["row_count"] = len(df)
    profile["created_at"] = datetime.now(timezone.utc).isoformat()

    TRAINING_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRAINING_PROFILE_PATH.write_text(json.dumps(profile, indent=2))
    print(f"  [monitor] Training profile saved to {TRAINING_PROFILE_PATH}")


def log_prediction(
    input_features: dict,
    prediction: int,
    probability: float,
    latency_ms: float,
    error: str | None = None,
) -> None:
    """Log a prediction event for monitoring."""
    _ensure_dirs()
    _recent_predictions.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prediction": prediction,
        "probability": probability,
        "latency_ms": latency_ms,
        "error": error,
        "features": input_features,
    })

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prediction": prediction,
        "probability": round(probability, 4),
        "latency_ms": round(latency_ms, 2),
        "error": error or "",
    }
    df = pd.DataFrame([row])
    header = not PREDICTION_LOG_CSV.exists()
    df.to_csv(PREDICTION_LOG_CSV, mode="a", header=header, index=False)


def compute_drift() -> dict[str, Any]:
    """Compute feature drift between training data and recent predictions.

    Uses the Kolmogorov-Smirnov test for numeric features and a
    chi-square-like distribution comparison for categorical features.
    """
    from scipy.stats import ks_2samp

    profile = _load_training_profile()
    if not profile or not _recent_predictions:
        return {"status": "insufficient_data"}

    recent = list(_recent_predictions)
    recent_df = pd.DataFrame([r["features"] for r in recent])

    drift_results: dict[str, Any] = {"numeric": {}, "categorical": {}, "summary": {}}
    drift_detected = False

    numeric_cols = profile.get("numeric", {})
    for col, stats in numeric_cols.items():
        if col not in recent_df.columns:
            continue
        recent_vals = pd.to_numeric(recent_df[col], errors="coerce").dropna()
        if len(recent_vals) < 5:
            continue

        train_mean = stats["mean"]
        train_std = stats["std"]
        recent_mean = float(recent_vals.mean())

        mean_shift = abs(recent_mean - train_mean) / (train_std + 1e-9)

        ks_stat, ks_p = ks_2samp(
            np.random.normal(stats["mean"], stats["std"], 500),
            recent_vals.values,
        )

        is_drift = mean_shift > 0.5 or ks_p < 0.05
        if is_drift:
            drift_detected = True

        drift_results["numeric"][col] = {
            "train_mean": round(train_mean, 4),
            "recent_mean": round(recent_mean, 4),
            "mean_shift_std": round(mean_shift, 4),
            "ks_statistic": round(float(ks_stat), 4),
            "ks_p_value": round(float(ks_p), 4),
            "drift": is_drift,
        }

    categorical_cols = profile.get("categorical", {})
    for col, train_dist in categorical_cols.items():
        if col not in recent_df.columns:
            continue
        recent_dist = recent_df[col].value_counts(normalize=True).to_dict()

        all_cats = set(train_dist.keys()) | set(recent_dist.keys())
        max_diff = 0.0
        for cat in all_cats:
            t = train_dist.get(cat, 0.0)
            r = recent_dist.get(cat, 0.0)
            max_diff = max(max_diff, abs(t - r))

        is_drift = max_diff > 0.2
        if is_drift:
            drift_detected = True

        drift_results["categorical"][col] = {
            "train_distribution": train_dist,
            "recent_distribution": recent_dist,
            "max_distribution_diff": round(max_diff, 4),
            "drift": is_drift,
        }

    drift_results["summary"] = {
        "drift_detected": drift_detected,
        "num_predictions": len(recent),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return drift_results


def compute_class_distribution() -> dict[str, Any]:
    """Compute the predicted class distribution from recent predictions."""
    if not _recent_predictions:
        return {"status": "no_predictions"}

    recent = list(_recent_predictions)
    preds = [r["prediction"] for r in recent if r.get("error") is None]
    if not preds:
        return {"status": "no_valid_predictions"}

    total = len(preds)
    at_risk = sum(preds)
    low_risk = total - at_risk

    return {
        "total": total,
        "at_risk": at_risk,
        "at_risk_pct": round(at_risk / total * 100, 2),
        "low_risk": low_risk,
        "low_risk_pct": round(low_risk / total * 100, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def compute_latency_stats() -> dict[str, Any]:
    """Compute latency statistics from recent predictions."""
    if not _recent_predictions:
        return {"status": "no_predictions"}

    latencies = [r["latency_ms"] for r in _recent_predictions if r.get("latency_ms") is not None]
    if not latencies:
        return {"status": "no_latency_data"}

    return {
        "count": len(latencies),
        "mean_ms": round(float(np.mean(latencies)), 2),
        "p50_ms": round(float(np.percentile(latencies, 50)), 2),
        "p95_ms": round(float(np.percentile(latencies, 95)), 2),
        "p99_ms": round(float(np.percentile(latencies, 99)), 2),
        "max_ms": round(float(max(latencies)), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def compute_failure_stats() -> dict[str, Any]:
    """Compute failure statistics from recent predictions."""
    if not _recent_predictions:
        return {"status": "no_predictions"}

    total = len(_recent_predictions)
    errors = sum(1 for r in _recent_predictions if r.get("error") is not None)
    return {
        "total_requests": total,
        "errors": errors,
        "error_rate": round(errors / total * 100, 2) if total > 0 else 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def compute_input_quality() -> dict[str, Any]:
    """Check input quality of recent predictions for missing/invalid values."""
    if not _recent_predictions:
        return {"status": "no_predictions"}

    required_fields = [
        "age", "studytime", "failures", "absences", "attendance_pct",
        "g1_grade", "g2_grade", "g3_grade", "academic_average",
    ]
    recent = list(_recent_predictions)
    total = len(recent)
    missing_count = 0
    invalid_count = 0

    for r in recent:
        features = r.get("features", {})
        for field in required_fields:
            if field not in features or features[field] is None:
                missing_count += 1
            else:
                try:
                    val = float(features[field])
                    if val != val:
                        invalid_count += 1
                except (ValueError, TypeError):
                    invalid_count += 1

    return {
        "total_requests": total,
        "missing_values": missing_count,
        "invalid_values": invalid_count,
        "quality_score": round(
            max(0, 1 - (missing_count + invalid_count) / (total * len(required_fields))) * 100, 2
        ) if total > 0 else 100.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def compute_model_performance(y_true: list[int], y_pred: list[int]) -> dict[str, Any]:
    """Compute model performance metrics when ground truth is available."""
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
    )

    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return {"status": "insufficient_data"}

    return {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
        "sample_count": len(y_true),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def write_monitoring_metrics() -> dict[str, Any]:
    """Compute all monitoring metrics and write them to the metrics log.

    This function is called by the Airflow monitoring task and can also
    be run standalone. It never raises — monitoring must not break
    prediction.
    """
    _ensure_dirs()

    metrics: dict[str, Any] = {}
    try:
        metrics["drift"] = compute_drift()
    except Exception as e:
        metrics["drift"] = {"error": str(e)}
    try:
        metrics["class_distribution"] = compute_class_distribution()
    except Exception as e:
        metrics["class_distribution"] = {"error": str(e)}
    try:
        metrics["latency"] = compute_latency_stats()
    except Exception as e:
        metrics["latency"] = {"error": str(e)}
    try:
        metrics["failures"] = compute_failure_stats()
    except Exception as e:
        metrics["failures"] = {"error": str(e)}
    try:
        metrics["input_quality"] = compute_input_quality()
    except Exception as e:
        metrics["input_quality"] = {"error": str(e)}

    metrics["computed_at"] = datetime.now(timezone.utc).isoformat()

    row = {
        "timestamp": metrics["computed_at"],
        "drift_detected": metrics.get("drift", {}).get("summary", {}).get("drift_detected", False),
        "num_predictions": len(_recent_predictions),
        "latency_mean_ms": metrics.get("latency", {}).get("mean_ms", 0),
        "latency_p95_ms": metrics.get("latency", {}).get("p95_ms", 0),
        "error_rate": metrics.get("failures", {}).get("error_rate", 0),
        "input_quality_score": metrics.get("input_quality", {}).get("quality_score", 100),
        "at_risk_pct": metrics.get("class_distribution", {}).get("at_risk_pct", 0),
        "metrics_json": json.dumps(metrics, default=str),
    }

    df = pd.DataFrame([row])
    header = not MONITORING_CSV.exists()
    df.to_csv(MONITORING_CSV, mode="a", header=header, index=False)

    # Persist to the ml_monitoring_metrics table in PostgreSQL.
    # Falls back to CSV-only if the database is unavailable.
    try:
        from database.db_client import upsert_rows
        db_row = {
            "computed_at": row["timestamp"],
            "drift_detected": bool(row["drift_detected"]),
            "num_predictions": int(row["num_predictions"]),
            "latency_mean_ms": float(row["latency_mean_ms"]),
            "latency_p95_ms": float(row["latency_p95_ms"]),
            "error_rate": float(row["error_rate"]),
            "input_quality_score": float(row["input_quality_score"]),
            "at_risk_pct": float(row["at_risk_pct"]),
            "metrics_json": row["metrics_json"],
        }
        upsert_rows("ml_monitoring_metrics", [db_row])
        print(f"  [monitor] Metrics written to {MONITORING_CSV} and ml_monitoring_metrics table")
    except Exception as e:
        print(f"  [monitor] Metrics written to {MONITORING_CSV} (DB fallback: {e})")

    return metrics


if __name__ == "__main__":
    save_training_profile()
    write_monitoring_metrics()
    print("  [monitor] Monitoring metrics computed.")
