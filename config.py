import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    MODEL_PATH = BASE_DIR / "model" / "model.pkl"
    RAW_DATA_DIR = BASE_DIR / "data" / "raw"
    PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
