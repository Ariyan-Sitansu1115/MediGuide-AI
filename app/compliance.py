"""
Compliance module for MediGuide AI — Phase 1.

Contains:
  - MedicalDisclaimerManager : versioned disclaimer text and response decoration
  - ConsentManager           : consent collection and verification
  - PrivacyManager           : GDPR/HIPAA-aligned data access and deletion
  - RedFlagDetector          : emergency symptom combination detection
  - AuditLogger              : structured audit trail for all significant events
"""

import json

from app.database import (
    decrypt_data,
    encrypt_data,
    get_db_connection,
    new_id,
    utcnow,
)

# ---------------------------------------------------------------------------
# Disclaimer content
# ---------------------------------------------------------------------------

DISCLAIMER_VERSION = "1.0"

DISCLAIMER_TEXT = (
    "MEDICAL DISCLAIMER AND INFORMED CONSENT\n"
    "========================================\n\n"
    "MediGuide AI is an EDUCATIONAL TOOL ONLY and is NOT a medical device.\n\n"
    "THIS SYSTEM DOES NOT:\n"
    "  \u2022 Diagnose any disease or medical condition\n"
    "  \u2022 Prescribe medications, antibiotics, or any treatments\n"
    "  \u2022 Replace consultation with licensed healthcare professionals\n"
    "  \u2022 Provide emergency medical advice or crisis intervention\n"
    "  \u2022 Guarantee the accuracy of any health-related information\n\n"
    "ALL OUTPUTS ARE:\n"
    "  \u2022 For educational and informational awareness purposes only\n"
    "  \u2022 Non-diagnostic educational risk stratification (NOT clinical diagnosis)\n"
    "  \u2022 Advisory guidance only \u2014 NOT actionable medical instructions\n\n"
    "IMPORTANT MEDICAL WARNINGS:\n"
    "  \u2022 In a medical emergency, immediately call 911 or your local emergency number\n"
    "  \u2022 Do NOT delay seeking emergency care based on information from this system\n"
    "  \u2022 Always consult a licensed healthcare professional before making any "
    "health decisions\n"
    "  \u2022 This system cannot account for your complete medical history\n\n"
    "REGULATORY NOTICE:\n"
    "This educational software is designed to align with FDA guidance on "
    "non-diagnostic\nclinical decision-support tools, FTC health-app disclosure "
    "requirements, and WHO\nantibiotic stewardship principles.  It is not a medical "
    "device and has not been\nreviewed by the FDA.\n\n"
    "BY USING THIS SYSTEM, YOU ACKNOWLEDGE:\n"
    "  1. You understand this is an educational tool only\n"
    "  2. All information is for awareness purposes, not medical advice\n"
    "  3. You will consult a licensed healthcare professional for medical decisions\n"
    "  4. In an emergency you will immediately contact emergency services\n"
    "  5. You consent to anonymous, encrypted session data collection for service "
    "improvement\n"
    "  6. You have the right to access, download, and delete your session data"
)

SHORT_DISCLAIMER = (
    "\u2695\ufe0f EDUCATIONAL ONLY \u2014 This is NOT medical advice. "
    "This system does not diagnose. "
    "Always consult a licensed healthcare professional."
)


# ---------------------------------------------------------------------------
# MedicalDisclaimerManager
# ---------------------------------------------------------------------------


class MedicalDisclaimerManager:
    """Manages medical disclaimers with versioning and response decoration."""

    VERSION = DISCLAIMER_VERSION
    TEXT = DISCLAIMER_TEXT
    SHORT = SHORT_DISCLAIMER

    @classmethod
    def get_disclaimer(cls) -> dict:
        """Return the full disclaimer document."""
        return {
            "version": cls.VERSION,
            "text": cls.TEXT,
            "short": cls.SHORT,
            "effective_date": "2024-01-01",
        }

    @classmethod
    def attach_to_response(cls, data: dict) -> dict:
        """Return *data* with disclaimer fields appended."""
        return {
            **data,
            "disclaimer": cls.SHORT,
            "disclaimer_version": cls.VERSION,
        }


# ---------------------------------------------------------------------------
# ConsentManager
# ---------------------------------------------------------------------------


class ConsentManager:
    """Consent collection, verification, and audit logging."""

    @staticmethod
    def record_consent(
        session_id: str,
        disclaimer_version: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """Persist a consent acceptance and return a confirmation dict."""
        record_id = new_id()
        now = utcnow()

        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO consent_records
                    (id, session_id, disclaimer_version, consent_given,
                     ip_address, user_agent, created_at)
                VALUES (?, ?, ?, 1, ?, ?, ?)
                """,
                (record_id, session_id, disclaimer_version, ip_address, user_agent, now),
            )
            conn.commit()
        finally:
            conn.close()

        AuditLogger.log(
            session_id=session_id,
            action="consent_given",
            resource="disclaimer",
            ip_address=ip_address,
            details=f"version={disclaimer_version}",
        )

        return {"consent_id": record_id, "session_id": session_id, "recorded_at": now}

    @staticmethod
    def has_valid_consent(session_id: str) -> bool:
        """Return True if the session has an accepted consent record."""
        conn = get_db_connection()
        try:
            row = conn.execute(
                """
                SELECT id FROM consent_records
                WHERE session_id = ? AND consent_given = 1
                ORDER BY created_at DESC LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    @staticmethod
    def get_consent_status(session_id: str) -> dict:
        """Return consent status details for a session."""
        conn = get_db_connection()
        try:
            row = conn.execute(
                """
                SELECT * FROM consent_records
                WHERE session_id = ? AND consent_given = 1
                ORDER BY created_at DESC LIMIT 1
                """,
                (session_id,),
            ).fetchone()

            if row:
                return {
                    "has_consent": True,
                    "disclaimer_version": row["disclaimer_version"],
                    "consented_at": row["created_at"],
                }
            return {"has_consent": False}
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# PrivacyManager
# ---------------------------------------------------------------------------


class PrivacyManager:
    """GDPR/HIPAA-aligned user-data access, export, and deletion."""

    @staticmethod
    def get_user_data(session_id: str) -> dict:
        """Export all data held for a session (data-portability right)."""
        conn = get_db_connection()
        try:
            consents = conn.execute(
                "SELECT * FROM consent_records WHERE session_id = ?",
                (session_id,),
            ).fetchall()

            symptoms = conn.execute(
                "SELECT * FROM symptom_records WHERE session_id = ?",
                (session_id,),
            ).fetchall()

            logs = conn.execute(
                "SELECT * FROM audit_logs WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        finally:
            conn.close()

        decrypted_symptoms = []
        for row in symptoms:
            r = dict(row)
            try:
                r["symptom_data"] = json.loads(decrypt_data(r["symptom_data"]))
            except Exception:
                r["symptom_data"] = r["symptom_data"]
            decrypted_symptoms.append(r)

        return {
            "session_id": session_id,
            "exported_at": utcnow(),
            "consent_records": [dict(r) for r in consents],
            "symptom_records": decrypted_symptoms,
            "audit_logs": [dict(r) for r in logs],
        }

    @staticmethod
    def delete_all_user_data(session_id: str, ip_address: str | None = None) -> dict:
        """Delete all data for a session (right to erasure)."""
        conn = get_db_connection()
        try:
            conn.execute(
                "DELETE FROM consent_records WHERE session_id = ?", (session_id,)
            )
            conn.execute(
                "DELETE FROM symptom_records WHERE session_id = ?", (session_id,)
            )
            conn.execute(
                "DELETE FROM audit_logs WHERE session_id = ?", (session_id,)
            )
            conn.commit()
        finally:
            conn.close()

        AuditLogger.log(
            session_id=session_id,
            action="data_deleted",
            resource="all_user_data",
            ip_address=ip_address,
            details="User invoked right to erasure",
        )

        return {"deleted": True, "session_id": session_id, "deleted_at": utcnow()}


# ---------------------------------------------------------------------------
# RedFlagDetector
# ---------------------------------------------------------------------------


class RedFlagDetector:
    """
    Detects dangerous symptom combinations requiring immediate emergency care.

    Rules are hard-coded to ensure they cannot be altered by ML inference.
    Detection is keyword-based and conservative — a single matching rule is
    sufficient to trigger an emergency alert.
    """

    RULES = [
        {
            "id": "chest_pain_breathing",
            "symptoms": {"chest_pain", "shortness_of_breath"},
            "message": (
                "Chest pain combined with difficulty breathing may indicate a serious "
                "cardiac or respiratory emergency."
            ),
            "action": "Call 911 or your local emergency number IMMEDIATELY.",
        },
        {
            "id": "severe_headache_stiff_neck",
            "symptoms": {"severe_headache", "stiff_neck"},
            "message": (
                "Severe headache combined with stiff neck may indicate bacterial "
                "meningitis, which is a medical emergency."
            ),
            "action": "Seek emergency medical care IMMEDIATELY.",
        },
        {
            "id": "loss_of_consciousness",
            "symptoms": {"loss_of_consciousness"},
            "message": "Loss of consciousness is always a medical emergency.",
            "action": "Call 911 or your local emergency number IMMEDIATELY.",
        },
        {
            "id": "stroke_symptoms",
            "symptoms": {"facial_drooping", "arm_weakness", "speech_difficulty"},
            "message": (
                "Facial drooping, arm weakness, and speech difficulty are warning "
                "signs of stroke (FAST: Face, Arms, Speech, Time)."
            ),
            "action": "Call 911 IMMEDIATELY \u2014 time is critical for stroke treatment.",
        },
        {
            "id": "anaphylaxis",
            "symptoms": {"throat_swelling", "difficulty_swallowing"},
            "message": (
                "Throat swelling with difficulty swallowing may indicate anaphylaxis "
                "(severe allergic reaction)."
            ),
            "action": "Call 911 IMMEDIATELY and use epinephrine if available.",
        },
        {
            "id": "sepsis_indicators",
            "symptoms": {"high_fever", "confusion"},
            "message": (
                "High fever combined with confusion may indicate sepsis or severe "
                "infection requiring immediate treatment."
            ),
            "action": "Seek emergency medical care IMMEDIATELY.",
        },
        {
            "id": "hemoptysis",
            "symptoms": {"coughing_blood"},
            "message": (
                "Coughing up blood (hemoptysis) requires immediate medical evaluation."
            ),
            "action": "Seek emergency or urgent medical care IMMEDIATELY.",
        },
        {
            "id": "chest_pain_alone",
            "symptoms": {"chest_pain"},
            "message": (
                "Chest pain may indicate a cardiac emergency, especially when "
                "accompanied by radiating pain, sweating, or nausea."
            ),
            "action": "Seek urgent medical evaluation. Call 911 if severe.",
        },
    ]

    EMERGENCY_CONTACTS = {
        "us_emergency": "911",
        "us_poison_control": "1-800-222-1222",
        "mental_health_crisis": "988",
    }

    @classmethod
    def check(cls, symptoms: list[str]) -> dict:
        """
        Evaluate *symptoms* (list of symptom key strings) against all rules.

        Returns a dict with ``is_emergency`` flag, triggered rules, and
        emergency contact information when applicable.
        """
        symptom_set = {s.lower().strip() for s in symptoms}
        triggered = []

        for rule in cls.RULES:
            if rule["symptoms"].issubset(symptom_set):
                triggered.append(
                    {
                        "rule_id": rule["id"],
                        "message": rule["message"],
                        "action": rule["action"],
                        "severity": "EMERGENCY",
                    }
                )

        is_emergency = bool(triggered)

        return {
            "is_emergency": is_emergency,
            "triggered_rules": triggered,
            "emergency_contacts": cls.EMERGENCY_CONTACTS if is_emergency else {},
            "guidance": (
                "⚠️ EMERGENCY DETECTED — Please seek immediate medical attention. "
                "Do not rely on this system in an emergency."
            )
            if is_emergency
            else None,
        }


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------


class AuditLogger:
    """Structured audit trail for all significant system events."""

    @staticmethod
    def log(
        session_id: str | None = None,
        action: str = "",
        resource: str | None = None,
        ip_address: str | None = None,
        details: str | None = None,
    ) -> None:
        """Persist an audit event. Failures are silently swallowed so that
        audit logging never interrupts normal request processing."""
        try:
            conn = get_db_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO audit_logs
                        (id, session_id, action, resource,
                         ip_address, details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id(),
                        session_id,
                        action,
                        resource,
                        ip_address,
                        details,
                        utcnow(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass
