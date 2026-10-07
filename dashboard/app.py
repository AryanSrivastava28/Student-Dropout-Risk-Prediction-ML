"""Streamlit Dashboard for Student Performance Analytics.

Displays interactive analytics from the PostgreSQL data warehouse:
  1. Overall Performance Overview (KPIs)
  2. Attendance vs Performance relationship
  3. Performance Distribution (pass/fail, grade distribution)
  4. Risk Analysis (Low / Medium / High Risk)
  5. Student-Level Analysis (search, filter, detail view)

The dashboard reads from the student_performance_analytics table via the
Supabase REST API.  If the database is unavailable, it falls back to the
local analytical CSV file so the dashboard can still be demonstrated.

Usage:
    streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Add project root to sys.path so imports resolve when running with streamlit.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import ANALYTICAL_DIR
from database.db_client import fetch_all, test_connection
from dashboard.ml_panel import render_ml_panel


@st.cache_data(ttl=300)
def load_analytics_data() -> pd.DataFrame:
    """Load analytics data from PostgreSQL, falling back to local CSV."""
    # Try the database first.
    if test_connection():
        try:
            rows = fetch_all(
                "student_performance_analytics",
                "student_id,subject,school,sex,age,studytime,failures,absences,"
                "attendance_pct,g1_grade,g2_grade,g3_grade,academic_average,"
                "pass_fail,risk_score,risk_category,schoolsup,famsup,higher,"
                "internet,famrel,goout,dalc,walc,health",
            )
            if rows:
                df = pd.DataFrame(rows)
                st.session_state["data_source"] = "PostgreSQL database"
                return df
        except Exception as exc:
            st.warning(f"Database query failed: {exc}. Falling back to local CSV.")

    # Fall back to the local analytical CSV.
    csv_path = ANALYTICAL_DIR / "student_analytics.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        st.session_state["data_source"] = f"Local CSV ({csv_path.name})"
        return df

    st.error("No analytics data found. Run the pipeline first.")
    st.session_state["data_source"] = "No data available"
    return pd.DataFrame()


def main() -> None:
    st.set_page_config(
        page_title="Student Performance Analytics",
        page_icon="📊",
        layout="wide",
    )

    st.title("Student Performance & Dropout-Risk Analytics")
    st.markdown("Part 1 — Data Engineering Pipeline Dashboard")

    # Load data.
    df = load_analytics_data()

    if df.empty:
        st.stop()

    # Show data source in the sidebar.
    data_source = st.session_state.get("data_source", "Unknown")
    st.sidebar.info(f"Data source: {data_source}")
    st.sidebar.info(f"Total records: {len(df)}")

    # --- Sidebar Filters ---
    st.sidebar.header("Filters")

    # Subject filter.
    subjects = ["All"] + sorted(df["subject"].unique().tolist())
    selected_subject = st.sidebar.selectbox("Subject", subjects)

    # Risk filter.
    risks = ["All"] + sorted(df["risk_category"].unique().tolist())
    selected_risk = st.sidebar.selectbox("Risk Category", risks)

    # Pass/fail filter.
    pass_fail_options = ["All"] + sorted(df["pass_fail"].unique().tolist())
    selected_pass_fail = st.sidebar.selectbox("Pass / Fail", pass_fail_options)

    # Apply filters.
    filtered_df = df.copy()
    if selected_subject != "All":
        filtered_df = filtered_df[filtered_df["subject"] == selected_subject]
    if selected_risk != "All":
        filtered_df = filtered_df[filtered_df["risk_category"] == selected_risk]
    if selected_pass_fail != "All":
        filtered_df = filtered_df[filtered_df["pass_fail"] == selected_pass_fail]

    if filtered_df.empty:
        st.warning("No records match the selected filters.")
        st.stop()

    # --- 1. Overall Performance Overview ---
    st.header("1. Overall Performance Overview")

    total_students = filtered_df["student_id"].nunique()
    avg_performance = filtered_df["academic_average"].mean()
    pass_pct = (filtered_df["pass_fail"] == "pass").mean() * 100
    fail_pct = (filtered_df["pass_fail"] == "fail").mean() * 100
    high_risk_count = (filtered_df["risk_category"] == "High Risk").sum()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Students", total_students)
    col2.metric("Avg Performance", f"{avg_performance:.1f}/20")
    col3.metric("Pass %", f"{pass_pct:.1f}%")
    col4.metric("Fail %", f"{fail_pct:.1f}%")
    col5.metric("High Risk", high_risk_count)

    st.markdown("---")

    # --- 2. Attendance vs Performance ---
    st.header("2. Attendance vs Performance")

    col_left, col_right = st.columns([3, 2])

    with col_left:
        fig_scatter = px.scatter(
            filtered_df,
            x="attendance_pct",
            y="academic_average",
            color="risk_category",
            title="Attendance % vs Academic Average",
            labels={
                "attendance_pct": "Attendance (%)",
                "academic_average": "Academic Average (0-20)",
                "risk_category": "Risk Category",
            },
            hover_data=["student_id", "subject", "failures"],
            color_discrete_map={
                "Low Risk": "#2ecc71",
                "Medium Risk": "#f39c12",
                "High Risk": "#e74c3c",
            },
        )
        fig_scatter.update_layout(height=400)
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col_right:
        # Study time vs average grade (bar chart).
        study_avg = filtered_df.groupby("studytime")["academic_average"].mean().reset_index()
        study_labels = {1: "<2 hrs", 2: "2-5 hrs", 3: "5-10 hrs", 4: ">10 hrs"}
        study_avg["study_label"] = study_avg["studytime"].map(study_labels)
        fig_study = px.bar(
            study_avg,
            x="study_label",
            y="academic_average",
            title="Avg Grade by Study time",
            labels={"study_label": "Weekly Study time", "academic_average": "Avg Grade"},
        )
        fig_study.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_study, use_container_width=True)

    st.markdown("---")

    # --- 3. Performance Distribution ---
    st.header("3. Performance Distribution")

    col_a, col_b = st.columns(2)

    with col_a:
        # Pass/fail pie chart.
        pass_fail_counts = filtered_df["pass_fail"].value_counts().reset_index()
        pass_fail_counts.columns = ["Status", "Count"]
        fig_pf = px.pie(
            pass_fail_counts,
            values="Count",
            names="Status",
            title="Pass / Fail Distribution",
            color="Status",
            color_discrete_map={"pass": "#2ecc71", "fail": "#e74c3c"},
        )
        fig_pf.update_layout(height=400)
        st.plotly_chart(fig_pf, use_container_width=True)

    with col_b:
        # Grade distribution histogram.
        fig_hist = px.histogram(
            filtered_df,
            x="academic_average",
            nbins=20,
            title="Academic Average Distribution",
            labels={"academic_average": "Academic Average (0-20)"},
            color="risk_category",
            color_discrete_map={
                "Low Risk": "#2ecc71",
                "Medium Risk": "#f39c12",
                "High Risk": "#e74c3c",
            },
        )
        fig_hist.update_layout(height=400, barmode="overlay")
        fig_hist.update_traces(opacity=0.75)
        st.plotly_chart(fig_hist, use_container_width=True)

    st.markdown("---")

    # --- 4. Risk Analysis ---
    st.header("4. Risk Analysis")

    col_r1, col_r2 = st.columns([2, 3])

    with col_r1:
        risk_counts = filtered_df["risk_category"].value_counts().reset_index()
        risk_counts.columns = ["Risk Category", "Count"]
        fig_risk = px.bar(
            risk_counts,
            x="Risk Category",
            y="Count",
            title="Students by Risk Category",
            color="Risk Category",
            color_discrete_map={
                "Low Risk": "#2ecc71",
                "Medium Risk": "#f39c12",
                "High Risk": "#e74c3c",
            },
        )
        fig_risk.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_risk, use_container_width=True)

    with col_r2:
        # Risk factors: failures vs risk.
        risk_fail = filtered_df.groupby(["risk_category", "failures"]).size().reset_index(name="count")
        fig_rf = px.bar(
            risk_fail,
            x="failures",
            y="count",
            color="risk_category",
            title="Past Failures by Risk Category",
            labels={"failures": "Number of Past Failures", "count": "Student Count"},
            color_discrete_map={
                "Low Risk": "#2ecc71",
                "Medium Risk": "#f39c12",
                "High Risk": "#e74c3c",
            },
            barmode="group",
        )
        fig_rf.update_layout(height=400)
        st.plotly_chart(fig_rf, use_container_width=True)

    st.markdown("---")

    # --- 5. Student-Level Analysis ---
    st.header("5. Student-Level Analysis")

    # Student search / selection.
    student_ids = sorted(filtered_df["student_id"].unique().tolist())
    selected_student = st.selectbox(
        "Select a student to view details", student_ids, key="student_select"
    )

    student_data = filtered_df[filtered_df["student_id"] == selected_student]

    if not student_data.empty:
        st.subheader(f"Student: {selected_student}")

        # Show student metrics in columns.
        s = student_data.iloc[0]
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Subject", s.get("subject", "N/A"))
        sc2.metric("Academic Average", f"{s.get('academic_average', 0):.1f}/20")
        sc3.metric("Attendance", f"{s.get('attendance_pct', 0):.1f}%")
        sc4.metric("Risk", s.get("risk_category", "N/A"))

        sc5, sc6, sc7, sc8 = st.columns(4)
        sc5.metric("G1 Grade", s.get("g1_grade", "N/A"))
        sc6.metric("G2 Grade", s.get("g2_grade", "N/A"))
        sc7.metric("G3 Grade", s.get("g3_grade", "N/A"))
        sc8.metric("Past Failures", s.get("failures", "N/A"))

        # Grade trend for this student.
        grade_cols = ["g1_grade", "g2_grade", "g3_grade"]
        grade_labels = ["G1 (Period 1)", "G2 (Period 2)", "G3 (Final)"]
        fig_trend = go.Figure(
            data=go.Scatter(
                x=grade_labels,
                y=[s.get(c, 0) for c in grade_cols],
                mode="lines+markers",
                name="Grades",
                line=dict(color="#3498db", width=3),
                marker=dict(size=10),
            )
        )
        fig_trend.update_layout(
            title="Grade Progression",
            yaxis_title="Grade (0-20)",
            xaxis_title="Assessment Period",
            height=350,
        )
        st.plotly_chart(fig_trend, use_container_width=True)

        # Full record as a table.
        st.subheader("Full Record")
        st.dataframe(student_data.T, use_container_width=True)

    st.markdown("---")

    # --- Data table view ---
    with st.expander("View Filtered Data Table"):
        st.dataframe(filtered_df, use_container_width=True)

    # --- 6. ML Risk Prediction (Part 2) ---
    render_ml_panel(filtered_df)

    # --- Footer ---
    st.markdown("---")
    st.caption(
        "Student Performance & Dropout-Risk Prediction — Part 1 (Data Engineering) + Part 2 (ML/MLOps) | "
        "Data: UCI Student Performance Dataset | "
        "ML model: XGBoost (MLflow-tracked, FastAPI-served)"
    )


if __name__ == "__main__":
    main()
