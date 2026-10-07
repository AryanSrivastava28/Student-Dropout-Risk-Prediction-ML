"""FastAPI Prediction API for Student Dropout-Risk Prediction.

Serves predictions from the trained production model. The API loads the
best model artifact (joblib) and its metadata, accepts student feature
inputs, validates them, and returns a risk prediction with probability.

Endpoints:
  GET  /           - Health check
  GET  /model-info  - Model metadata
  POST /predict     - Single prediction
  POST /predict-batch - Batch predictions

Usage:
    uvicorn api.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import ANALYTICAL_DIR, PROJECT_ROOT
from monitoring.drift_monitor import log_prediction

MODELS_DIR = PROJECT_ROOT / "models" / "artifacts"
METADATA_DIR = PROJECT_ROOT / "models" / "metadata"

app = FastAPI(
    title="Student Dropout-Risk Prediction API",
    description="Part 2 - ML model serving for student risk prediction",
    version="1.0.0",
)


def _load_model():
    """Load the best model, scaler, and metadata from disk."""
    model_path = MODELS_DIR / "best_model.joblib"
    scaler_path = MODELS_DIR / "scaler.joblib"
    meta_path = METADATA_DIR / "model_metadata.json"

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found at {model_path}. Run training first: python -m models.train"
        )

    model = joblib.load(model_path)
    scaler = None
    if scaler_path.exists() and scaler_path.stat().st_size > 0:
        scaler = joblib.load(scaler_path)

    metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    feature_names = metadata.get("feature_names", [])
    return model, scaler, feature_names, metadata


_model, _scaler, _feature_names, _model_metadata = _load_model()


class StudentInput(BaseModel):
    """Input schema for a single student prediction request."""
    age: int = Field(..., ge=15, le=22, description="Student age (15-22)")
    studytime: int = Field(..., ge=1, le=4, description="Weekly study time (1-4)")
    failures: int = Field(..., ge=0, le=4, description="Past class failures (0-4)")
    absences: int = Field(..., ge=0, le=93, description="Number of absences (0-93)")
    attendance_pct: float = Field(..., ge=0, le=100, description="Attendance percentage")
    g1_grade: int = Field(..., ge=0, le=20, description="First period grade (0-20)")
    g2_grade: int = Field(..., ge=0, le=20, description="Second period grade (0-20)")
    g3_grade: int = Field(..., ge=0, le=20, description="Final grade (0-20)")
    academic_average: float = Field(..., ge=0, le=20, description="Mean of G1, G2, G3")
    famrel: int = Field(..., ge=1, le=5, description="Family relationship quality (1-5)")
    goout: int = Field(..., ge=1, le=5, description="Going out frequency (1-5)")
    Dalc: int = Field(..., ge=1, le=5, description="Workday alcohol consumption (1-5)")
    Walc: int = Field(..., ge=1, le=5, description="Weekend alcohol consumption (1-5)")
    health: int = Field(..., ge=1, le=5, description="Health status (1-5)")
    school: str = Field(..., description="School (GP or MS)")
    sex: str = Field(..., description="Sex (F or M)")
    schoolsup: str = Field(..., description="Extra educational support (yes/no)")
    famsup: str = Field(..., description="Family educational support (yes/no)")
    higher: str = Field(..., description="Wants higher education (yes/no)")
    internet: str = Field(..., description="Internet access at home (yes/no)")
    subject: str = Field(..., description="Subject (Math or Portuguese)")


class BatchInput(BaseModel):
    """Input schema for batch predictions."""
    students: list[StudentInput]


class PredictionResponse(BaseModel):
    """Response schema for a single prediction."""
    at_risk: bool
    risk_probability: float
    risk_label: str
    model_name: str
    latency_ms: float


class BatchPredictionResponse(BaseModel):
    """Response schema for batch predictions."""
    predictions: list[PredictionResponse]


def _prepare_features(student: StudentInput) -> pd.DataFrame:
    """Convert a StudentInput into the feature vector expected by the model."""
    raw = student.model_dump()

    categorical = {
        "school": raw["school"],
        "sex": raw["sex"],
        "schoolsup": raw["schoolsup"],
        "famsup": raw["famsup"],
        "higher": raw["higher"],
        "internet": raw["internet"],
        "subject": raw["subject"],
    }
    numeric = {
        "age": raw["age"],
        "studytime": raw["studytime"],
        "failures": raw["failures"],
        "absences": raw["absences"],
        "attendance_pct": raw["attendance_pct"],
        "g1_grade": raw["g1_grade"],
        "g2_grade": raw["g2_grade"],
        "g3_grade": raw["g3_grade"],
        "academic_average": raw["academic_average"],
        "famrel": raw["famrel"],
        "goout": raw["goout"],
        "Dalc": raw["Dalc"],
        "Walc": raw["Walc"],
        "health": raw["health"],
    }

    row = dict(numeric)
    for col, val in categorical.items():
        prefix = f"{col}_"
        for fn in _feature_names:
            if fn.startswith(prefix):
                expected_val = fn[len(prefix):]
                row[fn] = 1 if val == expected_val else 0

    df = pd.DataFrame([row], columns=_feature_names)
    for col in _feature_names:
        if col not in df.columns:
            df[col] = 0
    return df[_feature_names]


@app.get("/")
def health():
    """Health check endpoint."""
    return {"status": "healthy", "model": _model_metadata.get("best_model", "unknown")}


@app.get("/model-info")
def model_info():
    """Return model metadata."""
    return _model_metadata


@app.post("/predict", response_model=PredictionResponse)
def predict(student: StudentInput):
    """Predict dropout risk for a single student."""
    start = time.time()
    try:
        X = _prepare_features(student)

        if _scaler is not None:
            X_arr = _scaler.transform(X.values)
        else:
            X_arr = X.values

        prediction = int(_model.predict(X_arr)[0])
        if hasattr(_model, "predict_proba"):
            probability = float(_model.predict_proba(X_arr)[0, 1])
        else:
            probability = float(prediction)

        latency = (time.time() - start) * 1000

        risk_label = "At Risk" if prediction == 1 else "Low Risk"

        try:
            log_prediction(student.model_dump(), prediction, probability, latency)
        except Exception:
            pass

        return PredictionResponse(
            at_risk=bool(prediction),
            risk_probability=round(probability, 4),
            risk_label=risk_label,
            model_name=_model_metadata.get("best_model", "unknown"),
            latency_ms=round(latency, 2),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/predict-batch", response_model=BatchPredictionResponse)
def predict_batch(batch: BatchInput):
    """Predict dropout risk for multiple students."""
    results = []
    for student in batch.students:
        start = time.time()
        try:
            X = _prepare_features(student)
            if _scaler is not None:
                X_arr = _scaler.transform(X.values)
            else:
                X_arr = X.values

            prediction = int(_model.predict(X_arr)[0])
            if hasattr(_model, "predict_proba"):
                probability = float(_model.predict_proba(X_arr)[0, 1])
            else:
                probability = float(prediction)

            latency = (time.time() - start) * 1000
            risk_label = "At Risk" if prediction == 1 else "Low Risk"

            try:
                log_prediction(student.model_dump(), prediction, probability, latency)
            except Exception:
                pass

            results.append(PredictionResponse(
                at_risk=bool(prediction),
                risk_probability=round(probability, 4),
                risk_label=risk_label,
                model_name=_model_metadata.get("best_model", "unknown"),
                latency_ms=round(latency, 2),
            ))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
    return BatchPredictionResponse(predictions=results)
