# Student Performance and Dropout-Risk Prediction

## Project Overview

This project is a data-driven academic analytics system that processes
student academic records from the UCI Student Performance dataset, creates
reliable analytical datasets, and trains machine learning models for
dropout/performance-risk prediction.

**Part 1** covers the complete data engineering pipeline: data ingestion,
staging, validation, cleaning, feature engineering, PostgreSQL data
warehousing, Apache Airflow orchestration, and a Streamlit dashboard with
interactive analytics.

**Part 2** covers the MLOps pipeline: ML model training (Logistic
Regression, Random Forest, XGBoost), MLflow experiment tracking and model
registry, Git-based dataset/model versioning, FastAPI model serving,
Docker containerization, Streamlit ML prediction integration, and
comprehensive monitoring (input quality, feature drift, class distribution,
model performance, latency, and failures).

## Features

### Part 1 — Data Engineering
- **Reproducible data ingestion** from CSV source files with metadata logging
- **Multi-layer data architecture**: raw, staging, cleaned, rejected, analytical
- **Data quality validation** with 7 validation rules and a validation report
- **Rejected records tracking** with rejection reasons and timestamps
- **Feature engineering** with academic average, attendance percentage, pass/fail
- **Rule-based risk categorization** (Low / Medium / High Risk)
- **PostgreSQL data warehouse** with star-schema-inspired design
- **Apache Airflow DAG** for automated pipeline orchestration
- **Interactive Streamlit dashboard** with 5+ views and sidebar filters
- **Comprehensive documentation** including data dictionary and architecture

### Part 2 — MLOps
- **ML risk prediction target**: binary classification (at_risk vs low_risk)
- **Three models trained and evaluated**: Logistic Regression (baseline),
  Random Forest, XGBoost (advanced)
- **Reproducible train/validation/test split** (60/20/20) with stratification
  and no data leakage
- **MLflow tracking**: experiments, parameters, metrics, and artifacts logged
- **Model registry**: best model (XGBoost) registered as production model
- **Git-based dataset/model versioning**: metadata files with SHA256 hashes,
  feature names, split info, and metrics (DVC not used — assignment allows
  Git-based metadata as an alternative)
- **FastAPI prediction API**: single and batch prediction endpoints with
  Pydantic input validation
- **Docker containerization**: Dockerfile for the FastAPI API
- **Streamlit ML integration**: interactive prediction panel added to the
  existing dashboard without modifying Part 1 views
- **Monitoring**: input quality, feature drift (numerical + categorical),
  class distribution, model performance, latency, and failure tracking
- **Airflow Part 2 tasks**: ML training, training profile, and monitoring
  tasks added to the existing DAG with correct dependencies
- **Model lifecycle and retraining criteria** documented

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3 |
| Data Processing | Pandas, NumPy |
| Database | PostgreSQL (via Supabase) |
| Database Access | REST API (urllib) / SQLAlchemy + psycopg2 |
| Orchestration | Apache Airflow |
| Dashboard | Streamlit |
| Visualization | Plotly |
| ML Models | scikit-learn, XGBoost |
| Experiment Tracking | MLflow |
| Model Serving | FastAPI |
| Containerization | Docker |
| Configuration | python-dotenv |

## Project Structure

```
student-performance-project/
│
├── data/
│   ├── source/              # Original UCI CSV files (input)
│   ├── raw/                 # Untouched copies of source files
│   ├── staging/             # Standardized columns + student_id
│   ├── cleaned/             # Validated + cleaned records
│   ├── rejected/            # Invalid records with rejection reasons
│   └── analytical/          # Feature-engineered analytical dataset
│
├── ingestion/
│   ├── __init__.py
│   └── ingest_data.py       # Stage 1: CSV ingestion + raw copies
│
├── transformation/
│   ├── __init__.py
│   ├── stage_data.py        # Stage 2: Standardize + add student_id
│   ├── validate_data.py     # Stage 3: Validation + rejected records
│   ├── clean_data.py        # Stage 5: Cleaning + deduplication
│   └── create_analytics.py  # Stage 6: Feature engineering + risk
│
├── database/
│   ├── __init__.py
│   ├── schema.sql           # PostgreSQL schema (reference)
│   ├── db_client.py         # REST API database client
│   └── load_data.py         # Stage 7: Load into PostgreSQL
│
├── models/                  # Part 2: ML training + artifacts
│   ├── __init__.py
│   ├── train.py             # ML training (LR, RF, XGBoost) + MLflow
│   ├── artifacts/           # Saved model + scaler (joblib)
│   └── metadata/            # Model + dataset metadata (Git-based versioning)
│
├── api/                     # Part 2: FastAPI model serving
│   ├── __init__.py
│   └── main.py              # Prediction API endpoints
│
├── monitoring/              # Part 2: ML monitoring
│   ├── __init__.py
│   └── drift_monitor.py     # Drift, quality, latency, failure monitoring
│
├── dashboard/
│   ├── app.py               # Streamlit dashboard (Part 1 + Part 2 ML panel)
│   └── ml_panel.py          # Part 2: ML prediction panel
│
├── airflow/
│   └── dags/
│       └── student_performance_pipeline.py  # Part 1 + Part 2 DAG
│
├── logs/                    # Ingestion + validation + ML monitoring metadata
│
├── docs/
│   ├── dataset_source.md    # Dataset documentation
│   ├── data_dictionary.md   # Column descriptions
│   ├── validation_rules.md  # Validation + cleaning rules
│   ├── architecture.md      # Architecture with Mermaid diagram
│   ├── mlops_lifecycle.md   # Part 2: Model lifecycle + retraining criteria
│   └── uci_student_dataset_description.txt
│
├── config/
│   ├── __init__.py
│   └── settings.py          # Central configuration + paths
│
├── run_pipeline.py          # End-to-end Part 1 pipeline runner
├── Dockerfile               # Part 2: Containerize the FastAPI API
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── .gitignore
└── README.md
```

## Dataset Setup

This project uses the **UCI Student Performance Dataset**.

1. Download from: https://archive.ics.uci.edu/dataset/320/student+performance
2. Extract the ZIP file
3. Copy the two CSV files to `data/source/`:
   - `student-mat.csv` (Math course, 395 records)
   - `student-por.csv` (Portuguese course, 649 records)

The dataset files are already included in `data/source/` in this project.

See `docs/dataset_source.md` for full dataset documentation.

## Environment Setup

### Python Installation

This project requires Python 3.10 or later. Verify your installation:

```bash
python3 --version
```

If Python is not installed, download it from https://www.python.org/downloads/

### Virtual Environment Creation

```bash
# Create a virtual environment
python3 -m venv venv

# Activate it (Linux/macOS)
source venv/bin/activate

# Activate it (Windows)
venv\Scripts\activate
```

### Package Installation

```bash
pip install -r requirements.txt
```

### PostgreSQL Setup

This project uses a pre-provisioned Supabase PostgreSQL database. The
connection details are in the `.env` file. No manual database setup is required.

For a local PostgreSQL setup (optional alternative):
1. Install PostgreSQL from https://www.postgresql.org/download/
2. Create a database: `CREATE DATABASE student_performance;`
3. Run the schema: `psql -d student_performance -f database/schema.sql`
4. Set the POSTGRES_* environment variables in `.env`

### Environment Variable Setup

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

The `.env` file should contain:
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=student_performance
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Part 2 - MLflow tracking
MLFLOW_TRACKING_URI=sqlite:///mlflow.db

# Part 2 - FastAPI
API_HOST=0.0.0.0
API_PORT=8000
```

## Pipeline Execution

### Running the Full Part 1 Pipeline

```bash
python run_pipeline.py
```

This runs all Part 1 stages in sequence:
1. Ingestion (source -> raw)
2. Staging (raw -> staging)
3. Validation (staging -> valid + rejected)
4. Cleaning (valid -> cleaned)
5. Analytics (cleaned -> analytical)
6. Database loading (cleaned + analytical -> PostgreSQL)

### Running Individual Part 1 Stages

```bash
# Stage 1: Ingestion
python -m ingestion.ingest_data

# Stage 2: Staging
python -m transformation.stage_data

# Stages 3-6: Validation -> Cleaning -> Analytics
python -m transformation.create_analytics

# Stage 7: Database loading
python -m database.load_data
```

## Part 2: ML Model Training

### Training the Models

```bash
python -m models.train
```

This trains three models (Logistic Regression, Random Forest, XGBoost),
logs all experiments to MLflow, evaluates on the held-out test set, and
registers the best model in the MLflow Model Registry.

### MLflow Tracking

MLflow uses a local SQLite backend (`sqlite:///mlflow.db`). To view the
MLflow UI:

```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db --host 0.0.0.0 --port 5000
```

Open http://localhost:5000 to view experiments, runs, metrics, and the
model registry.

### Model and Dataset Versioning

This project uses **Git-based metadata** for versioning (DVC is not used,
as the assignment allows Git-based metadata as an alternative):

- `models/metadata/model_metadata.json` — model name, feature names, split
  ratios, metrics, and artifact paths
- `models/metadata/dataset_metadata.json` — dataset SHA256 hash, row/column
  counts, target distribution, and feature columns
- `models/metadata/training_profile.json` — training data feature statistics
  for drift detection

These files are tracked in Git, providing reproducible versioning of the
dataset and model.

## Part 2: FastAPI Model Serving

### Running the API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000/docs for the interactive Swagger UI.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/model-info` | Model metadata |
| POST | `/predict` | Single student prediction |
| POST | `/predict-batch` | Batch predictions |

### Example Prediction Request

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "age": 17, "studytime": 2, "failures": 0, "absences": 5,
    "attendance_pct": 94.62, "g1_grade": 10, "g2_grade": 10,
    "g3_grade": 10, "academic_average": 10.0,
    "famrel": 4, "goout": 3, "Dalc": 1, "Walc": 1, "health": 3,
    "school": "GP", "sex": "F", "schoolsup": "no", "famsup": "yes",
    "higher": "yes", "internet": "yes", "subject": "Math"
  }'
```

## Part 2: Docker Containerization

### Building the Docker Image

```bash
docker build -t student-risk-api .
```

### Running the Container

```bash
docker run -p 8000:8000 student-risk-api
```

The API is available at http://localhost:8000.

## Part 2: Monitoring

The monitoring module tracks:

1. **Input quality** — missing/invalid values in prediction requests
2. **Feature drift** — numerical (KS-test) and categorical (distribution
   comparison) drift between training data and recent predictions
3. **Class distribution** — predicted class balance over time
4. **Model performance** — rolling metrics when ground truth is available
5. **Latency** — prediction response time (mean, p50, p95, p99, max)
6. **Failures** — error count and rate

Metrics are written to `logs/ml_monitoring_metrics.csv` and can also be
written to the `ml_monitoring_metrics` PostgreSQL table.

Run monitoring standalone:

```bash
python -m monitoring.drift_monitor
```

## Part 2: Model Lifecycle and Retraining

See `docs/mlops_lifecycle.md` for the complete model lifecycle documentation
including retraining criteria, promotion stages, and rollback procedures.

## Airflow Execution

### Setting Up Airflow

```bash
# Install Airflow (if not already installed via requirements.txt)
pip install apache-airflow

# Set Airflow home
export AIRFLOW_HOME=~/airflow

# Initialize the database
airflow db init

# Copy the DAG file
cp airflow/dags/student_performance_pipeline.py $AIRFLOW_HOME/dags/

# Set PYTHONPATH to include the project root
export PYTHONPATH=$(pwd):$PYTHONPATH

# Start Airflow (standalone mode for development)
airflow standalone
```

### Using the Airflow UI

1. Open http://localhost:8080 in your browser
2. Find the `student_performance_pipeline` DAG
3. Toggle it to "unpaused"
4. Click "Trigger DAG" to run it manually
5. Monitor task progress in the Graph view

The DAG runs daily at 2:00 AM by default and can be triggered manually at any time.

### DAG Tasks

**Part 1 (data engineering):**
1. `ingest_source_data` → `store_raw_data` → `create_staging_data` →
   `validate_data` → `save_rejected_records` → `create_cleaned_data` →
   `create_analytical_data` → `load_postgresql` → `create_or_refresh_analytics_data_mart`

**Part 2 (ML/MLOps):**
10. `train_ml_models` — trains LR/RF/XGBoost, logs to MLflow, registers best
11. `save_training_profile` — saves training data profile for drift monitoring
12. `monitor_ml_model` — computes drift, quality, latency, failure metrics

Part 2 tasks depend on Part 1 completion (mart_task >> train_task >> profile_task >> monitor_task).

## Streamlit Dashboard Execution

```bash
streamlit run dashboard/app.py
```

The dashboard opens in your browser at http://localhost:8501

### Dashboard Views

**Part 1 views (unchanged):**
1. **Overall Performance Overview** — total students, average performance, pass/fail %, high-risk count
2. **Attendance vs Performance** — scatter plot + study time bar chart
3. **Performance Distribution** — pass/fail pie chart + grade histogram
4. **Risk Analysis** — risk category bar chart + failures by risk
5. **Student-Level Analysis** — search students, view grade progression, full records

**Part 2 view (new):**
6. **ML Risk Prediction** — interactive single-student prediction with
   probability, batch predictions on all students, model details

Use the sidebar to filter by subject, risk category, and pass/fail status.

## Expected Workflow

```
Source CSVs → Ingestion → Raw → Staging → Validation → Rejected + Valid
                                                        ↓
                                                  Cleaning → Analytics → PostgreSQL → Dashboard
                                                                    ↓
                                                            ML Training (LR/RF/XGBoost)
                                                                    ↓
                                                  MLflow → Model Registry → FastAPI → Docker
                                                                    ↓
                                                              Monitoring → Drift Detection
```

1. Place CSV files in `data/source/`
2. Run `python run_pipeline.py` (or use Airflow)
3. Run `python -m models.train` to train ML models
4. Run `uvicorn api.main:app` to serve predictions
5. Run `streamlit run dashboard/app.py` to view the dashboard
6. Check `logs/` for metadata, validation reports, and monitoring metrics
7. Check `data/rejected/` for invalid records

## Project Architecture

See `docs/architecture.md` for the complete architecture with a Mermaid diagram
showing all layers from source to dashboard to ML serving.

## Completion Status

| Component | Status |
|-----------|--------|
| **Part 1** | |
| Dataset source documentation | Complete |
| Reproducible ingestion | Complete |
| Raw data layer | Complete |
| Ingestion metadata | Complete |
| Staging layer | Complete |
| Validation rules | Complete |
| Validation report | Complete |
| Rejected records | Complete |
| Cleaned layer | Complete |
| Analytical layer | Complete |
| Rule-based risk analysis | Complete |
| PostgreSQL database | Complete |
| Analytical data mart | Complete |
| Apache Airflow DAG | Complete |
| Streamlit dashboard | Complete |
| 5+ dashboard indicators | Complete |
| Architecture documentation | Complete |
| Data dictionary | Complete |
| **Part 2** | |
| Risk prediction target | Complete |
| Logistic Regression (baseline) | Complete |
| Random Forest (advanced) | Complete |
| XGBoost (advanced) | Complete |
| Train/val/test split (no leakage) | Complete |
| MLflow tracking | Complete |
| Model registry | Complete |
| Git-based dataset/model metadata | Complete |
| FastAPI serving | Complete |
| Docker containerization | Complete |
| Streamlit ML integration | Complete |
| Monitoring (drift, quality, latency, failures) | Complete |
| Airflow Part 2 tasks | Complete |
| Model lifecycle + retraining criteria | Complete |
| Documentation + reproducibility | Complete |

**Part 1 and Part 2 are complete.**
