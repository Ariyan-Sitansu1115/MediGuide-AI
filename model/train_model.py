from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = [
    "fever",
    "cough",
    "throat_pain",
    "skin_issue",
]
TARGET_COLUMN = "output"

ROOT_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DATA_PATH = ROOT_DIR / "data" / "final_dataset.CSV"
MODEL_OUTPUT_PATH = ROOT_DIR / "model" / "model.pkl"


def load_dataset(path=PROCESSED_DATA_PATH):
    if not path.exists():
        raise FileNotFoundError(
            f"Processed dataset not found at {path}. "
            "Add your cleaned dataset before training."
        )

    df = pd.read_csv(path)

    missing = [col for col in FEATURE_COLUMNS + [TARGET_COLUMN] if col not in df.columns]
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")

    return df


def train_and_save_model():
    df = load_dataset()

    x = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=200,
                    random_state=42,
                    class_weight="balanced",
                ),
            ),
        ]
    )

    pipeline.fit(x_train, y_train)

    accuracy = pipeline.score(x_test, y_test)
    MODEL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_OUTPUT_PATH)

    print(f"Model trained. Validation accuracy: {accuracy:.4f}")
    print(f"Saved model to: {MODEL_OUTPUT_PATH}")


if __name__ == "__main__":
    train_and_save_model()
