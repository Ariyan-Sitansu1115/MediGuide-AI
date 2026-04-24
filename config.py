import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    MODEL_PATH = BASE_DIR / "model" / "model.pkl"
    RAW_DATA_DIR = BASE_DIR / "data" / "raw"
    PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"

    # Phase 1: database and encryption
    DB_PATH = BASE_DIR / "data" / "mediguide.db"
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")  # Fernet key; auto-generated if absent

    # Phase 1: compliance
    DISCLAIMER_VERSION = "1.0"
    REQUIRE_CONSENT = True  # Set False to disable consent gate during development
