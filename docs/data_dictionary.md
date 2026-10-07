# Data Dictionary

This document explains the columns in the analytical dataset produced by the pipeline.

## Source Dataset Columns (UCI Student Performance)

| Column | Type | Description | Values |
|--------|------|-------------|--------|
| school | text | Student's school | GP (Gabriel Pereira), MS (Mousinho da Silveira) |
| sex | text | Student's sex | F (female), M (male) |
| age | integer | Student's age | 15-22 |
| address | text | Home address type | U (urban), R (rural) |
| famsize | text | Family size | LE3 (≤3), GT3 (>3) |
| Pstatus | text | Parents' cohabitation status | T (together), A (apart) |
| Medu | integer | Mother's education | 0 (none), 1 (primary), 2 (5-9th grade), 3 (secondary), 4 (higher) |
| Fedu | integer | Father's education | 0 (none), 1 (primary), 2 (5-9th grade), 3 (secondary), 4 (higher) |
| Mjob | text | Mother's job | teacher, health, services, at_home, other |
| Fjob | text | Father's job | teacher, health, services, at_home, other |
| reason | text | Reason to choose school | home, reputation, course, other |
| guardian | text | Student's guardian | mother, father, other |
| traveltime | integer | Home-to-school travel time | 1 (<15 min), 2 (15-30 min), 3 (30-60 min), 4 (>1 hr) |
| studytime | integer | Weekly study time | 1 (<2 hrs), 2 (2-5 hrs), 3 (5-10 hrs), 4 (>10 hrs) |
| failures | integer | Number of past class failures | 0, 1, 2, 4 (4 = 3 or more) |
| schoolsup | text | Extra educational support | yes, no |
| famsup | text | Family educational support | yes, no |
| paid | text | Extra paid classes | yes, no |
| activities | text | Extra-curricular activities | yes, no |
| nursery | text | Attended nursery school | yes, no |
| higher | text | Wants higher education | yes, no |
| internet | text | Internet access at home | yes, no |
| romantic | text | In a romantic relationship | yes, no |
| famrel | integer | Quality of family relationships | 1 (very bad) - 5 (excellent) |
| freetime | integer | Free time after school | 1 (very low) - 5 (very high) |
| goout | integer | Going out with friends | 1 (very low) - 5 (very high) |
| Dalc | integer | Workday alcohol consumption | 1 (very low) - 5 (very high) |
| Walc | integer | Weekend alcohol consumption | 1 (very low) - 5 (very high) |
| health | integer | Current health status | 1 (very bad) - 5 (very good) |
| absences | integer | Number of school absences | 0-93 |
| G1 | integer | First period grade | 0-20 |
| G2 | integer | Second period grade | 0-20 |
| G3 | integer | Final grade | 0-20 |

## Engineered Columns (Added by the Pipeline)

| Column | Type | Description | How It Is Computed |
|--------|------|-------------|--------------------|
| student_id | text | Reproducible student identifier | SHA-256 hash of demographic key columns, prefixed with "STU_" |
| subject | text | Course subject | "Math" or "Portuguese" (derived from source file name) |
| attendance_pct | numeric | Attendance percentage | 100 - (absences / 93 × 100) |
| academic_average | numeric | Mean of three grading periods | (G1 + G2 + G3) / 3, rounded to 2 decimals |
| g1_grade | integer | First period grade (renamed) | Same as G1 |
| g2_grade | integer | Second period grade (renamed) | Same as G2 |
| g3_grade | integer | Final grade (renamed) | Same as G3 |
| pass_fail | text | Pass or fail status | "pass" if academic_average ≥ 10, else "fail" |
| risk_score | integer | Rule-based risk score (0-6) | Sum of points from 3 factors (see validation_rules.md) |
| risk_category | text | Risk category label | "Low Risk" (0-2), "Medium Risk" (3-4), "High Risk" (5-6) |

## Student ID Generation Rule

The UCI dataset does not include a real student identifier. We generate a
reproducible `student_id` using the following rule:

1. Take the 14 demographic key columns that uniquely identify a student
   (same columns used in the dataset's `student-merge.R` file):
   `school, sex, age, address, famsize, Pstatus, Medu, Fedu, Mjob, Fjob, reason, guardian, traveltime, studytime`
2. Concatenate their values (lowercased, stripped) with `|` as separator.
3. Compute the SHA-256 hash of the resulting string.
4. Take the first 12 hex characters and prefix with `STU_`.
5. Example: `STU_F331360EEF03`

The same student appearing in both the Math and Portuguese files receives
the same `student_id`, enabling cross-subject analysis.
