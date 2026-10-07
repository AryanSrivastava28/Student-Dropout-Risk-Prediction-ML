# Validation and Cleaning Rules

This document describes every validation rule and cleaning rule applied
in the pipeline.

---

## Validation Rules (Stage 3)

The validation module (`transformation/validate_data.py`) checks each
staged record against the following rules. Records that fail any rule are
sent to the rejected records layer.

### 1. Duplicate Records

**Rule**: No two records may share the same `student_id` AND `subject`
combination.

**Implementation**: `df.duplicated(subset=["student_id", "subject"], keep=False)`
flags all rows involved in a duplicate (not just the second occurrence).

**Action**: All duplicate rows are rejected with reason `duplicate_record`.

### 2. Missing Critical Identifiers

**Rule**: `student_id` and `subject` must not be null or empty.

**Action**: Rows with missing critical fields are rejected with reason
`missing_critical_id`.

### 3. Invalid Numeric Values

**Rule**: The following columns must contain valid numeric values within
their specified ranges:

| Column | Min | Max | Description |
|--------|-----|-----|-------------|
| age | 15 | 22 | Student age |
| Medu | 0 | 4 | Mother's education level |
| Fedu | 0 | 4 | Father's education level |
| traveltime | 1 | 4 | Home-to-school travel time |
| studytime | 1 | 4 | Weekly study time |
| failures | 0 | 4 | Past class failures (4 = 3+) |
| famrel | 1 | 5 | Family relationship quality |
| freetime | 1 | 5 | Free time after school |
| goout | 1 | 5 | Going out with friends |
| Dalc | 1 | 5 | Workday alcohol consumption |
| Walc | 1 | 5 | Weekend alcohol consumption |
| health | 1 | 5 | Current health status |
| absences | 0 | 93 | Number of absences |
| G1 | 0 | 20 | First period grade |
| G2 | 0 | 20 | Second period grade |
| G3 | 0 | 20 | Final grade |

**Action**: Rows with out-of-range or non-numeric values are rejected with
reason `invalid_<column_name>`.

### 4. Invalid Mark Ranges

**Rule**: Grades G1, G2, G3 must be between 0 and 20 (Portuguese grading scale).

**Action**: Covered by the numeric range check above. Rejected with reason
`invalid_G1`, `invalid_G2`, or `invalid_G3`.

### 5. Invalid Attendance Ranges

**Rule**: `absences` must be between 0 and 93.

**Action**: Covered by the numeric range check. Rejected with reason
`invalid_absences`.

### 6. Invalid Categorical Values

**Rule**: Categorical columns must contain only their allowed values:

| Column | Allowed Values |
|--------|-----------------|
| school | GP, MS |
| sex | F, M |
| address | U, R |
| famsize | LE3, GT3 |
| Pstatus | T, A |
| Mjob | teacher, health, services, at_home, other |
| Fjob | teacher, health, services, at_home, other |
| reason | home, reputation, course, other |
| guardian | mother, father, other |
| schoolsup | yes, no |
| famsup | yes, no |
| paid | yes, no |
| activities | yes, no |
| nursery | yes, no |
| higher | yes, no |
| internet | yes, no |
| romantic | yes, no |

**Action**: Rows with invalid categorical values are rejected with reason
`invalid_<column_name>`.

### 7. Data Type Issues

**Rule**: Numeric columns must be coercible to numeric types. This is
implicitly checked during the numeric range validation — if `pd.to_numeric`
fails, the value is flagged as invalid.

**Action**: Rows with type issues are rejected as part of the numeric checks.

---

## Rejected Records (Stage 4)

Invalid records are saved to `data/rejected/rejected_records.csv` with the
following additional columns:

| Column | Description |
|--------|-------------|
| rejection_reason | Semicolon-separated list of failed validation rules |
| source_file | Name of the source file the record came from |
| rejection_timestamp | UTC timestamp of when the record was rejected |

The rejected records file is never manually edited.

---

## Cleaning Rules (Stage 5)

The cleaning module (`transformation/clean_data.py`) applies these rules
to the valid records:

### 1. Remove Duplicate Records

**Rule**: Keep only the first occurrence of each `student_id` + `subject`
combination.

**Implementation**: `df.drop_duplicates(subset=["student_id", "subject"], keep="first")`

### 2. Handle Missing Values

**Numeric columns**: Fill missing values with the **median** of that column
within the same subject group (Math and Portuguese are handled independently).
If the subject-group median is also empty, fall back to the global column median.

**Categorical columns**: Fill missing values with the **mode** (most frequent
value) of that column within the same subject group. If the mode is empty,
fill with `"unknown"`.

### 3. Correct Data Types

**Numeric columns**: Coerce to `Int64` (nullable integer type) using
`pd.to_numeric(errors="coerce")`.

**Categorical columns**: Convert to string and strip whitespace.

### 4. Ensure Important Fields Are Valid

All range and categorical validity checks were already performed in the
validation stage. The cleaning stage operates only on records that passed
validation, so no additional range corrections are needed.

### 5. Retain Only Accepted Records

Only records that passed all validation checks are included in the cleaned
output. Rejected records are excluded.

---

## Risk Categorization Rules (Stage 6)

The risk score is computed from three academic factors, each contributing
0-2 points (total score: 0-6):

### Factor 1: Academic Performance (academic_average, 0-20 scale)

| Score | Condition |
|-------|-----------|
| 0 points | average ≥ 14 (good performance) |
| 1 point | 10 ≤ average < 14 (moderate performance) |
| 2 points | average < 10 (poor performance) |

### Factor 2: Past Failures (failures column)

| Score | Condition |
|-------|-----------|
| 0 points | failures = 0 |
| 1 point | failures = 1 |
| 2 points | failures ≥ 2 |

### Factor 3: Attendance (attendance_pct)

| Score | Condition |
|-------|-----------|
| 0 points | attendance ≥ 90% (good attendance) |
| 1 point | 75% ≤ attendance < 90% (moderate attendance) |
| 2 points | attendance < 75% (poor attendance) |

### Risk Category Mapping

| Total Score | Category |
|-------------|----------|
| 0-2 | Low Risk |
| 3-4 | Medium Risk |
| 5-6 | High Risk |

### Pass/Fail Rule

The Portuguese grading scale uses 0-20, with 10 as the passing threshold:

| academic_average | Status |
|------------------|--------|
| ≥ 10 | pass |
| < 10 | fail |
