# Model Lifecycle and Retraining Criteria

## Overview

This document describes the ML model lifecycle for the Student Dropout-Risk
Prediction system (Part 2), including training, evaluation, registration,
serving, monitoring, and retraining criteria.

## Model Lifecycle Stages

```
Training → Evaluation → Registration (MLflow) → Serving (FastAPI)
    ↑                                                    ↓
    └──── Retraining ← Monitoring ← Drift Detection ←────┘
```

### 1. Training

- **Models**: Logistic Regression (baseline), Random Forest, XGBoost (advanced)
- **Data**: `data/analytical/student_analytics.csv` (1032 rows, 25 columns)
- **Target**: `at_risk` (binary: 1 = High/Medium Risk, 0 = Low Risk)
- **Split**: 60% train / 20% validation / 20% test (stratified, random_state=42)
- **Features**: 14 numeric + 7 one-hot encoded categorical = 21 features

### 2. Evaluation

Models are evaluated on the held-out test set using:
- Accuracy
- Precision
- Recall
- F1-score
- ROC-AUC

The best model is selected by validation F1-score. The current production
model is **XGBoost** (val_f1=0.9565, test_f1=0.9444, test_auc=0.9967).

### 3. Registration (MLflow Model Registry)

The best model is registered in the MLflow Model Registry with:
- Model name: `student_risk_model`
- Tags: `model_type`, `stage=production`
- Version: incremented on each training run

To view registered models:
```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

### 4. Serving (FastAPI)

The production model is served via FastAPI at `http://localhost:8000`:
- `POST /predict` — single student prediction
- `POST /predict-batch` — batch predictions
- `GET /model-info` — model metadata

The API loads the joblib model artifact from `models/artifacts/best_model.joblib`.

### 5. Monitoring

Monitoring tracks six aspects (see `monitoring/drift_monitor.py`):

| Metric | Description | Threshold |
|--------|-------------|-----------|
| Input quality | Missing/invalid values | quality_score < 95% |
| Feature drift (numeric) | KS-test, mean shift > 0.5 std | p < 0.05 |
| Feature drift (categorical) | Distribution diff > 0.2 | diff > 0.2 |
| Class distribution | Predicted class balance | at_risk% change > 15% |
| Model performance | F1-score on feedback data | F1 < 0.85 |
| Latency | p95 response time | p95 > 100ms |
| Failures | Error rate | error_rate > 5% |

### 6. Retraining Criteria

Retraining is triggered when any of the following conditions are met:

1. **Feature drift**: Significant drift detected in more than 2 features
   (KS-test p < 0.05 or categorical distribution diff > 0.2)
2. **Performance degradation**: Model F1-score drops below 0.85 on new
   labeled data (when ground truth becomes available)
3. **Class distribution shift**: Predicted at-risk percentage changes by
   more than 15 percentage points from the training distribution
4. **Data pipeline update**: The analytical dataset is regenerated with
   new data (new school year, additional features, etc.)
5. **Scheduled retraining**: Quarterly (every 3 months) as a preventive
   measure, regardless of drift detection

### 7. Retraining Process

1. Run `python -m models.train` to retrain all models on the current dataset
2. Compare new model metrics with the current production model
3. If the new model's validation F1 is better, register it as a new version
   in MLflow
4. Update `models/metadata/model_metadata.json` with the new model info
5. Restart the FastAPI server to load the new model artifact
6. Reset the monitoring prediction log

### 8. Rollback

If a new model performs poorly in production:
1. Load the previous model version from MLflow registry
2. Replace `models/artifacts/best_model.joblib` with the previous artifact
3. Restart the FastAPI server
4. Investigate the cause (data quality, drift, training bug)

## Git-Based Versioning

Since DVC is not used, versioning is handled via Git-tracked metadata files:

- `models/metadata/model_metadata.json` — model name, features, metrics,
  split info, artifact paths
- `models/metadata/dataset_metadata.json` — dataset SHA256, row/column
  counts, target distribution, feature columns
- `models/metadata/training_profile.json` — training data statistics for
  drift comparison

These files provide full reproducibility: any Git commit can reproduce the
exact dataset, model, and evaluation results.
