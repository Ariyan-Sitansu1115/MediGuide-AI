# MediGuide AI

MediGuide AI is a clean, modular starter architecture for an AI-powered healthcare web application built with Flask and a Random Forest prediction pipeline.

## Project Structure

```text
MediGuide-AI/
|-- app/
|   |-- __init__.py          # Flask app factory
|   |-- routes.py            # REST API endpoints
|   `-- utils.py             # Shared helper and preprocessing validation
|
|-- model/
|   |-- train_model.py       # Random Forest training and model persistence
|   |-- predict.py           # Model loading and inference logic
|   `-- model.pkl            # Saved trained model artifact
|
|-- data/
|   |-- raw/                 # Original source data (immutable)
|   |   `-- README.md
|   `-- processed/           # Cleaned/feature-ready data for training
|       `-- README.md
|
|-- notebooks/
|   `-- README.md            # Experimentation notebook guidance
|
|-- static/
|   |-- css/
|   |   `-- styles.css
|   `-- js/
|       `-- app.js
|
|-- templates/
|   `-- index.html
|
|-- config.py                # Centralized config values
|-- main.py                  # Flask app entry point
|-- requirements.txt         # Python dependencies
`-- README.md
```

## Architecture Highlights

- Uses Flask application factory pattern for scalability.
- Keeps model training logic isolated from API serving logic.
- Includes dedicated layers for data ingestion, preprocessing, and inference.
- Supports easy migration from static frontend to React without backend rewrites.
- Organized to grow into larger domains (auth, audit, model versioning, monitoring).

## API Endpoints

- `GET /` - Service health check
- `GET /api/health` - API health check
- `POST /api/predict` - Run prediction

Example request payload:

```json
{
	"features": [
		{
			"age": 45,
			"temperature": 98.6,
			"blood_pressure": 120,
			"heart_rate": 82,
			"symptom_score": 3
		}
	]
}
```

## Getting Started

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Add processed training data to `data/processed/dataset_clean.csv`.
4. Train model:

```bash
python model/train_model.py
```

5. Start application:

```bash
python main.py
```

## Next Scaling Steps

- Add schema validation (`pydantic` or `marshmallow`) for stricter API contracts.
- Add model/version metadata and experiment tracking.
- Add authentication, rate limiting, and audit logs for healthcare compliance.
- Add CI checks for linting, tests, and model training reproducibility.
