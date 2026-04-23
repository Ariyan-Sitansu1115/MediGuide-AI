import pandas as pd


EXPECTED_FEATURE_COLUMNS = [
    "fever",
    "cough",
    "throat_pain",
    "skin_issue",
]


def clean_and_validate_features(features):
    """Validate input data and convert it to a DataFrame for model consumption."""
    if isinstance(features, dict):
        features = [features]

    if not isinstance(features, list) or len(features) == 0:
        raise ValueError("'features' must be a non-empty list or object.")

    df = pd.DataFrame(features)

    missing_cols = [col for col in EXPECTED_FEATURE_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required feature columns: {missing_cols}")

    return df[EXPECTED_FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
