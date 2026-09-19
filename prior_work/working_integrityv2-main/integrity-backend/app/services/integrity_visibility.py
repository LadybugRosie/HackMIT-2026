"""
Integrity visibility control — single source of truth for what integrity data
students can see, plus a tombstone guard for the removed composite score.

The composite trust score has been REMOVED from the product: it is no longer
computed or stored. COMPOSITE_FIELDS remains only as a guard so that old Mongo
rows (written before the removal) never leak their stale composite values
through any endpoint that spreads a raw document.

Behavior is gated by the INTEGRITY_LEGACY_MODE env var:

  INTEGRITY_LEGACY_MODE=false (default) -> students see NO integrity signals
  INTEGRITY_LEGACY_MODE=true            -> students see their INDIVIDUAL signals
                                           (trust score, stylometry, AI) again

This flag can no longer restore the composite — that code path is gone.
The stylometry verify flywheel / baseline absorption are never touched here.
"""
import os

# Composite is hidden from EVERYONE (all roles) in new mode.
COMPOSITE_FIELDS = {
    "composite_trust_score",
    "composite_provisional",
    "composite_factors",
}

# Full integrity signal set — hidden from STUDENTS in new mode.
INTEGRITY_FIELDS = COMPOSITE_FIELDS | {
    "trust_score",
    "content_mix",
    "integrity_flags",
    "flags",
    "face_verification_log",
    "plagiarism_score",
    "plagiarism_matches",
    "ai_probability",
    "ai_detection",
    "stylometry",
    "stylometry_v3",
    "stylometry_verdict",
    "external_pastes_found",
    "chunk_analysis",
    "has_report",
    "similarity_pending",
}


def effective_ai_probability(d) -> object:
    """AI probability only if detection actually ran; None otherwise ('not run').

    Legacy rows (no status persisted) are recognized by their failure
    fingerprint: probability 0 with a fabricated or absent predicted_class.
    """
    if not isinstance(d, dict):
        return None
    status = d.get("status")
    if status is not None and status != "success":
        return None
    if status is None and not d.get("ai_probability") and d.get("predicted_class") in (None, "skipped", "unknown"):
        return None
    return d.get("ai_probability")


def legacy_mode() -> bool:
    """True when the production-revert switch is on (return everything unchanged)."""
    return os.getenv("INTEGRITY_LEGACY_MODE", "false").strip().lower() in ("1", "true", "yes", "on")


def sanitize_submission_response(payload: dict, role: str) -> dict:
    """Strip composite (all roles) and full integrity (students) from a response dict.

    No-op when the legacy switch is on, so behavior is byte-for-byte production.
    """
    if legacy_mode() or not isinstance(payload, dict):
        return payload
    drop = INTEGRITY_FIELDS if role == "student" else COMPOSITE_FIELDS
    out = {k: v for k, v in payload.items() if k not in drop}
    # auto_grade_suggestion can carry integrity verdicts — null those out for students.
    if role == "student" and isinstance(out.get("auto_grade_suggestion"), dict):
        ag = dict(out["auto_grade_suggestion"])
        ag.pop("integrity_notes", None)
        ag.pop("flag_reason", None)
        out["auto_grade_suggestion"] = ag
    return out
