"""Part 2 - ML Model Training with MLflow Tracking.

Trains and evaluates three models for student dropout-risk prediction:
  1. Logistic Regression (baseline)
  2. Random Forest (advanced)
  3. XGBoost (advanced)

Target: binary classification — at_risk (1 if risk_category is "High Risk"
         or "Medium Risk", 0 if "Low Risk").

Split strategy: train / validation / test with stratification on the target.
  - Test set is held out completely (no leakage).
  - Validation set is used for model selection.
  - A fixed random_state ensures reproducibility.

MLflow tracks experiments, parameters, metrics, and artifacts. The
selected production model is registered in the MLflow Model Registry.

Usage:
    python -m models.train
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import ANALYTICAL_DIR, PROJECT_ROOT

MODELS_DIR = PROJECT_ROOT / "models" / "artifacts"
MLRUNS_DIR = PROJECT_ROOT / "mlruns"
MLFLOW_DB = PROJECT_ROOT / "mlflow.db"
METADATA_DIR = PROJECT_ROOT / "models" / "metadata"

RANDOM_STATE = 42

FEATURE_COLUMNS = [
    "age", "studytime", "failures", "absences", "attendance_pct",
    "g1_grade", "g2_grade", "g3_grade", "academic_average",
    "famrel", "goout", "Dalc", "Walc", "health",
]
CATEGORICAL_COLUMNS = [
    "school", "sex", "schoolsup", "famsup", "higher", "internet", "subject",
]


def load_analytics_data() -> pd.DataFrame:
    """Load the analytical dataset used for training."""
    csv_path = ANALYTICAL_DIR / "student_analytics.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Analytical dataset not found at {csv_path}. "
            "Run the Part 1 pipeline first."
        )
    df = pd.read_csv(csv_path)
    return df


def define_target(df: pd.DataFrame) -> pd.DataFrame:
    """Define the binary risk prediction target.

    at_risk = 1 if the student is "High Risk" or "Medium Risk", else 0.
    This recasts the 3-class rule-based label into a binary dropout-risk
    prediction target suitable for classification.
    """
    df = df.copy()
    df["at_risk"] = (df["risk_category"].isin(["High Risk", "Medium Risk"])).astype(int)
    return df


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Select and encode features for model training."""
    df = df.copy()

    # One-hot encode categorical features.
    for col in CATEGORICAL_COLUMNS:
        if col in df.columns:
            dummies = pd.get_dummies(df[col], prefix=col, drop_first=True)
            df = pd.concat([df, dummies], axis=1)

    # Build the final feature set: numeric + encoded categoricals.
    encoded_cols = []
    for col in CATEGORICAL_COLUMNS:
        if col in df.columns:
            df.drop(columns=[col], inplace=True)
        encoded_cols.extend(
            [c for c in df.columns if c.startswith(col + "_")]
        )

    feature_cols = FEATURE_COLUMNS + encoded_cols
    # Keep only columns that exist.
    feature_cols = [c for c in feature_cols if c in df.columns]
    return df[feature_cols]


def make_split(
    X: pd.DataFrame, y: pd.Series
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """Create a reproducible train / validation / test split.

    60% train, 20% validation, 20% test — stratified on the target.
    The test set is never used during training or model selection.
    """
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_STATE, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=0.25, random_state=RANDOM_STATE, stratify=y_temp
    )
    return X_train, X_val, X_test, y_train, y_val, y_test


def train_and_log(
    name: str,
    model,
    X_train, X_val, X_test,
    y_train, y_val, y_test,
    scaler: StandardScaler | None = None,
) -> dict:
    """Train a model, evaluate it, and log everything to MLflow."""
    mlflow.start_run(run_name=name) if mlflow.active_run() is None else None

    if scaler is not None:
        X_train_f = scaler.fit_transform(X_train)
        X_val_f = scaler.transform(X_val)
        X_test_f = scaler.transform(X_test)
    else:
        X_train_f = X_train.values
        X_val_f = X_val.values
        X_test_f = X_test.values

    model.fit(X_train_f, y_train)

    y_val_pred = model.predict(X_val_f)
    y_test_pred = model.predict(X_test_f)

    val_proba = (
        model.predict_proba(X_val_f)[:, 1]
        if hasattr(model, "predict_proba")
        else y_val_pred
    )
    test_proba = (
        model.predict_proba(X_test_f)[:, 1]
        if hasattr(model, "predict_proba")
        else y_test_pred
    )

    val_f1 = f1_score(y_val, y_val_pred, zero_division=0)
    test_f1 = f1_score(y_test, y_test_pred, zero_division=0)
    val_auc = roc_auc_score(y_val, val_proba) if len(np.unique(y_val)) > 1 else 0.0
    test_auc = roc_auc_score(y_test, test_proba) if len(np.unique(y_test)) > 1 else 0.0

    metrics = {
        "val_accuracy": accuracy_score(y_val, y_val_pred),
        "val_precision": precision_score(y_val, y_val_pred, zero_division=0),
        "val_recall": recall_score(y_val, y_val_pred, zero_division=0),
        "val_f1": val_f1,
        "val_auc": val_auc,
        "test_accuracy": accuracy_score(y_test, y_test_pred),
        "test_precision": precision_score(y_test, y_test_pred, zero_division=0),
        "test_recall": recall_score(y_test, y_test_pred, zero_division=0),
        "test_f1": test_f1,
        "test_auc": test_auc,
    }

    mlflow.log_params({"model": name, "random_state": RANDOM_STATE})
    if hasattr(model, "get_params"):
        params = model.get_params()
        for k, v in params.items():
            mlflow.log_param(f"param_{k}", v)

    mlflow.log_metrics(metrics)

    report = classification_report(
        y_test, y_test_pred, zero_division=0, output_dict=True
    )
    report_path = METADATA_DIR / f"{name}_classification_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    trusted = ["xgboost.core.Booster", "xgboost.sklearn.XGBClassifier"]
    mlflow.sklearn.log_model(
        model, artifact_path="model", skops_trusted_types=trusted
    )

    run_id = mlflow.active_run().info.run_id

    print(f"  [{name}] val_f1={val_f1:.4f}  test_f1={test_f1:.4f}  test_auc={test_auc:.4f}")
    return {"model": model, "scaler": scaler, "metrics": metrics, "name": name, "run_id": run_id}


def train_all() -> dict:
    """Train all three models, log to MLflow, and return results."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    MLRUNS_DIR.mkdir(parents=True, exist_ok=True)

    mlflow.set_tracking_uri(f"sqlite:///{MLFLOW_DB}")
    mlflow.set_experiment("student_risk_prediction")

    df = load_analytics_data()
    df = define_target(df)

    print(f"  [train] Dataset shape: {df.shape}")
    print(f"  [train] Target distribution:\n{df['at_risk'].value_counts()}")

    X = prepare_features(df)
    y = df["at_risk"]

    feature_names = list(X.columns)
    (METADATA_DIR / "feature_names.json").write_text(
        json.dumps(feature_names, indent=2)
    )

    X_train, X_val, X_test, y_train, y_val, y_test = make_split(X, y)
    print(f"  [train] Split: train={len(X_train)} val={len(X_val)} test={len(X_test)}")

    results = {}

    # 1. Logistic Regression (baseline) — scaled features.
    with mlflow.start_run(run_name="logistic_regression"):
        scaler = StandardScaler()
        lr = LogisticRegression(
            max_iter=1000, random_state=RANDOM_STATE, solver="lbfgs"
        )
        results["logistic_regression"] = train_and_log(
            "logistic_regression", lr, X_train, X_val, X_test,
            y_train, y_val, y_test, scaler=scaler,
        )

    # 2. Random Forest (advanced) — no scaling needed.
    with mlflow.start_run(run_name="random_forest"):
        rf = RandomForestClassifier(
            n_estimators=200, max_depth=10, random_state=RANDOM_STATE,
            class_weight="balanced",
        )
        results["random_forest"] = train_and_log(
            "random_forest", rf, X_train, X_val, X_test,
            y_train, y_val, y_test, scaler=None,
        )

    # 3. XGBoost (advanced) — no scaling needed.
    with mlflow.start_run(run_name="xgboost"):
        xgb = XGBClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.1,
            random_state=RANDOM_STATE, eval_metric="logloss",
        )
        results["xgboost"] = train_and_log(
            "xgboost", xgb, X_train, X_val, X_test,
            y_train, y_val, y_test, scaler=None,
        )

    # Select the best model by validation F1.
    best_name = max(results, key=lambda k: results[k]["metrics"]["val_f1"])
    best = results[best_name]
    print(f"\n  [train] Best model: {best_name} (val_f1={best['metrics']['val_f1']:.4f})")

    # Save the best model and scaler as a joblib artifact.
    model_path = MODELS_DIR / "best_model.joblib"
    scaler_path = MODELS_DIR / "scaler.joblib"
    joblib.dump(best["model"], model_path)
    if best["scaler"] is not None:
        joblib.dump(best["scaler"], scaler_path)
    else:
        scaler_path.write_bytes(b"")

    # Register the best model in the MLflow Model Registry.
    mlflow.register_model(
        model_uri=f"runs:/{best['run_id']}/model",
        name="student_risk_model",
        tags={"model_type": best_name, "stage": "production"},
    )

    # Save model metadata for Git-based versioning.
    metadata = {
        "best_model": best_name,
        "feature_names": feature_names,
        "random_state": RANDOM_STATE,
        "split_ratios": {"train": 0.60, "validation": 0.20, "test": 0.20},
        "metrics": best["metrics"],
        "dataset_rows": len(df),
        "dataset_path": str(ANALYTICAL_DIR / "student_analytics.csv"),
        "model_path": str(model_path),
        "scaler_path": str(scaler_path) if best["scaler"] is not None else None,
    }
    meta_path = METADATA_DIR / "model_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2))
    print(f"  [train] Metadata saved to {meta_path}")

    return results


if __name__ == "__main__":
    print("=" * 60)
    print("Part 2 - ML Model Training")
    print("=" * 60)
    train_all()
    print("=" * 60)
    print("Training complete!")
