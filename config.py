import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DATASET_FOLDER = BASE_DIR / "dataset"
    UPLOAD_FOLDER = BASE_DIR / "uploads" / "datasets"
    MODEL_FOLDER = BASE_DIR / "saved_models"
    REPORT_FOLDER = BASE_DIR / "reports"
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
