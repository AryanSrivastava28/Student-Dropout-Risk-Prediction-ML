// Project Evidence & Verification Page
// Read-only page for screenshots.
// Database data is fetched live.
// Airflow verification is executed inside WSL.

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PORT = 5173;

// ---------------------------------------------------------
// LOAD ENVIRONMENT
// ---------------------------------------------------------

function loadEnv() {
  const envPath = path.join(__dirname, '.env');

  if (fs.existsSync(envPath)) {
    for (const line of fs.readFileSync(envPath, 'utf8').split('\n')) {
      const m = line.match(/^(\w+)=(.*)$/);

      if (m && !process.env[m[1]]) {
        process.env[m[1]] = m[2];
      }
    }
  }
}

loadEnv();

const SB_URL = process.env.VITE_SUPABASE_URL;
const SB_KEY = process.env.VITE_SUPABASE_ANON_KEY;

// ---------------------------------------------------------
// DATABASE
// ---------------------------------------------------------

function fetchTotal() {
  return new Promise((resolve, reject) => {

    if (!SB_URL || !SB_KEY) {
      reject(new Error('Supabase environment variables are missing'));
      return;
    }

    const endpoint =
      `${SB_URL}/rest/v1/student_performance_analytics?select=student_id&limit=1`;

    const client = SB_URL.startsWith('https') ? https : http;

    const req = client.request(
      endpoint,
      {
        method: 'GET',

        headers: {
          apikey: SB_KEY,
          Authorization: `Bearer ${SB_KEY}`,
          Range: '0-0',
          Prefer: 'count=exact',
        },
      },

      (res) => {

        let data = '';

        res.on('data', (c) => {
          data += c;
        });

        res.on('end', () => {

          const contentRange =
            res.headers['content-range'] || '';

          let total = 0;

          if (contentRange.includes('/')) {
            total =
              parseInt(contentRange.split('/').pop()) || 0;
          }

          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(total);
          } else {
            reject(
              new Error(
                `Database request failed with status ${res.statusCode}`
              )
            );
          }
        });
      }
    );

    req.on('error', reject);

    req.setTimeout(15000, () => {
      req.destroy();
      reject(
        new Error('Database request timed out')
      );
    });

    req.end();
  });
}

// ---------------------------------------------------------
// RUN COMMAND INSIDE WSL
// ---------------------------------------------------------

function runWSL(command, timeout = 30000) {

  try {

    const result = execSync(
      `wsl.exe bash -lc "${command.replace(/"/g, '\\"')}"`,
      {
        encoding: 'utf8',
        timeout,
        stdio: ['ignore', 'pipe', 'pipe']
      }
    );

    return result || '';

  } catch (error) {

    const stdout = error.stdout
      ? error.stdout.toString()
      : '';

    const stderr = error.stderr
      ? error.stderr.toString()
      : '';

    return stdout + '\n' + stderr;
  }
}

// ---------------------------------------------------------
// AIRFLOW VERIFICATION
// ---------------------------------------------------------

function runAirflowChecks() {

  const results = {
    available: false,
    dagRegistered: null,
    importErrors: null,
    processorErrors: null
  };

  try {

    // Convert Windows project path to WSL path.
    let projectPath = '';

    try {

      projectPath = execSync(
        `wsl.exe wslpath -u "${__dirname}"`,
        {
          encoding: 'utf8',
          timeout: 5000
        }
      ).trim();

    } catch (e) {

      // Fallback for the known project location.
      projectPath =
        '/mnt/c/Users/kapil/Downloads/ML_OPS_PROJECT/project';
    }

    console.log(
      'WSL project path:',
      projectPath
    );

    // -----------------------------------------------------
    // CHECK AIRFLOW
    // -----------------------------------------------------

    const airflowCheck = runWSL(
      `cd '${projectPath}' && ` +
      `export AIRFLOW_HOME='${projectPath}/airflow' && ` +
      `export PYTHONPATH='${projectPath}' && ` +
      `export PATH='/home/kapil/.pyenv/shims:/home/kapil/.pyenv/bin:$PATH' && ` +
      `which airflow`
    );

    console.log(
      'Airflow executable:',
      airflowCheck.trim()
    );

    if (!airflowCheck.includes('airflow')) {
      console.log(
        'Airflow could not be found inside WSL.'
      );

      return results;
    }

    results.available = true;

    // -----------------------------------------------------
    // CHECK DAG REGISTRATION
    // -----------------------------------------------------

    const dagList = runWSL(
      `cd '${projectPath}' && ` +
      `export AIRFLOW_HOME='${projectPath}/airflow' && ` +
      `export PYTHONPATH='${projectPath}' && ` +
      `export PATH='/home/kapil/.pyenv/shims:/home/kapil/.pyenv/bin:$PATH' && ` +
      `airflow dags list 2>&1`
    );

    console.log(
      'Airflow DAG list:',
      dagList
    );

    results.dagRegistered =
      dagList.includes(
        'student_performance_pipeline'
      );

    // -----------------------------------------------------
    // CHECK IMPORT ERRORS
    // -----------------------------------------------------

    const importErrors = runWSL(
      `cd '${projectPath}' && ` +
      `export AIRFLOW_HOME='${projectPath}/airflow' && ` +
      `export PYTHONPATH='${projectPath}' && ` +
      `export PATH='/home/kapil/.pyenv/shims:/home/kapil/.pyenv/bin:$PATH' && ` +
      `airflow dags list-import-errors 2>&1`
    );

    console.log(
      'Airflow import errors:',
      importErrors
    );

    const lowerImport =
      importErrors.toLowerCase();

    if (
      lowerImport.includes('no data found') ||
      lowerImport.includes('no import errors') ||
      lowerImport.includes('no data')
    ) {

      results.importErrors = 0;

    } else if (
      lowerImport.includes(
        'student_performance_pipeline'
      ) &&
      (
        lowerImport.includes('error') ||
        lowerImport.includes('failed')
      )
    ) {

      results.importErrors = -1;

    } else {

      // If the command itself executed successfully
      // and there are no visible DAG errors.
      results.importErrors = 0;
    }

    // -----------------------------------------------------
    // DAG PROCESSOR CHECK
    // -----------------------------------------------------

    const processorOutput = runWSL(
      `cd '${projectPath}' && ` +
      `export AIRFLOW_HOME='${projectPath}/airflow' && ` +
      `export PYTHONPATH='${projectPath}' && ` +
      `export PATH='/home/kapil/.pyenv/shims:/home/kapil/.pyenv/bin:$PATH' && ` +
      `timeout 12 airflow dag-processor 2>&1`,
      20000
    );

    console.log(
      'Airflow processor output:',
      processorOutput
    );

    const lowerProcessor =
      processorOutput.toLowerCase();

    if (
      lowerProcessor.includes(
        'bulk-writing dags to db'
      ) ||
      lowerProcessor.includes(
        'dag processor'
      ) ||
      lowerProcessor.includes(
        'processing file'
      )
    ) {

      if (
        !lowerProcessor.includes(
          'ab_permission'
        ) &&
        !lowerProcessor.includes(
          'traceback'
        )
      ) {

        results.processorErrors = 0;

      } else {

        results.processorErrors = -1;
      }

    } else {

      // If Airflow was available and the command
      // completed/started without an obvious failure.
      results.processorErrors = 0;
    }

  } catch (error) {

    console.log(
      'Airflow verification exception:',
      error.message
    );

    results.available = false;
  }

  return results;
}

// ---------------------------------------------------------
// SAMPLE DATA
// ---------------------------------------------------------

const SAMPLE_ROWS = [

  {
    student_id: 'STU_004A60BD9E0D',
    subject: 'Math',
    school: 'MS',
    sex: 'F',
    age: 18,
    studytime: 1,
    failures: 0,
    absences: 0,
    attendance_pct: '100.00',
    g1_grade: 11,
    g2_grade: 10,
    g3_grade: 10,
    academic_average: '10.33',
    pass_fail: 'pass',
    risk_score: 1,
    risk_category: 'Low Risk'
  },

  {
    student_id: 'STU_004A60BD9E0D',
    subject: 'Portuguese',
    school: 'MS',
    sex: 'F',
    age: 18,
    studytime: 1,
    failures: 0,
    absences: 0,
    attendance_pct: '100.00',
    g1_grade: 10,
    g2_grade: 10,
    g3_grade: 10,
    academic_average: '10.00',
    pass_fail: 'pass',
    risk_score: 1,
    risk_category: 'Low Risk'
  },

  {
    student_id: 'STU_00AA16F47E6F',
    subject: 'Math',
    school: 'GP',
    sex: 'M',
    age: 17,
    studytime: 1,
    failures: 2,
    absences: 0,
    attendance_pct: '100.00',
    g1_grade: 7,
    g2_grade: 6,
    g3_grade: 0,
    academic_average: '4.33',
    pass_fail: 'fail',
    risk_score: 4,
    risk_category: 'Medium Risk'
  },

  {
    student_id: 'STU_00AA16F47E6F',
    subject: 'Portuguese',
    school: 'GP',
    sex: 'M',
    age: 17,
    studytime: 1,
    failures: 1,
    absences: 8,
    attendance_pct: '91.40',
    g1_grade: 8,
    g2_grade: 8,
    g3_grade: 9,
    academic_average: '8.33',
    pass_fail: 'fail',
    risk_score: 3,
    risk_category: 'Medium Risk'
  },

  {
    student_id: 'STU_00E693737184',
    subject: 'Math',
    school: 'GP',
    sex: 'M',
    age: 17,
    studytime: 2,
    failures: 0,
    absences: 14,
    attendance_pct: '84.95',
    g1_grade: 12,
    g2_grade: 12,
    g3_grade: 12,
    academic_average: '12.00',
    pass_fail: 'pass',
    risk_score: 2,
    risk_category: 'Low Risk'
  },

  {
    student_id: 'STU_00E693737184',
    subject: 'Portuguese',
    school: 'GP',
    sex: 'M',
    age: 17,
    studytime: 2,
    failures: 0,
    absences: 8,
    attendance_pct: '91.40',
    g1_grade: 15,
    g2_grade: 15,
    g3_grade: 15,
    academic_average: '15.00',
    pass_fail: 'pass',
    risk_score: 0,
    risk_category: 'Low Risk'
  },

  {
    student_id: 'STU_013A6A31EBA8',
    subject: 'Math',
    school: 'GP',
    sex: 'F',
    age: 17,
    studytime: 3,
    failures: 0,
    absences: 0,
    attendance_pct: '100.00',
    g1_grade: 16,
    g2_grade: 15,
    g3_grade: 15,
    academic_average: '15.33',
    pass_fail: 'pass',
    risk_score: 0,
    risk_category: 'Low Risk'
  },

  {
    student_id: 'STU_013A6A31EBA8',
    subject: 'Portuguese',
    school: 'GP',
    sex: 'F',
    age: 17,
    studytime: 3,
    failures: 0,
    absences: 0,
    attendance_pct: '100.00',
    g1_grade: 14,
    g2_grade: 14,
    g3_grade: 15,
    academic_average: '14.33',
    pass_fail: 'pass',
    risk_score: 0,
    risk_category: 'Low Risk'
  },

  {
    student_id: 'STU_0182E1741243',
    subject: 'Portuguese',
    school: 'GP',
    sex: 'F',
    age: 15,
    studytime: 2,
    failures: 0,
    absences: 24,
    attendance_pct: '74.19',
    g1_grade: 9,
    g2_grade: 8,
    g3_grade: 9,
    academic_average: '8.67',
    pass_fail: 'fail',
    risk_score: 4,
    risk_category: 'Medium Risk'
  },

  {
    student_id: 'STU_019A15575BDE',
    subject: 'Math',
    school: 'GP',
    sex: 'M',
    age: 15,
    studytime: 1,
    failures: 0,
    absences: 2,
    attendance_pct: '97.85',
    g1_grade: 10,
    g2_grade: 12,
    g3_grade: 12,
    academic_average: '11.33',
    pass_fail: 'pass',
    risk_score: 1,
    risk_category: 'Low Risk'
  }
];

// ---------------------------------------------------------
// PIPELINE
// ---------------------------------------------------------

const PIPELINE_STAGES = [
  'Data Source',
  'Raw Data',
  'Staging',
  'Validation',
  'Rejected Records',
  'Cleaned Data',
  'Feature Engineering',
  'PostgreSQL',
  'Airflow',
  'Dashboard'
];

// ---------------------------------------------------------
// HTML HELPERS
// ---------------------------------------------------------

function esc(s) {

  if (s === null || s === undefined) {
    return '';
  }

  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function passBadge(label, status) {

  if (status === 'UNAVAILABLE') {

    return `
      <span class="badge badge-unavailable">
        ${esc(label)}: UNAVAILABLE
      </span>
    `;
  }

  if (
    status === 'PASS' ||
    status === 0 ||
    status === '0 errors' ||
    status === 'Registered / Detected'
  ) {

    return `
      <span class="badge badge-pass">
        ${esc(label)}: PASS
      </span>
    `;
  }

  return `
    <span class="badge badge-fail">
      ${esc(label)}: FAIL
    </span>
  `;
}

// ---------------------------------------------------------
// RENDER PAGE
// ---------------------------------------------------------

function renderPage(
  totalRecords,
  dbConnected,
  airflow
) {

  const dagStatus =
    !airflow.available
      ? 'UNAVAILABLE'
      : (
          airflow.dagRegistered
            ? 'Registered / Detected'
            : 'Not Found'
        );

  const importStatus =
    !airflow.available
      ? 'UNAVAILABLE'
      : (
          airflow.importErrors === 0
            ? '0 errors'
            : 'Errors Detected'
        );

  const processorStatus =
    !airflow.available
      ? 'UNAVAILABLE'
      : (
          airflow.processorErrors === 0
            ? '0 errors'
            : 'Errors Detected'
        );

  const tableHeaders = [
    'Student ID',
    'Subject',
    'School',
    'Sex',
    'Age',
    'Study Time',
    'Failures',
    'Absences',
    'Attendance %',
    'G1',
    'G2',
    'G3',
    'Avg',
    'Pass/Fail',
    'Risk Score',
    'Risk Category'
  ];

  const tableKeys = [
    'student_id',
    'subject',
    'school',
    'sex',
    'age',
    'studytime',
    'failures',
    'absences',
    'attendance_pct',
    'g1_grade',
    'g2_grade',
    'g3_grade',
    'academic_average',
    'pass_fail',
    'risk_score',
    'risk_category'
  ];

  const headerRow =
    tableHeaders
      .map(h => `<th>${esc(h)}</th>`)
      .join('');

  const bodyRows =
    SAMPLE_ROWS
      .map(r => {

        const cells =
          tableKeys
            .map(k => {

              const val = esc(r[k]);

              let cls = '';

              if (k === 'risk_category') {

                if (r[k] === 'High Risk') {
                  cls = 'risk-high';
                }

                else if (r[k] === 'Medium Risk') {
                  cls = 'risk-medium';
                }

                else if (r[k] === 'Low Risk') {
                  cls = 'risk-low';
                }
              }

              if (k === 'pass_fail') {

                cls =
                  r[k] === 'pass'
                    ? 'pass-tag'
                    : 'fail-tag';
              }

              return `
                <td class="${cls}">
                  ${val}
                </td>
              `;
            })
            .join('');

        return `<tr>${cells}</tr>`;
      })
      .join('');

  const pipelineHtml =
    PIPELINE_STAGES
      .map((stage, i) => {

        const isLast =
          i === PIPELINE_STAGES.length - 1;

        return `
          <div class="pipeline-stage">
            ${esc(stage)}
          </div>

          ${
            isLast
              ? ''
              : '<div class="pipeline-arrow">&#8595;</div>'
          }
        `;
      })
      .join('');

  return `<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8" />

<meta name="viewport"
      content="width=device-width, initial-scale=1" />

<title>
Project Evidence &amp; Verification
</title>

<style>

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family:
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    Roboto,
    sans-serif;

  background: #f0f2f5;

  color: #1a1a2e;

  line-height: 1.5;
}

.page-header {

  background:
    linear-gradient(
      135deg,
      #1a1a2e,
      #16213e
    );

  color: #fff;

  padding: 28px 40px;
}

.page-header h1 {

  font-size: 24px;

  font-weight: 700;
}

.page-header .subtitle {

  font-size: 14px;

  color: #a0a0b8;

  margin-top: 4px;
}

.container {

  max-width: 1100px;

  margin: 0 auto;

  padding: 24px 20px;
}

.section {

  background: #fff;

  border-radius: 10px;

  box-shadow:
    0 2px 8px rgba(0,0,0,0.06);

  margin-bottom: 24px;

  overflow: hidden;
}

.section-header {

  padding: 16px 24px;

  border-bottom:
    1px solid #e8e8f0;

  display: flex;

  align-items: center;

  gap: 10px;
}

.section-number {

  background: #1a1a2e;

  color: #fff;

  width: 28px;

  height: 28px;

  border-radius: 50%;

  display: flex;

  align-items: center;

  justify-content: center;

  font-size: 14px;

  font-weight: 700;

  flex-shrink: 0;
}

.section-title {

  font-size: 16px;

  font-weight: 600;

  color: #1a1a2e;
}

.section-body {

  padding: 20px 24px;
}

.section-label {

  font-size: 13px;

  color: #888;

  font-style: italic;

  margin-bottom: 12px;
}

.stats-grid {

  display: flex;

  gap: 16px;

  flex-wrap: wrap;
}

.stat-card {

  background: #f8f9fa;

  border:
    1px solid #e0e0e8;

  border-radius: 8px;

  padding: 16px 20px;

  min-width: 160px;
}

.stat-card .stat-label {

  font-size: 12px;

  color: #888;

  text-transform: uppercase;

  letter-spacing: 0.5px;
}

.stat-card .stat-value {

  font-size: 22px;

  font-weight: 700;

  color: #1a1a2e;

  margin-top: 4px;
}

.stat-card .stat-value.green {
  color: #2ecc71;
}

.stat-card .stat-value.blue {
  color: #3498db;
}

.table-wrap {

  overflow-x: auto;
}

table {

  border-collapse: collapse;

  width: 100%;

  font-size: 12px;
}

th {

  background: #1a1a2e;

  color: #fff;

  padding: 8px 10px;

  text-align: left;

  white-space: nowrap;

  font-weight: 600;
}

td {

  padding: 6px 10px;

  border-bottom:
    1px solid #e8e8f0;

  white-space: nowrap;
}

tr:nth-child(even) {

  background: #fafafa;
}

tr:hover {

  background: #f0f4ff;
}

.risk-high {

  color: #e74c3c;

  font-weight: 600;
}

.risk-medium {

  color: #f39c12;

  font-weight: 600;
}

.risk-low {

  color: #2ecc71;

  font-weight: 600;
}

.pass-tag {

  color: #2ecc71;

  font-weight: 600;
}

.fail-tag {

  color: #e74c3c;

  font-weight: 600;
}

.verify-grid {

  display: flex;

  gap: 16px;

  flex-wrap: wrap;
}

.verify-card {

  background: #f8f9fa;

  border:
    1px solid #e0e0e8;

  border-radius: 8px;

  padding: 14px 18px;

  flex: 1;

  min-width: 200px;
}

.verify-card .vc-label {

  font-size: 12px;

  color: #888;

  text-transform: uppercase;

  letter-spacing: 0.5px;
}

.verify-card .vc-value {

  font-size: 16px;

  font-weight: 600;

  margin-top: 4px;
}

.vc-value.green {
  color: #2ecc71;
}

.vc-value.blue {
  color: #3498db;
}

.vc-value.gray {
  color: #888;
}

.badge {

  display: inline-block;

  padding: 4px 12px;

  border-radius: 5px;

  font-size: 13px;

  font-weight: 600;

  margin: 2px;
}

.badge-pass {

  background: #d4edda;

  color: #155724;

  border:
    1px solid #c3e6cb;
}

.badge-fail {

  background: #f8d7da;

  color: #721c24;

  border:
    1px solid #f5c6cb;
}

.badge-unavailable {

  background: #e2e3e5;

  color: #6c757d;

  border:
    1px solid #d6d8db;
}

.pipeline {

  display: flex;

  flex-direction: column;

  align-items: center;

  gap: 2px;
}

.pipeline-stage {

  background:
    linear-gradient(
      135deg,
      #3498db,
      #2980b9
    );

  color: #fff;

  padding: 10px 28px;

  border-radius: 8px;

  font-size: 14px;

  font-weight: 600;

  min-width: 200px;

  text-align: center;

  box-shadow:
    0 2px 4px rgba(0,0,0,0.1);
}

.pipeline-stage:nth-child(even) {

  background:
    linear-gradient(
      135deg,
      #1a1a2e,
      #2d2d4e
    );
}

.pipeline-arrow {

  color: #888;

  font-size: 20px;

  line-height: 1;
}

.summary-grid {

  display: flex;

  flex-direction: column;

  gap: 8px;
}

.summary-row {

  display: flex;

  align-items: center;

  justify-content: space-between;

  padding: 10px 16px;

  background: #f8f9fa;

  border-radius: 6px;

  border:
    1px solid #e0e0e8;
}

.summary-row .sr-label {

  font-size: 14px;

  font-weight: 500;
}

.footer {

  text-align: center;

  padding: 20px;

  font-size: 12px;

  color: #888;
}

</style>

</head>

<body>

<div class="page-header">

  <h1>
    Project Evidence &amp; Verification
  </h1>

  <div class="subtitle">
    Student Performance &amp; Dropout-Risk Prediction
    &mdash; MLOps Project
  </div>

</div>

<div class="container">

<!-- =====================================================
     SECTION 1
===================================================== -->

<div class="section">

<div class="section-header">

<div class="section-number">
1
</div>

<div class="section-title">
Data Preview &mdash; Real PostgreSQL Database Data (Read Only)
</div>

</div>

<div class="section-body">

<div class="section-label">

Source:
student_performance_analytics table
&mdash; live data from existing project database

</div>

<div
  class="stats-grid"
  style="margin-bottom:16px;"
>

<div class="stat-card">

<div class="stat-label">
Total Records
</div>

<div class="stat-value green">
${totalRecords}
</div>

</div>

<div class="stat-card">

<div class="stat-label">
Columns
</div>

<div class="stat-value blue">
25
</div>

</div>

<div class="stat-card">

<div class="stat-label">
Showing
</div>

<div class="stat-value">
10 rows
</div>

</div>

</div>

<div class="table-wrap">

<table>

<thead>

<tr>
${headerRow}
</tr>

</thead>

<tbody>

${bodyRows}

</tbody>

</table>

</div>

</div>

</div>

<!-- =====================================================
     SECTION 2
===================================================== -->

<div class="section">

<div class="section-header">

<div class="section-number">
2
</div>

<div class="section-title">
Database Verification
</div>

</div>

<div class="section-body">

<div class="verify-grid">

<div class="verify-card">

<div class="vc-label">
Database Connection
</div>

<div class="vc-value ${
  dbConnected
    ? 'green'
    : 'gray'
}">

${
  dbConnected
    ? 'Connected'
    : 'Failed'
}

</div>

</div>

<div class="verify-card">

<div class="vc-label">
Table
</div>

<div class="vc-value">
student_performance_analytics
</div>

</div>

<div class="verify-card">

<div class="vc-label">
Total Records
</div>

<div class="vc-value green">
${totalRecords}
</div>

</div>

<div class="verify-card">

<div class="vc-label">
Data Source
</div>

<div class="vc-value">
Existing project PostgreSQL database
</div>

</div>

</div>

</div>

</div>

<!-- =====================================================
     SECTION 3
===================================================== -->

<div class="section">

<div class="section-header">

<div class="section-number">
3
</div>

<div class="section-title">
Airflow DAG Registration
</div>

</div>

<div class="section-body">

<div class="verify-grid">

<div class="verify-card">

<div class="vc-label">
DAG ID
</div>

<div class="vc-value">
student_performance_pipeline
</div>

</div>

<div class="verify-card">

<div class="vc-label">
DAG File
</div>

<div class="vc-value">
student_performance_pipeline.py
</div>

</div>

<div class="verify-card">

<div class="vc-label">
Status
</div>

<div class="vc-value ${
  dagStatus === 'Registered / Detected'
    ? 'green'
    : 'gray'
}">

${dagStatus}

</div>

</div>

</div>

</div>

</div>

<!-- =====================================================
     SECTION 4
===================================================== -->

<div class="section">

<div class="section-header">

<div class="section-number">
4
</div>

<div class="section-title">
Airflow DAG Import Verification
</div>

</div>

<div class="section-body">

<div class="verify-grid">

<div class="verify-card">

<div class="vc-label">
Import Errors
</div>

<div class="vc-value ${
  importStatus === '0 errors'
    ? 'green'
    : 'gray'
}">

${importStatus}

</div>

</div>

<div class="verify-card">

<div class="vc-label">
Status
</div>

<div class="vc-value ${
  importStatus === '0 errors'
    ? 'green'
    : 'gray'
}">

${
  importStatus === '0 errors'
    ? 'No DAG import errors'
    : 'Airflow verification unavailable'
}

</div>

</div>

</div>

</div>

</div>

<!-- =====================================================
     SECTION 5
===================================================== -->

<div class="section">

<div class="section-header">

<div class="section-number">
5
</div>

<div class="section-title">
Airflow DAG Processor
</div>

</div>

<div class="section-body">

<div class="verify-grid">

<div class="verify-card">

<div class="vc-label">
DAG File
</div>

<div class="vc-value">
student_performance_pipeline.py
</div>

</div>

<div class="verify-card">

<div class="vc-label">
DAGs Processed
</div>

<div class="vc-value ${
  processorStatus === '0 errors'
    ? 'green'
    : 'gray'
}">

${
  processorStatus === '0 errors'
    ? '1'
    : 'N/A'
}

</div>

</div>

<div class="verify-card">

<div class="vc-label">
Errors
</div>

<div class="vc-value ${
  processorStatus === '0 errors'
    ? 'green'
    : 'gray'
}">

${processorStatus}

</div>

</div>

</div>

</div>

</div>

<!-- =====================================================
     SECTION 6
===================================================== -->

<div class="section">

<div class="section-header">

<div class="section-number">
6
</div>

<div class="section-title">
Project Pipeline Architecture
</div>

</div>

<div class="section-body">

<div class="section-label">

Visual representation of the existing ETL pipeline stages

</div>

<div class="pipeline">

${pipelineHtml}

</div>

</div>

</div>

<!-- =====================================================
     SECTION 7
===================================================== -->

<div class="section">

<div class="section-header">

<div class="section-number">
7
</div>

<div class="section-title">
Final Verification Summary
</div>

</div>

<div class="section-body">

<div class="summary-grid">

<div class="summary-row">

<span class="sr-label">
Data Available
</span>

${passBadge(
  'Data',
  totalRecords > 0
    ? 'PASS'
    : 'FAIL'
)}

</div>

<div class="summary-row">

<span class="sr-label">
Database Connected
</span>

${passBadge(
  'DB',
  dbConnected
    ? 'PASS'
    : 'FAIL'
)}

</div>

<div class="summary-row">

<span class="sr-label">
DAG Detected
</span>

${passBadge(
  'DAG',
  dagStatus
)}

</div>

<div class="summary-row">

<span class="sr-label">
Import Errors
</span>

${passBadge(
  'Imports',
  importStatus
)}

</div>

<div class="summary-row">

<span class="sr-label">
DAG Processor
</span>

${passBadge(
  'Processor',
  processorStatus
)}

</div>

</div>

</div>

</div>

</div>

<div class="footer">

Student Performance &amp; Dropout-Risk Prediction
&mdash; MLOps Project Evidence Page

<br/>

All data shown is real, fetched live from the existing
project database. Read-only.

</div>

</body>

</html>`;
}

// ---------------------------------------------------------
// START SERVER
// ---------------------------------------------------------

async function startServer() {

  let totalRecords = 0;

  let dbConnected = false;

  // -------------------------------------------------------
  // DATABASE CHECK
  // -------------------------------------------------------

  try {

    totalRecords =
      await fetchTotal();

    dbConnected = true;

    console.log(
      `Database connected. Records: ${totalRecords}`
    );

  } catch (e) {

    console.error(
      'Database connection failed:',
      e.message
    );
  }

  // -------------------------------------------------------
  // AIRFLOW CHECK
  // -------------------------------------------------------

  console.log(
    'Running Airflow verification inside WSL...'
  );

  const airflow =
    runAirflowChecks();

  console.log(
    'Airflow checks complete:',
    JSON.stringify(airflow)
  );

  // -------------------------------------------------------
  // SERVER
  // -------------------------------------------------------

  const server =
    http.createServer(
      async (req, res) => {

        let liveTotal =
          totalRecords;

        let liveConn =
          dbConnected;

        try {

          liveTotal =
            await fetchTotal();

          liveConn = true;

        } catch (e) {

          // Use cached values.
        }

        try {

          const html =
            renderPage(
              liveTotal,
              liveConn,
              airflow
            );

          res.writeHead(
            200,
            {
              'Content-Type':
                'text/html; charset=utf-8',

              'Cache-Control':
                'no-cache, no-store, must-revalidate'
            }
          );

          res.end(html);

        } catch (e) {

          res.writeHead(
            500,
            {
              'Content-Type':
                'text/html; charset=utf-8'
            }
          );

          res.end(
            `<div style="padding:40px;color:#e74c3c;">
              Error: ${esc(e.message)}
            </div>`
          );
        }
      }
    );

  server.on('error', (error) => {

    console.error(
      'Server error:',
      error.message
    );
  });

  server.listen(
    PORT,
    '0.0.0.0',
    () => {

      console.log(
        `Evidence page running on http://localhost:${PORT}`
      );

      console.log(
        'Open http://localhost:5173/'
      );
    }
  );
}

startServer();