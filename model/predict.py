from pathlib import Path

import joblib

from app.utils import clean_and_validate_features

ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT_DIR / "model" / "model.pkl"

_model_cache = None


def load_model():
    global _model_cache

    if _model_cache is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model file not found at {MODEL_PATH}. "
                "Run model/train_model.py first."
            )
        _model_cache = joblib.load(MODEL_PATH)

    return _model_cache


def predict_risk(features):
    model = load_model()
    feature_df = clean_and_validate_features(features)

    prediction = model.predict(feature_df)
    return prediction.tolist()
