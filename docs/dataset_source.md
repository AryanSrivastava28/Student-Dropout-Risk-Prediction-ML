# Dataset Source Documentation

## Dataset Name

**UCI Machine Learning Repository — Student Performance Data Set**

## Source

- **Repository**: UC Irvine Machine Learning Repository
- **URL**: https://archive.ics.uci.edu/dataset/320/student+performance
- **Citation**: P. Cortez and A. Silva, "Using Data Mining to Predict Secondary School Student Performance," in A. K. et al. (Eds.), *Proceedings of 5th Future Business Technology Conference (FUBUTEC 2008)*, pp. 5-12, Porto, Portugal, 2008.

## Access Instructions

The dataset is freely available for research and educational purposes.

1. Visit the UCI repository page: https://archive.ics.uci.edu/dataset/320/student+performance
2. Click "Download" to get the ZIP archive.
3. Extract the ZIP file to obtain:
   - `student-mat.csv` — Math course student records
   - `student-por.csv` — Portuguese language course student records
   - `student.txt` — Attribute description
   - `student-merge.R` — R script for merging the two datasets

Alternatively, the files can be downloaded directly:
```
wget https://archive.ics.uci.edu/static/public/320/student+performance.zip
unzip student+performance.zip
```

## Dataset Description

This dataset contains student achievement data from two Portuguese secondary schools:
- **Gabriel Pereira (GP)**
- **Mousinho da Silveira (MS)**

The data was collected using school reports and questionnaires. It includes:
- Student demographics (age, sex, address, family size)
- Family background (parents' education, parents' jobs, family relationship quality)
- School-related attributes (study time, travel time, extra support, absences)
- Academic performance (three grading periods: G1, G2, G3 on a 0-20 scale)
- Lifestyle factors (alcohol consumption, going out, health status)

### Key Statistics

| File | Records | Columns | Description |
|------|---------|---------|-------------|
| `student-mat.csv` | 395 | 33 | Math course students |
| `student-por.csv` | 649 | 33 | Portuguese language course students |

There are approximately 382 students who appear in both datasets (identified by matching demographic attributes).

## Files Used in This Project

Both CSV files are placed in `data/source/`:

1. **`data/source/student-mat.csv`** — Math course records (395 rows)
2. **`data/source/student-por.csv`** — Portuguese course records (649 rows)

The original `student.txt` attribute description is preserved in `docs/uci_student_dataset_description.txt`.

## Privacy and Ethics

- The dataset contains **no personally identifiable information** (no names, no real IDs).
- All attributes are anonymized categorical or ordinal values.
- The dataset is publicly available and approved for educational use by the UCI repository.
- No confidential or real student data is included in this project.
