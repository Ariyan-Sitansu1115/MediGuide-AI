"""
API routes for MediGuide AI — Phase 1.

All routes return educational, non-diagnostic information.
Every response includes a mandatory medical disclaimer.
"""

import json

from flask import Blueprint, jsonify, request

from app.compliance import (
    AuditLogger,
    ConsentManager,
    MedicalDisclaimerManager,
    PrivacyManager,
    RedFlagDetector,
)
from app.database import encrypt_data, get_db_connection, new_id, utcnow
from model.predict import explain_prediction, predict_risk

api_bp = Blueprint("api", __name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_id() -> str | None:
    """Extract session_id from request headers or JSON body."""
    return request.headers.get("X-Session-ID") or (
        (request.get_json(silent=True) or {}).get("session_id")
    )


def _ip() -> str | None:
    """Return the best-guess client IP."""
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def _ok(data: dict, status: int = 200):
    """Return a JSON response with disclaimer attached."""
    return jsonify(MedicalDisclaimerManager.attach_to_response(data)), status


def _err(message: str, status: int = 400):
    return jsonify({"error": message}), status


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@api_bp.get("/health")
def api_health():
    return jsonify({"status": "healthy", "api": "MediGuide AI"}), 200


# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------


@api_bp.get("/disclaimer")
def get_disclaimer():
    """Return the current disclaimer text and version."""
    return jsonify(MedicalDisclaimerManager.get_disclaimer()), 200


@api_bp.post("/disclaimer/accept")
def accept_disclaimer():
    """
    Record that a user has accepted the medical disclaimer.

    Expected body (JSON):
        { "session_id": "<uuid>", "disclaimer_version": "1.0" }
    """
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id") or _session_id()
    version = payload.get("disclaimer_version", MedicalDisclaimerManager.VERSION)

    if not session_id:
        return _err("'session_id' is required.")

    result = ConsentManager.record_consent(
        session_id=session_id,
        disclaimer_version=version,
        ip_address=_ip(),
        user_agent=request.headers.get("User-Agent"),
    )
    return _ok({"message": "Consent recorded.", **result}, 201)


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------


@api_bp.post("/consent/status")
def consent_status():
    """
    Check whether a session has accepted the disclaimer.

    Expected body (JSON):
        { "session_id": "<uuid>" }
    """
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id") or _session_id()

    if not session_id:
        return _err("'session_id' is required.")

    status = ConsentManager.get_consent_status(session_id)
    return _ok(status)


# ---------------------------------------------------------------------------
# Symptoms
# ---------------------------------------------------------------------------


@api_bp.post("/symptoms")
def submit_symptoms():
    """
    Store a symptom submission for the session (requires prior consent).

    Expected body (JSON):
        {
            "session_id": "<uuid>",
            "symptoms": { "fever": 1, "cough": 0, "throat_pain": 1, "skin_issue": 0 },
            "severity":  "moderate",          // optional
            "duration":  "3 days",            // optional
            "context":   "started after rain" // optional
        }
    """
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id") or _session_id()
    symptoms = payload.get("symptoms")

    if not session_id:
        return _err("'session_id' is required.")
    if not symptoms:
        return _err("'symptoms' field is required.")
    if not ConsentManager.has_valid_consent(session_id):
        return _err("User has not accepted the disclaimer.", 403)

    record = {
        "symptoms": symptoms,
        "severity": payload.get("severity"),
        "duration": payload.get("duration"),
        "context": payload.get("context"),
    }

    encrypted = encrypt_data(json.dumps(record))
    record_id = new_id()
    now = utcnow()

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO symptom_records (id, session_id, symptom_data, created_at) "
            "VALUES (?, ?, ?, ?)",
            (record_id, session_id, encrypted, now),
        )
        conn.commit()
    finally:
        conn.close()

    AuditLogger.log(
        session_id=session_id,
        action="symptom_submitted",
        resource="symptom_records",
        ip_address=_ip(),
        details=f"record_id={record_id}",
    )

    return _ok(
        {
            "message": "Symptom data stored.",
            "record_id": record_id,
            "created_at": now,
        },
        201,
    )


@api_bp.get("/symptoms/<session_id>")
def get_symptoms(session_id: str):
    """Retrieve all symptom submissions for a session."""
    if not ConsentManager.has_valid_consent(session_id):
        return _err("No valid consent found for this session.", 403)

    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, session_id, symptom_data, created_at "
            "FROM symptom_records WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()

    records = []
    from app.database import decrypt_data

    for row in rows:
        try:
            data = json.loads(decrypt_data(row["symptom_data"]))
        except Exception:
            data = {}
        records.append({"id": row["id"], "created_at": row["created_at"], **data})

    AuditLogger.log(
        session_id=session_id,
        action="symptoms_accessed",
        resource="symptom_records",
        ip_address=_ip(),
    )

    return _ok({"session_id": session_id, "records": records})


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------


@api_bp.post("/risk-assessment")
def risk_assessment():
    """
    Perform non-diagnostic educational risk stratification.

    Expected body (JSON):
        {
            "session_id": "<uuid>",
            "features": { "fever": 1, "cough": 1, "throat_pain": 0, "skin_issue": 0 }
        }

    The response includes:
      - risk_tier (low / medium / high)
      - confidence score
      - per-feature contributions
      - mandatory disclaimer
    """
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id") or _session_id()
    features = payload.get("features")

    if not session_id:
        return _err("'session_id' is required.")
    if features is None:
        return _err("'features' field is required.")
    if not ConsentManager.has_valid_consent(session_id):
        return _err("User has not accepted the disclaimer.", 403)

    try:
        result = explain_prediction(features)
    except ValueError as exc:
        return _err(str(exc))
    except FileNotFoundError:
        return _err("Model not found. Please contact the administrator.", 503)
    except Exception:
        return _err("Risk assessment failed.", 500)

    AuditLogger.log(
        session_id=session_id,
        action="risk_assessment",
        resource="model",
        ip_address=_ip(),
        details=f"risk_tier={result.get('risk_tier')}",
    )

    return _ok({"risk_assessment": result})


# ---------------------------------------------------------------------------
# Red-flag check
# ---------------------------------------------------------------------------


@api_bp.post("/red-flag-check")
def red_flag_check():
    """
    Check a symptom list for dangerous combinations requiring emergency care.

    Expected body (JSON):
        {
            "session_id": "<uuid>",
            "symptoms": ["chest_pain", "shortness_of_breath"]
        }
    """
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id") or _session_id()
    symptoms = payload.get("symptoms", [])

    if not session_id:
        return _err("'session_id' is required.")
    if not isinstance(symptoms, list):
        return _err("'symptoms' must be a list of symptom key strings.")

    result = RedFlagDetector.check(symptoms)

    if result["is_emergency"]:
        AuditLogger.log(
            session_id=session_id,
            action="emergency_alert_triggered",
            resource="red_flag_detector",
            ip_address=_ip(),
            details=f"rules={[r['rule_id'] for r in result['triggered_rules']]}",
        )

    return _ok(result)


# ---------------------------------------------------------------------------
# Legacy predict (backward compatibility)
# ---------------------------------------------------------------------------


@api_bp.post("/predict")
def predict():
    """Legacy endpoint — returns raw model predictions with disclaimer."""
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

    return _ok({"prediction": prediction})


# ---------------------------------------------------------------------------
# Privacy / GDPR
# ---------------------------------------------------------------------------


@api_bp.get("/privacy/my-data")
def export_my_data():
    """
    Export all data held for a session (GDPR data portability).

    Pass session_id as query-param or X-Session-ID header.
    """
    session_id = request.args.get("session_id") or _session_id()

    if not session_id:
        return _err("'session_id' is required.")

    AuditLogger.log(
        session_id=session_id,
        action="data_export_requested",
        resource="all_user_data",
        ip_address=_ip(),
    )

    data = PrivacyManager.get_user_data(session_id)
    return jsonify(data), 200


@api_bp.delete("/privacy/delete-all")
def delete_all_data():
    """
    Delete all data for a session (GDPR right to erasure).

    Pass session_id as query-param or X-Session-ID header.
    """
    session_id = request.args.get("session_id") or _session_id()

    if not session_id:
        return _err("'session_id' is required.")

    result = PrivacyManager.delete_all_user_data(session_id, ip_address=_ip())
    return jsonify(result), 200
