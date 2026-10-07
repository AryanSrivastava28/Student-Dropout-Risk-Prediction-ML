"""Stage 6 - Feature Engineering and Analytical Data Layer.

Creates a student-level analytical dataset from the cleaned data with
engineered features and a **rule-based** risk category (no ML model).

Features generated
-------------------
- student_id            : reproducible identifier
- subject               : Math or Portuguese
- studytime             : weekly study time (1-4 ordinal)
- absences              : number of absences (0-93)
- academic_average      : mean of G1, G2, G3 (0-20)
- g1_grade              : first period grade
- g2_grade              : second period grade
- g3_grade              : final grade
- failures              : number of past class failures
- pass_fail             : "pass" if academic_average >= 10 else "fail"
                         (Portuguese grading scale: 0-9 fail, 10-20 pass)
- attendance_pct        : derived attendance percentage = 100 - (absences / max_absences * 100)
                         where max_absences is the maximum observed in the dataset
- risk_category         : "Low Risk", "Medium Risk", or "High Risk"

Rule-based risk categorization (documented in docs/validation_rules.md)
-----------------------------------------------------------------------
The risk score is computed from three academic factors available in the
dataset, each contributing 0-2 points:

  1. Academic performance (academic_average on 0-20 scale):
       0 points if average >= 14 (good)
       1 point  if 10 <= average < 14 (moderate)
       2 points if average < 10 (poor)

  2. Past failures (failures column):
       0 points if failures == 0
       1 point  if failures == 1
       2 points if failures >= 2

  3. Absences (attendance_pct):
       0 points if attendance_pct >= 90  (good attendance)
       1 point  if 75 <= attendance_pct < 90 (moderate attendance)
       2 points if attendance_pct < 75 (poor attendance)

Total risk score (0-6):
  Low Risk:    0-2
  Medium Risk: 3-4
  High Risk:   5-6
"""
from __future__ import annotations

import pandas as pd

from config.settings import ANALYTICAL_DIR, ensure_directories
from transformation.clean_data import run_cleaning


def _compute_attendance_pct(absences: pd.Series) -> pd.Series:
    """Convert raw absence counts to an attendance percentage.

    The UCI dataset caps absences at 93.  We use 93 as the denominator so that
    0 absences = 100% attendance and 93 absences = 0% attendance.
    """
    max_absences = 93
    return (100 - (absences / max_absences) * 100).round(2)


def _compute_risk_score(row: pd.Series) -> int:
    """Compute a 0-6 risk score from academic performance, failures, and attendance."""
    score = 0

    # 1. Academic performance
    avg = row["academic_average"]
    if avg < 10:
        score += 2
    elif avg < 14:
        score += 1

    # 2. Past failures
    failures = row["failures"]
    if failures >= 2:
        score += 2
    elif failures == 1:
        score += 1

    # 3. Attendance
    attendance = row["attendance_pct"]
    if attendance < 75:
        score += 2
    elif attendance < 90:
        score += 1

    return score


def _compute_risk_category(score: int) -> str:
    """Map a 0-6 risk score to a risk category label."""
    if score <= 2:
        return "Low Risk"
    elif score <= 4:
        return "Medium Risk"
    else:
        return "High Risk"


def create_analytics(cleaned_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build the analytical dataset from cleaned data.

    Args:
        cleaned_df: optional pre-loaded cleaned DataFrame.  If None, the
            cleaning pipeline is run first.

    Returns the analytical DataFrame.
    """
    ensure_directories()
    print("=== Stage 6: Feature Engineering and Analytical Layer ===")

    if cleaned_df is None:
        cleaned_df = run_cleaning()

    if cleaned_df.empty:
        print("  [analytics] No cleaned data available.")
        return pd.DataFrame()

    df = cleaned_df.copy()

    # --- Feature engineering ---
    print("  [analytics] Engineering features ...")

    # Academic average: mean of G1, G2, G3.
    df["academic_average"] = df[["G1", "G2", "G3"]].mean(axis=1).round(2)

    # Attendance percentage derived from absences.
    df["attendance_pct"] = _compute_attendance_pct(df["absences"])

    # Pass/fail: Portuguese passing grade is 10/20.
    df["pass_fail"] = df["academic_average"].apply(
        lambda avg: "pass" if avg >= 10 else "fail"
    )

    # Rename grade columns for clarity in the analytical layer.
    df = df.rename(columns={"G1": "g1_grade", "G2": "g2_grade", "G3": "g3_grade"})

    # --- Rule-based risk scoring ---
    print("  [analytics] Computing rule-based risk categories ...")
    df["risk_score"] = df.apply(_compute_risk_score, axis=1)
    df["risk_category"] = df["risk_score"].apply(_compute_risk_category)

    # Select and order the analytical columns.
    analytical_columns = [
        "student_id",
        "subject",
        "school",
        "sex",
        "age",
        "studytime",
        "failures",
        "absences",
        "attendance_pct",
        "g1_grade",
        "g2_grade",
        "g3_grade",
        "academic_average",
        "pass_fail",
        "risk_score",
        "risk_category",
        "schoolsup",
        "famsup",
        "higher",
        "internet",
        "famrel",
        "goout",
        "Dalc",
        "Walc",
        "health",
    ]
    analytical_df = df[analytical_columns].copy()

    # Save the analytical dataset.
    output_path = ANALYTICAL_DIR / "student_analytics.csv"
    analytical_df.to_csv(output_path, index=False)
    print(f"  [analytics] Saved {output_path.name} ({len(analytical_df)} rows)")

    # Print a quick risk distribution summary.
    risk_counts = analytical_df["risk_category"].value_counts()
    print("  [analytics] Risk distribution:")
    for category, count in risk_counts.items():
        print(f"         {category}: {count}")

    print("  [analytics] Analytical layer complete.")
    return analytical_df


if __name__ == "__main__":
    create_analytics()
