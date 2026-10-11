# Placement Predict

**Placement Predict** is a Flask-based machine-learning web application for exploring student placement data, preprocessing datasets, comparing classification models, predicting placement outcomes, and generating downloadable reports.

The project is designed as an end-to-end **college ML project**: a user can move from raw dataset → analysis → preprocessing → model training → prediction → report generation from one interface.

---

## What the project does

Placement Predict provides a complete workflow for student placement analysis:

- Upload and activate a CSV or XLSX placement dataset.
- Search, filter, preview, and export dataset records.
- Inspect rows, columns, missing values, duplicates, and generated EDA graphs.
- Configure preprocessing options for missing values, categorical encoding, scaling, and outlier handling.
- Train and compare multiple machine-learning algorithms.
- Select the best model using cross-validation on the training split.
- Evaluate the selected model on an untouched test split.
- Enter student details and predict **Placed / Not Placed**.
- Display a confidence score when the active model supports probability output.
- Save prediction history per user.
- Generate and download PDF prediction reports.
- Use separate Administrator and Student access levels.
- Switch between light and dark interface themes.

---

## Project workflow

```text
Placement Dataset
       │
       ▼
Dataset Explorer
       │
       ▼
Exploratory Data Analysis
       │
       ▼
Data Preprocessing
       │
       ▼
Train / Test Split
       │
       ▼
5-Fold Cross-Validation
       │
       ▼
Model Comparison
       │
       ▼
Best Model
       │
       ▼
Student Placement Prediction
       │
       ├──► Prediction History
       │
       └──► PDF Report
```

---

## Machine-learning models

The training pipeline compares these algorithms:

| Model | Purpose |
| --- | --- |
| Logistic Regression | Linear classification baseline |
| Decision Tree | Rule-based nonlinear classifier |
| Random Forest | Ensemble tree classifier |
| K-Nearest Neighbors | Distance-based classification |
| Gaussian Naive Bayes | Probabilistic classifier |
| Support Vector Machine | Margin-based classification |

The model-selection process uses **5-fold stratified cross-validation** on the training split. The best pipeline is then evaluated once on the held-out test data.

---

## Main modules

### 1. Dashboard
Shows the active dataset, placement rate, model accuracy, prediction count, stream analytics, CGPA analytics, regression visualization, and gradient-descent demonstration.

### 2. Dataset Explorer
Administrators can upload a new dataset. Users can search the preview, filter placement status, and export data as CSV or Excel.

### 3. EDA Insights
Displays dataset structure, missing values, duplicate counts, column information, and generated analysis graphs.

### 4. Preprocessing
Supports numerical and categorical missing-value handling, encoding, feature scaling, outlier configuration, preprocessing preview, and clean CSV export.

### 5. Model Training
Trains several ML algorithms and presents a model leaderboard based on cross-validation accuracy.

### 6. Placement Predictor
Builds the input form dynamically from the model feature schema and returns the predicted placement result.

### 7. Prediction History
Stores and displays previous prediction records for the signed-in user. Administrators can view the complete history.

### 8. Reports
Stores generated prediction PDFs and provides a searchable download interface.

---

## Technology stack

### Backend
- Python
- Flask
- Flask-WTF / CSRF protection
- Werkzeug password hashing

### Machine Learning
- Pandas
- NumPy
- Scikit-learn
- Joblib / Pickle model artifacts

### Visualization
- Chart.js
- Matplotlib / generated EDA graphs

### Frontend
- HTML5
- CSS3
- Bootstrap 5
- JavaScript
- Font Awesome

### Reports and data
- ReportLab / PDF generation
- OpenPyXL for Excel support
- CSV and XLSX datasets

---

## Project structure

```text
Placment-predict/
│
├── app.py                      # Flask application and routes
├── config.py                   # Application configuration
├── requirements.txt            # Python dependencies
│
├── dataset/
│   ├── placement_predict_50k_Dataset.csv
│   └── placement_predict_50k_Dataset.xlsx
│
├── prediction/
│   ├── eda.py                  # EDA graph generation
│   ├── evaluation.py           # Model evaluation helpers
│   ├── predict.py              # Prediction loader/inference
│   ├── report_generator.py     # PDF report generation
│   └── train_model.py          # Training and model selection
│
├── saved_models/               # Existing model artifacts
├── reports/                    # Generated analytical assets
│
├── static/
│   ├── css/                    # UI styles
│   ├── js/                     # Frontend behavior
│   └── graphs/                 # Generated graph images
│
├── templates/                  # Flask/Jinja pages
│
├── instance/                   # Runtime users/history/state (ignored)
└── uploads/                    # Uploaded datasets (ignored)
```

---

## Run the project locally

### 1. Clone the repository

```bash
git clone https://github.com/void-tech-shiv/Placment-predict.git
cd Placment-predict
```

### 2. Create a virtual environment (recommended)

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure a secret key

**Windows PowerShell**

```powershell
$env:SECRET_KEY="replace-with-a-long-random-secret"
```

**Linux / macOS**

```bash
export SECRET_KEY="replace-with-a-long-random-secret"
```

### 5. Start Flask

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

## User roles

### Administrator
The first account created on a fresh installation becomes the Administrator.

Administrator permissions include:
- uploading/replacing the active dataset;
- running preprocessing;
- retraining shared ML models;
- viewing all prediction history and reports.

### Student
Later registered accounts become Student users.

Student users can:
- view analytics;
- explore available data;
- run placement predictions;
- view their prediction history;
- download their prediction reports.

---

## Optional administrator bootstrap

Instead of relying on the first registration, an administrator can be created from environment variables.

**Windows PowerShell**

```powershell
$env:INITIAL_ADMIN_EMAIL="admin@example.com"
$env:INITIAL_ADMIN_PASSWORD="change-this-password"
$env:INITIAL_ADMIN_NAME="Project Admin"
python app.py
```

**Linux / macOS**

```bash
export INITIAL_ADMIN_EMAIL="admin@example.com"
export INITIAL_ADMIN_PASSWORD="change-this-password"
export INITIAL_ADMIN_NAME="Project Admin"
python app.py
```

---

## Training from the terminal

The model trainer can also run independently from the web interface:

```bash
python prediction/train_model.py --dataset dataset/placement_predict_50k_Dataset.csv
```

The trainer:

1. reads CSV/XLSX data;
2. identifies the placement target;
3. separates features and target;
4. splits training and test data before fitting preprocessing;
5. imputes missing values;
6. scales numeric features;
7. one-hot encodes categorical features;
8. compares candidate models using cross-validation;
9. trains the best model on the training split;
10. evaluates it on the untouched test split;
11. saves model artifacts for the web predictor.

---

## Runtime and security notes

- Passwords are stored as hashes, not plain text.
- Login does not automatically create unknown users.
- Public users cannot choose the Administrator role during registration.
- CSRF protection is enabled for state-changing forms and requests.
- Uploaded filenames are sanitized and file types are checked server-side.
- Session cookies use HttpOnly and SameSite protections.
- Mutable application data is stored under `instance/` and is ignored by Git.
- Generated user reports and prediction-history files are not intended to be committed.

For a classroom/demo deployment, the JSON runtime store is sufficient. For a multi-user production deployment, replace it with SQLite or PostgreSQL.

---

## Suggested classroom demo

A simple demonstration sequence is:

1. Sign in as Administrator.
2. Open **Dataset Explorer** and show the active dataset.
3. Open **EDA Insights** and explain missing values / graphs.
4. Open **Preprocessing** and explain encoding and scaling.
5. Open **Model Training** and show the model leaderboard.
6. Open **Placement Predictor** and enter a sample student profile.
7. Show the predicted result and confidence score.
8. Open **Prediction History**.
9. Download the generated PDF from **Reports**.

This demonstrates the complete ML lifecycle inside one project.

---

## Continuous validation

GitHub Actions installs the project dependencies and runs syntax/template/JavaScript checks on changes before they are merged.

---

## Project name

**Placement Predict — Student Placement Prediction & Analytics System**
