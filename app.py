import json
import os
import secrets
import subprocess
import sys
import threading
import traceback
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

import numpy as np
import pandas as pd
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from flask_wtf.csrf import CSRFProtect
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder, MinMaxScaler, RobustScaler, StandardScaler
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from prediction.predict import Predictor
from prediction.report_generator import ReportGenerator

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DATASET_FOLDER = BASE_DIR / "dataset"
UPLOAD_FOLDER = BASE_DIR / "uploads" / "datasets"
REPORT_FOLDER = BASE_DIR / "reports"
MODEL_FOLDER = BASE_DIR / "saved_models"
GRAPH_FOLDER = BASE_DIR / "static" / "graphs"

for directory in (INSTANCE_DIR, DATASET_FOLDER, UPLOAD_FOLDER, REPORT_FOLDER, MODEL_FOLDER, GRAPH_FOLDER):
    directory.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=20 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
    WTF_CSRF_TIME_LIMIT=None,
)
csrf = CSRFProtect(app)

if not os.environ.get("SECRET_KEY"):
    print("WARNING: SECRET_KEY is not set. A temporary key is being used for this run.")

USERS_FILE = INSTANCE_DIR / "users.json"
HISTORY_FILE = INSTANCE_DIR / "prediction_history.json"
ACTIVE_DATASET_FILE = INSTANCE_DIR / "active_dataset.json"
PREPROCESSED_FILE = INSTANCE_DIR / "preprocessed_dataset.csv"
ALLOWED_DATASET_EXTENSIONS = {"csv", "xlsx"}
_json_lock = threading.Lock()
_dataset_cache = {"path": None, "mtime": None, "df": None}


def _atomic_json_write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    os.replace(temp, path)


def _load_json(path: Path, default):
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
    except (OSError, json.JSONDecodeError):
        traceback.print_exc()
    return default


def init_runtime_state():
    if not USERS_FILE.exists():
        _atomic_json_write(USERS_FILE, [])
    if not HISTORY_FILE.exists():
        _atomic_json_write(HISTORY_FILE, [])
    admin_email = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip().lower()
    admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
    admin_name = os.environ.get("INITIAL_ADMIN_NAME", "Project Admin").strip() or "Project Admin"
    if admin_email and admin_password:
        with _json_lock:
            users = _load_json(USERS_FILE, [])
            if not any(u.get("email", "").lower() == admin_email for u in users):
                users.append({"email": admin_email, "name": admin_name, "password": generate_password_hash(admin_password), "role": "Admin"})
                _atomic_json_write(USERS_FILE, users)


init_runtime_state()


def load_users():
    return _load_json(USERS_FILE, [])


def save_user(user_data):
    with _json_lock:
        users = load_users()
        users.append(user_data)
        _atomic_json_write(USERS_FILE, users)


def verify_user_password(stored_password, provided_password):
    if not stored_password or not provided_password:
        return False
    try:
        return check_password_hash(stored_password, provided_password)
    except (ValueError, TypeError):
        return False


def load_history():
    return _load_json(HISTORY_FILE, [])


def save_prediction_history(student_data, prediction, confidence, report_name):
    user = session.get("user", {})
    label = "Placed" if str(prediction).strip().lower().startswith("placed") else "Not Placed"
    with _json_lock:
        history = load_history()
        next_id = max([int(item.get("id", 0)) for item in history] or [0]) + 1
        history.append({
            "id": next_id,
            "date": datetime.now().isoformat(timespec="seconds"),
            "student_name": student_data.get("Name") or student_data.get("Student_Name") or "Student",
            "student": student_data,
            "prediction": prediction,
            "prediction_label": label,
            "confidence": confidence,
            "report": report_name,
            "user_email": user.get("email", ""),
        })
        _atomic_json_write(HISTORY_FILE, history)


def current_user_history():
    user = session.get("user", {})
    history = load_history()
    if user.get("role") == "Admin":
        return history
    email = user.get("email", "")
    return [item for item in history if item.get("user_email") in ("", email)]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            flash("Please sign in to continue.", "info")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("user", {}).get("role") != "Admin":
            message = "Administrator access is required for this action."
            if request.path.startswith("/api/") or request.is_json:
                return jsonify({"success": False, "error": message}), 403
            flash(message, "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


def allowed_dataset(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_DATASET_EXTENSIONS


def set_active_dataset(path: Path):
    resolved = path.resolve()
    _atomic_json_write(ACTIVE_DATASET_FILE, {"path": str(resolved)})
    clear_dataset_cache()


def get_dataset_path():
    state = _load_json(ACTIVE_DATASET_FILE, {})
    active = state.get("path")
    if active:
        active_path = Path(active)
        if active_path.exists() and active_path.suffix.lower().lstrip(".") in ALLOWED_DATASET_EXTENSIONS:
            return active_path
    preferred = [DATASET_FOLDER / "placement_predict_50k_Dataset.xlsx", DATASET_FOLDER / "placement_predict_50k_Dataset.csv"]
    for candidate in preferred:
        if candidate.exists():
            set_active_dataset(candidate)
            return candidate
    candidates = sorted([p for p in DATASET_FOLDER.iterdir() if p.is_file() and p.suffix.lower().lstrip(".") in ALLOWED_DATASET_EXTENSIONS and not p.name.startswith("preprocessed_")], key=lambda p: p.stat().st_mtime, reverse=True)
    if candidates:
        set_active_dataset(candidates[0])
        return candidates[0]
    return None


def clear_dataset_cache():
    global _dataset_cache
    _dataset_cache = {"path": None, "mtime": None, "df": None}


def load_cached_dataset():
    global _dataset_cache
    dataset_path = get_dataset_path()
    if not dataset_path:
        return None, None
    try:
        mtime = dataset_path.stat().st_mtime
        if _dataset_cache["path"] == str(dataset_path) and _dataset_cache["mtime"] == mtime and _dataset_cache["df"] is not None:
            return dataset_path, _dataset_cache["df"]
        df = pd.read_csv(dataset_path) if dataset_path.suffix.lower() == ".csv" else pd.read_excel(dataset_path, engine="openpyxl")
        _dataset_cache = {"path": str(dataset_path), "mtime": mtime, "df": df}
        return dataset_path, df
    except Exception:
        traceback.print_exc()
        return dataset_path, None


def normalize_placement(value):
    normalized = str(value).strip().lower()
    if normalized in {"1", "1.0", "placed", "yes", "true", "selected"}:
        return True
    if normalized in {"0", "0.0", "not placed", "not_placed", "no", "false", "rejected"}:
        return False
    return None


def load_predictor():
    try:
        return Predictor()
    except Exception as exc:
        print("Predictor loading warning:", exc)
        return None


predictor = load_predictor()
report_generator = ReportGenerator()


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session and request.method == "GET":
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Please enter both email address and password.", "danger")
            return redirect(url_for("login"))
        user_match = next((u for u in load_users() if u.get("email", "").lower() == email), None)
        if not user_match or not verify_user_password(user_match.get("password"), password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))
        session.clear()
        session.permanent = True
        session["user"] = {"name": user_match.get("name", "User"), "email": user_match.get("email", email), "role": user_match.get("role", "Student")}
        flash(f"Welcome back, {session['user']['name']}!", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" in session and request.method == "GET":
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            flash("Name, email and a password of at least 6 characters are required.", "danger")
            return redirect(url_for("register"))
        users = load_users()
        if any(u.get("email", "").lower() == email for u in users):
            flash("An account with this email already exists.", "danger")
            return redirect(url_for("register"))
        role = "Admin" if not users else "Student"
        save_user({"name": name, "email": email, "password": generate_password_hash(password), "role": role})
        session.clear()
        session.permanent = True
        session["user"] = {"name": name, "email": email, "role": role}
        flash("Account created. As the first account, you were assigned Administrator access." if role == "Admin" else "Account created successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))


def _numeric_pair(df, feature_col=None, target_col=None):
    if df is None or df.empty:
        return None
    num_cols = list(df.select_dtypes(include=["number"]).columns)
    if len(num_cols) < 2:
        return None
    feature_col = feature_col if feature_col in num_cols else ("CGPA" if "CGPA" in num_cols else num_cols[0])
    targets = ["PlacementStatus", "Salary Package", "AptitudeTestScore", "Placed"]
    target_col = target_col if target_col in num_cols else next((c for c in targets if c in num_cols and c != feature_col), None)
    if not target_col:
        target_col = next((c for c in reversed(num_cols) if c != feature_col), None)
    if not target_col:
        return None
    valid = df[[feature_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid) < 5:
        return None
    return feature_col, target_col, valid[feature_col].astype(float).to_numpy(), valid[target_col].astype(float).to_numpy()


def compute_regression_analytics(df, feature_col=None, target_col=None):
    pair = _numeric_pair(df, feature_col, target_col)
    if not pair:
        return {}
    feature_col, target_col, x_vals, y_vals = pair
    try:
        X = x_vals.reshape(-1, 1)
        model = LinearRegression().fit(X, y_vals)
        y_pred = model.predict(X)
        w, b = float(model.coef_[0]), float(model.intercept_)
        r2, mse = float(r2_score(y_vals, y_pred)), float(mean_squared_error(y_vals, y_pred))
        rmse, mae = float(np.sqrt(mse)), float(mean_absolute_error(y_vals, y_pred))
        sample_idx = np.linspace(0, len(x_vals) - 1, min(len(x_vals), 250), dtype=int)
        scatter_x, scatter_y, scatter_pred = x_vals[sample_idx], y_vals[sample_idx], y_pred[sample_idx]
        residual_counts, bin_edges = np.histogram(scatter_y - scatter_pred, bins=8)
        x_min, x_max = float(np.min(x_vals)), float(np.max(x_vals))
        return {
            "feature_col": feature_col, "target_col": target_col, "slope": round(w, 4), "intercept": round(b, 4),
            "r2": round(r2, 4), "mse": round(mse, 4), "rmse": round(rmse, 4), "mae": round(mae, 4),
            "scatter": [{"x": round(float(x), 2), "y": round(float(y), 2)} for x, y in zip(scatter_x, scatter_y)],
            "line": [{"x": round(x_min, 2), "y": round(float(w * x_min + b), 2)}, {"x": round(x_max, 2), "y": round(float(w * x_max + b), 2)}],
            "residual_labels": [f"{bin_edges[i]:.1f} to {bin_edges[i + 1]:.1f}" for i in range(len(bin_edges) - 1)],
            "residual_counts": residual_counts.tolist(), "equation": f"y = {w:.4f} · x + ({b:.4f})",
        }
    except Exception:
        traceback.print_exc()
        return {}


def compute_gd_simulation(df, feature_col=None, target_col=None, learning_rate=0.05, epochs=50, w_init=0.0, b_init=0.0, gd_type="batch"):
    pair = _numeric_pair(df, feature_col, target_col)
    if not pair:
        return {"scatter": [], "history": [], "learning_rate": learning_rate, "epochs": epochs, "gd_type": gd_type}
    feature_col, target_col, x_raw, y_raw = pair
    epochs = max(1, min(int(epochs), 500))
    learning_rate = max(0.000001, min(float(learning_rate), 1.0))
    gd_type = gd_type if gd_type in {"batch", "sgd"} else "batch"
    x_min, x_max, y_min, y_max = float(np.min(x_raw)), float(np.max(x_raw)), float(np.min(y_raw)), float(np.max(y_raw))
    sx, sy = (x_max - x_min) or 1.0, (y_max - y_min) or 1.0
    x_norm, y_norm = (x_raw - x_min) / sx, (y_raw - y_min) / sy
    w, b, history = float(w_init), float(b_init), []
    rng = np.random.default_rng(42)
    for epoch in range(1, epochs + 1):
        if gd_type == "sgd":
            for idx in rng.permutation(len(x_norm)):
                err_i = (w * x_norm[idx] + b) - y_norm[idx]
                w -= learning_rate * err_i * x_norm[idx]
                b -= learning_rate * err_i
        y_hat = w * x_norm + b
        err = y_hat - y_norm
        cost, dw, db = float(np.mean(err**2) / 2.0), float(np.mean(err * x_norm)), float(np.mean(err))
        if gd_type == "batch":
            w -= learning_rate * dw
            b -= learning_rate * db
        slope_orig = w * (sy / sx)
        intercept_orig = b * sy + y_min - slope_orig * x_min
        history.append({"epoch": epoch, "w_norm": round(w, 4), "b_norm": round(b, 4), "w_orig": round(slope_orig, 4), "b_orig": round(intercept_orig, 4), "cost": round(cost, 6), "dw": round(dw, 5), "db": round(db, 5), "line": [{"x": round(x_min, 2), "y": round(float(slope_orig * x_min + intercept_orig), 2)}, {"x": round(x_max, 2), "y": round(float(slope_orig * x_max + intercept_orig), 2)}]})
    sample_idx = np.linspace(0, len(x_raw) - 1, min(len(x_raw), 200), dtype=int)
    scatter = [{"x": round(float(x_raw[i]), 2), "y": round(float(y_raw[i]), 2)} for i in sample_idx]
    return {"scatter": scatter, "history": history, "learning_rate": learning_rate, "epochs": epochs, "gd_type": gd_type, "feature_col": feature_col, "target_col": target_col}


@app.route("/")
@login_required
def dashboard():
    dataset_path, df = load_cached_dataset()
    dataset_name = dataset_path.name if dataset_path else "No Dataset Loaded"
    total_students = len(df) if df is not None else 0
    placed_students = not_placed = 0
    placement_rate = avg_cgpa = 0.0
    stream_analytics, cgpa_analytics, numeric_columns = {}, {}, []
    if df is not None and not df.empty:
        numeric_columns = list(df.select_dtypes(include=["number"]).columns)
        status_col = next((c for c in ["PlacementStatus", "Placed", "Status", "placement_status"] if c in df.columns), None)
        if status_col:
            statuses = df[status_col].map(normalize_placement)
            placed_students = int((statuses == True).sum())
            not_placed = int((statuses == False).sum())
            counted = placed_students + not_placed
            placement_rate = round(placed_students / counted * 100, 1) if counted else 0.0
            if "Stream" in df.columns:
                temp = pd.DataFrame({"Stream": df["Stream"].astype(str), "placed": statuses})
                temp = temp[temp["placed"].notna()]
                for stream_name, group in temp.groupby("Stream"):
                    total = len(group); placed_count = int((group["placed"] == True).sum())
                    stream_analytics[str(stream_name)] = {"total": total, "placed": placed_count, "rate": round(placed_count / total * 100, 1) if total else 0.0}
        cgpa_col = next((c for c in ["CGPA", "cgpa", "GPA", "gpa"] if c in df.columns), None)
        if cgpa_col:
            avg_cgpa = round(float(pd.to_numeric(df[cgpa_col], errors="coerce").mean()), 2)
            if status_col:
                temp = pd.DataFrame({"cgpa": pd.to_numeric(df[cgpa_col], errors="coerce"), "placed": df[status_col].map(normalize_placement)}).dropna()
                temp["bin"] = pd.cut(temp["cgpa"], bins=[0,6,7,8,9,10], labels=["< 6.0","6.0 - 7.0","7.0 - 8.0","8.0 - 9.0","9.0 - 10.0"], include_lowest=True)
                for label, group in temp.groupby("bin", observed=False):
                    total = len(group); placed_count = int((group["placed"] == True).sum())
                    cgpa_analytics[str(label)] = {"total": total, "placed": placed_count, "rate": round(placed_count / total * 100, 1) if total else 0.0}
    accuracies = _load_json(MODEL_FOLDER / "accuracy.json", {})
    best_model = max(accuracies, key=accuracies.get) if accuracies else "Not trained"
    best_accuracy = float(accuracies.get(best_model, 0.0)) if accuracies else 0.0
    history = current_user_history()
    return render_template("dashboard.html", dataset_name=dataset_name, total_students=total_students, placed_students=placed_students, not_placed=not_placed, placement_rate=placement_rate, avg_cgpa=avg_cgpa, accuracies=accuracies, accuracy=best_accuracy, best_model=best_model, total_models=len(accuracies), total_predictions=len(history), recent_predictions=list(reversed(history))[:10], stream_analytics=stream_analytics, cgpa_analytics=cgpa_analytics, numeric_columns=numeric_columns, regression_data=compute_regression_analytics(df), gd_sim_data=compute_gd_simulation(df))


@app.route("/api/regression_analytics", methods=["POST"])
@login_required
def api_regression_analytics():
    data = request.get_json(silent=True) or {}; _, df = load_cached_dataset()
    result = compute_regression_analytics(df, data.get("feature_col"), data.get("target_col"))
    return jsonify({"success": True, "data": result}) if result else (jsonify({"success": False, "error": "Choose two valid numerical columns."}), 400)


@app.route("/api/gradient_descent_sim", methods=["POST"])
@login_required
def api_gradient_descent_sim():
    data = request.get_json(silent=True) or {}; _, df = load_cached_dataset()
    try:
        result = compute_gd_simulation(df, data.get("feature_col"), data.get("target_col"), float(data.get("learning_rate", 0.05)), int(data.get("epochs", 50)), float(data.get("w_init", 0.0)), float(data.get("b_init", 0.0)), str(data.get("gd_type", "batch")))
        return jsonify({"success": True, "data": result})
    except (TypeError, ValueError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload_dataset():
    if request.method == "GET":
        return redirect(url_for("dataset_preview"))
    if session.get("user", {}).get("role") != "Admin":
        flash("Only an administrator can replace the shared dataset.", "danger")
        return redirect(request.referrer or url_for("dataset_preview"))
    file = request.files.get("dataset")
    if not file or not file.filename:
        flash("Please select a CSV or XLSX dataset.", "danger"); return redirect(request.referrer or url_for("dataset_preview"))
    if not allowed_dataset(file.filename):
        flash("Unsupported file type. Only .csv and .xlsx are allowed.", "danger"); return redirect(request.referrer or url_for("dataset_preview"))
    original = secure_filename(file.filename); suffix = Path(original).suffix.lower()
    saved_name = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}{suffix}"; save_path = UPLOAD_FOLDER / saved_name
    file.save(save_path)
    try:
        pd.read_csv(save_path, nrows=5) if suffix == ".csv" else pd.read_excel(save_path, nrows=5, engine="openpyxl")
    except Exception as exc:
        save_path.unlink(missing_ok=True); flash(f"The uploaded file could not be read as a dataset: {exc}", "danger"); return redirect(request.referrer or url_for("dataset_preview"))
    set_active_dataset(save_path); PREPROCESSED_FILE.unlink(missing_ok=True)
    flash(f"Dataset '{original}' is now active.", "success")
    return redirect(url_for("dashboard" if request.form.get("redirect_to") == "dashboard" else "dataset_preview"))


@app.route("/dataset")
@login_required
def dataset_preview():
    dataset_path, df = load_cached_dataset()
    if dataset_path is None or df is None:
        return render_template("upload.html", columns=[], rows_data=[], total_count=0, dataset_name=None)
    preview = df.head(150).replace({np.nan: "-"})
    return render_template("upload.html", dataset_name=dataset_path.name, columns=list(df.columns), rows_data=preview.to_dict(orient="records"), total_count=len(df))


@app.route("/export_csv")
@login_required
def export_csv():
    _, df = load_cached_dataset()
    if df is None:
        flash("No active dataset to export.", "danger"); return redirect(url_for("dataset_preview"))
    export_path = INSTANCE_DIR / "placement_dataset_export.csv"; df.to_csv(export_path, index=False)
    return send_file(export_path, as_attachment=True, download_name="placement_dataset.csv")


@app.route("/export_excel")
@login_required
def export_excel():
    _, df = load_cached_dataset()
    if df is None:
        flash("No active dataset to export.", "danger"); return redirect(url_for("dataset_preview"))
    export_path = INSTANCE_DIR / "placement_dataset_export.xlsx"; df.to_excel(export_path, index=False)
    return send_file(export_path, as_attachment=True, download_name="placement_dataset.xlsx")


@app.route("/preprocessing")
@login_required
def preprocessing():
    dataset_path, df = load_cached_dataset()
    if dataset_path is None or df is None:
        flash("No active dataset found.", "warning"); return redirect(url_for("dataset_preview"))
    total_rows, total_cols = df.shape; num_cols = list(df.select_dtypes(include=["number"]).columns); cat_cols = list(df.select_dtypes(exclude=["number"]).columns)
    missing_info = [{"column": col, "type": "Numerical" if col in num_cols else "Categorical", "missing_count": int(df[col].isna().sum()), "missing_pct": round(float(df[col].isna().mean() * 100), 2)} for col in df.columns]
    num_stats = []
    for col in num_cols:
        series = pd.to_numeric(df[col], errors="coerce"); q1, q3 = series.quantile(0.25), series.quantile(0.75); iqr = q3 - q1
        num_stats.append({"column": col, "mean": round(float(series.mean()), 2) if series.notna().any() else 0, "std": round(float(series.std()), 2) if series.notna().sum() > 1 else 0, "min": round(float(series.min()), 2) if series.notna().any() else 0, "max": round(float(series.max()), 2) if series.notna().any() else 0, "outliers": int(((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum())})
    cat_stats = [{"column": col, "unique_count": int(df[col].nunique(dropna=True)), "sample_values": [str(v) for v in df[col].dropna().astype(str).unique()[:5]]} for col in cat_cols]
    return render_template("preprocessing.html", dataset_name=dataset_path.name, total_rows=total_rows, total_cols=total_cols, missing_info=missing_info, total_missing=sum(item["missing_count"] for item in missing_info), num_stats=num_stats, cat_stats=cat_stats, preprocessed_exists=PREPROCESSED_FILE.exists())


@app.route("/api/preprocess", methods=["POST"])
@admin_required
def api_preprocess():
    _, source_df = load_cached_dataset()
    if source_df is None:
        return jsonify({"success": False, "error": "No active dataset found."}), 400
    data = request.get_json(silent=True) or {}; num_impute = data.get("impute_num", "median"); cat_impute = data.get("impute_cat", "mode"); encoding_type = data.get("encoding", "label"); scaler_type = data.get("scaling", "minmax"); outlier_action = data.get("outliers", "iqr_clip")
    if num_impute not in {"median","mean","zero"} or cat_impute not in {"mode","missing"} or encoding_type not in {"label","onehot"} or scaler_type not in {"minmax","standard","robust","none"}:
        return jsonify({"success": False, "error": "Invalid preprocessing option."}), 400
    df = source_df.copy(); orig_rows, orig_cols = df.shape; steps = []
    id_cols = [c for c in ["StudentID","Salary Package","IsAnomaly"] if c in df.columns]
    if id_cols: df.drop(columns=id_cols, inplace=True); steps.append(f"Removed non-predictive columns: {', '.join(id_cols)}.")
    num_cols = list(df.select_dtypes(include=["number"]).columns); cat_cols = list(df.select_dtypes(exclude=["number"]).columns)
    for col in num_cols:
        if df[col].isna().any():
            fill = 0 if num_impute == "zero" else (df[col].mean() if num_impute == "mean" else df[col].median()); df[col] = df[col].fillna(fill)
    steps.append(f"Imputed numerical values using {num_impute}.")
    for col in cat_cols:
        if df[col].isna().any():
            if cat_impute == "missing": fill = "Unknown"
            else:
                mode = df[col].mode(dropna=True); fill = str(mode.iloc[0]) if not mode.empty else "Unknown"
            df[col] = df[col].fillna(fill)
    steps.append(f"Imputed categorical values using {cat_impute}.")
    target_col = next((c for c in ["PlacementStatus","Placed"] if c in df.columns), None)
    if outlier_action == "iqr_clip":
        clipped = 0
        for col in num_cols:
            if col == target_col or col not in df.columns: continue
            q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75); iqr = q3 - q1; low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr; mask = (df[col] < low) | (df[col] > high); clipped += int(mask.sum())
            if mask.any(): df[col] = df[col].clip(low, high)
        steps.append(f"Clipped {clipped} outlier values using IQR boundaries.")
    cat_cols = [c for c in cat_cols if c in df.columns and c != target_col]
    if encoding_type == "label":
        for col in cat_cols: df[col] = LabelEncoder().fit_transform(df[col].astype(str))
        steps.append(f"Label encoded {len(cat_cols)} categorical feature(s).")
    else:
        df = pd.get_dummies(df, columns=cat_cols, drop_first=False, dtype=int); steps.append("Applied one-hot encoding to categorical features.")
    features = [c for c in df.columns if c != target_col]
    if scaler_type != "none" and features:
        scaler = {"minmax": MinMaxScaler(), "standard": StandardScaler(), "robust": RobustScaler()}[scaler_type]; df[features] = scaler.fit_transform(df[features]); steps.append(f"Applied {scaler.__class__.__name__} to feature columns.")
    df.to_csv(PREPROCESSED_FILE, index=False); preview = df.head(8).replace([np.inf,-np.inf], np.nan).where(pd.notna(df.head(8)), None)
    return jsonify({"success": True, "message": "Preprocessing completed.", "original_shape": [orig_rows,orig_cols], "preprocessed_shape": list(df.shape), "steps": steps, "preview_columns": list(df.columns), "preview_rows": preview.to_dict(orient="records")})


@app.route("/download_preprocessed")
@login_required
def download_preprocessed():
    if not PREPROCESSED_FILE.exists():
        flash("Run the preprocessing pipeline first.", "warning"); return redirect(url_for("preprocessing"))
    return send_file(PREPROCESSED_FILE, as_attachment=True, download_name="preprocessed_placement_dataset.csv")


@app.route("/eda")
@login_required
def eda():
    dataset_path, df = load_cached_dataset()
    if dataset_path is None or df is None:
        flash("Dataset not found.", "danger"); return redirect(url_for("dataset_preview"))
    column_info = [{"name": col, "dtype": str(df[col].dtype), "missing": int(df[col].isna().sum()), "unique": int(df[col].nunique(dropna=True))} for col in df.columns]
    graphs = sorted([p.name for p in GRAPH_FOLDER.iterdir() if p.suffix.lower() in {".png",".jpg",".jpeg",".webp"}])
    return render_template("eda.html", dataset_name=dataset_path.name, rows=len(df), columns=len(df.columns), missing=int(df.isna().sum().sum()), duplicates=int(df.duplicated().sum()), numerical=list(df.select_dtypes(include=["number"]).columns), categorical=list(df.select_dtypes(exclude=["number"]).columns), column_info=column_info, graphs=graphs, graph_count=len(graphs))


@app.route("/train")
@login_required
def train():
    accuracies = _load_json(MODEL_FOLDER / "accuracy.json", {}); best_model = max(accuracies, key=accuracies.get) if accuracies else None
    return render_template("train.html", accuracy=accuracies, accuracies=accuracies, best_model=best_model, best_accuracy=accuracies.get(best_model, 0) if best_model else 0)


@app.route("/start_training", methods=["POST"])
@admin_required
def start_training():
    dataset_path = get_dataset_path()
    if not dataset_path: return jsonify({"success": False, "error": "No active dataset found."}), 400
    try:
        script = BASE_DIR / "prediction" / "train_model.py"; subprocess.run([sys.executable, str(script), "--dataset", str(dataset_path)], cwd=str(BASE_DIR), check=True, timeout=900)
        global predictor; predictor = load_predictor(); accuracies = _load_json(MODEL_FOLDER / "accuracy.json", {}); best_model = max(accuracies, key=accuracies.get) if accuracies else None
        return jsonify({"success": True, "message": "Training completed successfully.", "accuracies": accuracies, "best_model": best_model, "best_accuracy": accuracies.get(best_model, 0) if best_model else 0})
    except subprocess.TimeoutExpired: return jsonify({"success": False, "error": "Training timed out."}), 504
    except subprocess.CalledProcessError as exc: return jsonify({"success": False, "error": f"Training failed with exit code {exc.returncode}."}), 500
    except Exception as exc: traceback.print_exc(); return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/prediction")
@login_required
def prediction():
    global predictor
    if predictor is None: predictor = load_predictor()
    if predictor is None: return render_template("prediction.html", feature_columns=[], feature_schema={}, error="Model not loaded. Ask an administrator to train the model first.")
    return render_template("prediction.html", feature_columns=predictor.get_feature_columns(), feature_schema=predictor.get_feature_schema())


@app.route("/predict", methods=["POST"])
@login_required
def predict():
    global predictor
    if predictor is None: predictor = load_predictor()
    if predictor is None: flash("Prediction model is unavailable. Train the model first.", "danger"); return redirect(url_for("prediction"))
    try:
        student_data = request.form.to_dict(); student_data.pop("csrf_token", None); result = predictor.predict(student_data); prediction_result = result["prediction"]; confidence = result.get("confidence")
        filename, _ = report_generator.generate_report(student_data, prediction_result, confidence); save_prediction_history(student_data, prediction_result, confidence, filename); session["last_report"] = filename
        return render_template("prediction.html", feature_columns=predictor.get_feature_columns(), feature_schema=predictor.get_feature_schema(), prediction=prediction_result, confidence=confidence, report_file=filename, student_input=student_data)
    except Exception as exc: traceback.print_exc(); flash(f"Prediction error: {exc}", "danger"); return redirect(url_for("prediction"))


@app.route("/download_report")
@login_required
def download_report():
    filename = session.get("last_report")
    if not filename: flash("No recent report is available.", "warning"); return redirect(url_for("prediction"))
    return _send_authorized_report(filename)


@app.route("/history")
@login_required
def history():
    return render_template("history.html", history=list(reversed(current_user_history())))


def _report_is_authorized(filename):
    if session.get("user", {}).get("role") == "Admin": return True
    return any(item.get("report") == filename for item in current_user_history())


def _send_authorized_report(filename):
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename or not _report_is_authorized(filename): flash("You do not have access to that report.", "danger"); return redirect(url_for("report"))
    file_path = REPORT_FOLDER / filename
    if not file_path.exists() or file_path.suffix.lower() != ".pdf": flash("Report file was not found.", "danger"); return redirect(url_for("report"))
    return send_from_directory(REPORT_FOLDER, filename, as_attachment=True)


@app.route("/report")
@login_required
def report():
    reports = []
    for item in current_user_history():
        filename = item.get("report")
        if not filename: continue
        path = REPORT_FOLDER / filename
        if path.exists() and path.suffix.lower() == ".pdf":
            reports.append({"name": filename, "size": f"{path.stat().st_size / 1024:.1f} KB", "timestamp": path.stat().st_mtime, "date": datetime.fromtimestamp(path.stat().st_mtime).strftime("%d-%m-%Y %H:%M:%S"), "student_name": item.get("student_name", "Student")})
    reports.sort(key=lambda item: item["timestamp"], reverse=True)
    return render_template("report.html", reports=reports, total_reports=len(reports))


@app.route("/reports/<filename>")
@login_required
def download_saved_report(filename):
    return _send_authorized_report(filename)


@app.errorhandler(413)
def too_large(_error):
    flash("Upload rejected: maximum file size is 20 MB.", "danger"); return redirect(request.referrer or url_for("dataset_preview"))


@app.errorhandler(404)
def page_not_found(_error):
    flash("The requested page was not found.", "warning"); return redirect(url_for("dashboard" if "user" in session else "login"))


@app.errorhandler(500)
def internal_error(_error):
    traceback.print_exc(); flash("An internal application error occurred.", "danger"); return redirect(url_for("dashboard" if "user" in session else "login"))


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG", "0") == "1")
