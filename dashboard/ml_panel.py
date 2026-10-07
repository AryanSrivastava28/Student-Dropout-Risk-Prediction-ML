"""ML Prediction panel for the Streamlit dashboard (Part 2).

This module adds an ML risk-prediction section to the existing dashboard
without modifying any Part 1 views. It loads the trained model, lets users
input student features, and shows the predicted risk with probability.

It is imported by dashboard/app.py and rendered as a new section below
the existing Part 1 views.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import ANALYTICAL_DIR, PROJECT_ROOT

MODELS_DIR = PROJECT_ROOT / "models" / "artifacts"
METADATA_DIR = PROJECT_ROOT / "models" / "metadata"


def _load_model():
    """Load the trained model and metadata."""
    import joblib

    model_path = MODELS_DIR / "best_model.joblib"
    scaler_path = MODELS_DIR / "scaler.joblib"
    meta_path = METADATA_DIR / "model_metadata.json"

    if not model_path.exists():
        return None, None, None, None

    model = joblib.load(model_path)
    scaler = None
    if scaler_path.exists() and scaler_path.stat().st_size > 0:
        scaler = joblib.load(scaler_path)

    metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    feature_names = metadata.get("feature_names", [])
    return model, scaler, feature_names, metadata


def _prepare_features(input_dict: dict, feature_names: list[str]) -> pd.DataFrame:
    """Convert input dict to the model's expected feature vector."""
    categorical = {
        "school": input_dict["school"],
        "sex": input_dict["sex"],
        "schoolsup": input_dict["schoolsup"],
        "famsup": input_dict["famsup"],
        "higher": input_dict["higher"],
        "internet": input_dict["internet"],
        "subject": input_dict["subject"],
    }
    numeric = {
        "age": input_dict["age"],
        "studytime": input_dict["studytime"],
        "failures": input_dict["failures"],
        "absences": input_dict["absences"],
        "attendance_pct": input_dict["attendance_pct"],
        "g1_grade": input_dict["g1_grade"],
        "g2_grade": input_dict["g2_grade"],
        "g3_grade": input_dict["g3_grade"],
        "academic_average": input_dict["academic_average"],
        "famrel": input_dict["famrel"],
        "goout": input_dict["goout"],
        "Dalc": input_dict["Dalc"],
        "Walc": input_dict["Walc"],
        "health": input_dict["health"],
    }

    row = dict(numeric)
    for col, val in categorical.items():
        prefix = f"{col}_"
        for fn in feature_names:
            if fn.startswith(prefix):
                expected_val = fn[len(prefix):]
                row[fn] = 1 if val == expected_val else 0

    df = pd.DataFrame([row], columns=feature_names)
    for col in feature_names:
        if col not in df.columns:
            df[col] = 0
    return df[feature_names]


def render_ml_panel(df: pd.DataFrame) -> None:
    """Render the ML prediction section in the Streamlit dashboard.

    This is called from app.py after the Part 1 views. It preserves all
    existing views and adds a new ML prediction section.
    """
    st.markdown("---")
    st.header("6. ML Risk Prediction (Part 2)")

    model, scaler, feature_names, metadata = _load_model()

    if model is None:
        st.warning(
            "No trained model found. Run `python -m models.train` to train "
            "the ML models first."
        )
        return

    model_name = metadata.get("best_model", "unknown")
    st.info(f"Production model: **{model_name}** | Trained with MLflow tracking")

    with st.expander("Model Details", expanded=False):
        st.json({
            "best_model": model_name,
            "metrics": metadata.get("metrics", {}),
            "split": metadata.get("split_ratios", {}),
            "features": len(feature_names),
        })

    st.subheader("Predict Student Risk")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        col1, col2, col3 = st.columns(3)
        with col1:
            age = st.slider("Age", 15, 22, 17, key="ml_age")
            studytime = st.slider("Study Time (1-4)", 1, 4, 2, key="ml_studytime")
            failures = st.slider("Past Failures", 0, 4, 0, key="ml_failures")
            absences = st.slider("Absences", 0, 93, 5, key="ml_absences")
        with col2:
            g1 = st.slider("G1 Grade (0-20)", 0, 20, 10, key="ml_g1")
            g2 = st.slider("G2 Grade (0-20)", 0, 20, 10, key="ml_g2")
            g3 = st.slider("G3 Grade (0-20)", 0, 20, 10, key="ml_g3")
            famrel = st.slider("Family Relationship (1-5)", 1, 5, 4, key="ml_famrel")
        with col3:
            goout = st.slider("Going Out (1-5)", 1, 5, 3, key="ml_goout")
            dalc = st.slider("Workday Alcohol (1-5)", 1, 5, 1, key="ml_dalc")
            walc = st.slider("Weekend Alcohol (1-5)", 1, 5, 1, key="ml_walc")
            health = st.slider("Health (1-5)", 1, 5, 3, key="ml_health")

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            school = st.selectbox("School", ["GP", "MS"], key="ml_school")
            sex = st.selectbox("Sex", ["F", "M"], key="ml_sex")
            schoolsup = st.selectbox("Extra School Support", ["no", "yes"], key="ml_schoolsup")
            famsup = st.selectbox("Family Support", ["yes", "no"], key="ml_famsup")
        with col_c2:
            higher = st.selectbox("Wants Higher Ed", ["yes", "no"], key="ml_higher")
            internet = st.selectbox("Internet Access", ["yes", "no"], key="ml_internet")
            subject = st.selectbox("Subject", ["Math", "Portuguese"], key="ml_subject")

    academic_average = round((g1 + g2 + g3) / 3, 2)
    attendance_pct = round(100 - (absences / 93 * 100), 2)

    input_dict = {
        "age": age, "studytime": studytime, "failures": failures,
        "absences": absences, "attendance_pct": attendance_pct,
        "g1_grade": g1, "g2_grade": g2, "g3_grade": g3,
        "academic_average": academic_average,
        "famrel": famrel, "goout": goout, "Dalc": dalc, "Walc": walc,
        "health": health, "school": school, "sex": sex,
        "schoolsup": schoolsup, "famsup": famsup, "higher": higher,
        "internet": internet, "subject": subject,
    }

    if st.button("Predict Risk", key="ml_predict_btn", type="primary"):
        import numpy as np

        X = _prepare_features(input_dict, feature_names)
        if scaler is not None:
            X_arr = scaler.transform(X.values)
        else:
            X_arr = X.values

        prediction = int(model.predict(X_arr)[0])
        if hasattr(model, "predict_proba"):
            probability = float(model.predict_proba(X_arr)[0, 1])
        else:
            probability = float(prediction)

        with col_right:
            st.markdown("### Prediction Result")
            if prediction == 1:
                st.error(f"AT RISK")
                st.metric("Risk Probability", f"{probability:.1%}")
            else:
                st.success(f"LOW RISK")
                st.metric("Risk Probability", f"{probability:.1%}")

            st.metric("Academic Average", f"{academic_average}/20")
            st.metric("Attendance", f"{attendance_pct}%")

            st.caption(f"Model: {model_name}")

    st.subheader("Batch Predictions on Current Data")

    if st.button("Run ML Predictions on All Students", key="ml_batch_btn"):
        import numpy as np

        with st.spinner("Running predictions..."):
            X_all = _prepare_batch_features(df, feature_names)
            if X_all is not None and not X_all.empty:
                if scaler is not None:
                    X_arr = scaler.transform(X_all.values)
                else:
                    X_arr = X_all.values

                preds = model.predict(X_arr)
                probas = (
                    model.predict_proba(X_arr)[:, 1]
                    if hasattr(model, "predict_proba")
                    else preds.astype(float)
                )

                result_df = df.copy()
                result_df["ml_at_risk"] = preds
                result_df["ml_risk_probability"] = probas

                st.write(f"Predictions for {len(result_df)} students:")
                pred_counts = result_df["ml_at_risk"].value_counts()
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    st.metric("Predicted At Risk", int(pred_counts.get(1, 0)))
                with col_p2:
                    st.metric("Predicted Low Risk", int(pred_counts.get(0, 0)))

                st.dataframe(
                    result_df[["student_id", "subject", "academic_average",
                              "risk_category", "ml_at_risk", "ml_risk_probability"]].head(50),
                    use_container_width=True,
                )
            else:
                st.warning("Could not prepare features from the current data.")


def _prepare_batch_features(df: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame | None:
    """Prepare features from the analytics DataFrame for batch prediction."""
    if df.empty:
        return None

    numeric_cols = [
        "age", "studytime", "failures", "absences", "attendance_pct",
        "g1_grade", "g2_grade", "g3_grade", "academic_average",
        "famrel", "goout", "dalc", "walc", "health",
    ]

    categorical_cols = [
        "school", "sex", "schoolsup", "famsup", "higher", "internet", "subject",
    ]

    df = df.copy()

    for col in numeric_cols:
        if col not in df.columns:
            return None

    rows = []

    for _, row in df.iterrows():
        r = {}

        for col in numeric_cols:
            r[col] = row[col]

        for col in categorical_cols:
            if col not in df.columns:
                continue

            val = row[col]
            prefix = f"{col}_"

            for fn in feature_names:
                if fn.startswith(prefix):
                    expected_val = fn[len(prefix):]
                    r[fn] = 1 if val == expected_val else 0

        rows.append(r)

    result = pd.DataFrame(rows)

    for col in feature_names:
        if col not in result.columns:
            result[col] = 0

    return result[feature_names]
