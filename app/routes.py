from flask import Blueprint, jsonify, request

from model.predict import predict_risk

api_bp = Blueprint("api", __name__)


@api_bp.get("/health")
def api_health():
    return jsonify({"status": "healthy", "api": "MediGuide AI"}), 200


@api_bp.post("/predict")
def predict():
    payload = request.get_json(silent=True)

    if not payload:
        return jsonify({"error": "JSON payload is required."}), 400

    features = payload.get("features")
    if features is None:
        return jsonify({"error": "'features' field is required."}), 400

    try:
        prediction = predict_risk(features)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        return jsonify({"error": "Prediction failed."}), 500

    return jsonify({"prediction": prediction}), 200
