"""
Prediction utilities for MediGuide AI.

All public helpers return *educational* outputs framed as non-diagnostic
risk stratification.  No function claims to diagnose any condition.
"""

from pathlib import Path

import joblib
import numpy as np

from app.utils import EXPECTED_FEATURE_COLUMNS, clean_and_validate_features

ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT_DIR / "model" / "model.pkl"

_model_cache = None

# Mapping from raw model label → educational risk tier
_RISK_TIER_MAP = {
    "bacterial": "high",
    "viral": "low",
}

# Non-diagnostic language templates
_TIER_DESCRIPTIONS = {
    "high": (
        "Patterns in these responses are commonly seen in presentations that "
        "healthcare providers evaluate carefully. A medical consultation is "
        "strongly recommended."
    ),
    "medium": (
        "Patterns in these responses may warrant a discussion with a healthcare "
        "provider to rule out conditions that benefit from early attention."
    ),
    "low": (
        "Patterns in these responses are commonly seen in self-limiting "
        "presentations; however, if symptoms persist or worsen, please consult "
        "a healthcare professional."
    ),
}

_EDUCATIONAL_DISCLAIMER = (
    "⚕️ EDUCATIONAL ONLY — This is NOT medical advice. "
    "This system does not diagnose. "
    "Always consult a licensed healthcare professional."
)


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
    """Return raw model predictions (list of label strings)."""
    model = load_model()
    feature_df = clean_and_validate_features(features)
    prediction = model.predict(feature_df)
    return prediction.tolist()


def explain_prediction(features) -> dict:
    """
    Return an educational risk-stratification result with:
      - risk_tier         : "low" | "medium" | "high"
      - confidence        : float 0-1 (model probability for predicted class)
      - pattern_label     : raw model output label
      - description       : non-diagnostic educational description
      - feature_contributions : per-feature importance ranked list
      - disclaimer        : mandatory educational disclaimer
    """
    model = load_model()
    feature_df = clean_and_validate_features(features)

    # --- Raw prediction + probabilities ---
    raw_label = model.predict(feature_df)[0]
    try:
        proba = model.predict_proba(feature_df)[0]
        classes = model.classes_
        confidence = float(proba[list(classes).index(raw_label)])
    except Exception:
        confidence = 1.0

    # --- Risk tier (non-diagnostic mapping) ---
    risk_tier = _RISK_TIER_MAP.get(str(raw_label).lower(), "medium")

    # --- Feature contributions from Random Forest importances ---
    feature_contributions = _get_feature_contributions(model, feature_df)

    return {
        "risk_tier": risk_tier,
        "confidence": round(confidence, 3),
        "pattern_label": str(raw_label),
        "description": _TIER_DESCRIPTIONS[risk_tier],
        "feature_contributions": feature_contributions,
        "next_steps": _get_next_steps(risk_tier),
        "disclaimer": _EDUCATIONAL_DISCLAIMER,
        "educational_note": (
            "Risk stratification is for educational awareness only. "
            "It does not constitute a medical diagnosis or treatment recommendation."
        ),
    }


def _get_feature_contributions(model, feature_df) -> list[dict]:
    """Return per-feature importance values as a ranked list."""
    try:
        # Works for Pipeline with a named 'classifier' step
        classifier = model.named_steps.get("classifier") or model
        importances = classifier.feature_importances_
        feature_names = feature_df.columns.tolist()
        input_values = feature_df.iloc[0].tolist()

        contributions = [
            {
                "feature": name,
                "importance": round(float(imp), 4),
                "reported_value": int(val),
                "contribution_label": (
                    "primary factor" if imp >= 0.3
                    else "secondary factor" if imp >= 0.15
                    else "minor factor"
                ),
            }
            for name, imp, val in sorted(
                zip(feature_names, importances, input_values),
                key=lambda x: x[1],
                reverse=True,
            )
        ]
        return contributions
    except Exception:
        return [
            {"feature": col, "importance": None, "reported_value": None,
             "contribution_label": "unknown"}
            for col in EXPECTED_FEATURE_COLUMNS
        ]


def _get_next_steps(risk_tier: str) -> list[str]:
    """Return educational next-step guidance (non-prescriptive)."""
    base = [
        "Consult a licensed healthcare professional for a proper evaluation.",
        "Do not self-medicate or start/stop antibiotics without medical supervision.",
    ]
    if risk_tier == "high":
        return [
            "Seek medical attention promptly.",
            "A healthcare provider may consider further evaluation.",
        ] + base
    if risk_tier == "medium":
        return [
            "Schedule an appointment with your healthcare provider soon.",
        ] + base
    return [
        "Monitor your symptoms and rest.",
        "If symptoms worsen or persist beyond a few days, consult a doctor.",
    ] + base
