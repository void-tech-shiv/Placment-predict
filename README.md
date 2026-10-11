# PlacementAI

Flask-based placement prediction dashboard with dataset exploration, preprocessing, EDA, model comparison, prediction history and PDF reports.

## Security and runtime changes

Runtime user data, prediction history, uploaded datasets and generated reports are no longer intended to be committed to Git. The application stores mutable state under `instance/` and `uploads/`.

The first account registered on a fresh installation becomes the Administrator. Later registrations become Student accounts. You can also bootstrap an administrator with environment variables:

```bash
export SECRET_KEY="replace-with-a-long-random-secret"
export INITIAL_ADMIN_EMAIL="admin@example.com"
export INITIAL_ADMIN_PASSWORD="change-this-password"
export INITIAL_ADMIN_NAME="Project Admin"
```

On Windows PowerShell:

```powershell
$env:SECRET_KEY="replace-with-a-long-random-secret"
$env:INITIAL_ADMIN_EMAIL="admin@example.com"
$env:INITIAL_ADMIN_PASSWORD="change-this-password"
$env:INITIAL_ADMIN_NAME="Project Admin"
```

## Run locally

```bash
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## ML workflow

1. Sign in as Administrator.
2. Upload a CSV or XLSX dataset from **Dataset & Search**.
3. Optionally inspect preprocessing and EDA.
4. Open **Model Leaderboard** and train models.
5. The trainer selects a model using 5-fold cross-validation on the training split and reports performance on an untouched test split.
6. Use **Predict Placement** for predictions and PDF reports.

The training command can also be run directly:

```bash
python prediction/train_model.py --dataset path/to/dataset.csv
```

## Important repository hygiene

Older commits may still contain data that was previously committed. Removing files in a new commit does not erase them from Git history. If any exposed email/user record was real, rotate credentials where relevant and rewrite repository history before treating the repository as clean.
