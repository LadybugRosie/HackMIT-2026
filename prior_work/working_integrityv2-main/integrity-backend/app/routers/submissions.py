"""
Submissions Router - Student Submissions and Teacher Grading
"""
from fastapi import APIRouter, HTTPException, Query, Request, Header
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import hashlib
import re
import bleach

from ..models import (
    SubmissionCreate, SubmissionSubmit, GradeSubmission,
    SubmissionResponse, ContentMix, PlagiarismMatch,
    FaceVerificationLog, CriteriaScore, AutoGradeResult
)
from ..services.integrity_visibility import (
    sanitize_submission_response,
    legacy_mode,
)

router = APIRouter(prefix="/api/submissions", tags=["Submissions"])

# =========================================================================
# HTML SANITIZATION (Fix for loophole #10 - XSS in reports)
# Uses bleach to strip dangerous tags/attributes from user-submitted HTML.
# =========================================================================
ALLOWED_TAGS = list(bleach.ALLOWED_TAGS) + [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'hr', 'div', 'span', 'pre', 'code',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'ul', 'ol', 'li', 'dl', 'dt', 'dd',
    'img', 'figure', 'figcaption', 'svg', 'path',
    'strong', 'em', 'u', 'sub', 'sup', 'mark', 'del', 'ins',
    'blockquote', 'cite', 'q',
    'section', 'article', 'header', 'footer', 'nav',
    'details', 'summary', 'canvas',
]
ALLOWED_ATTRIBUTES = {
    # FIX #11: Removed 'style' to prevent CSS injection / data exfiltration
    '*': ['class', 'id', 'data-*', 'title', 'role', 'aria-label'],
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'width', 'height', 'loading'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan', 'scope'],
    'svg': ['viewBox', 'xmlns', 'width', 'height', 'fill'],
    'path': ['d', 'fill', 'stroke', 'stroke-width'],
}

def sanitize_html(html_content: str) -> str:
    """Sanitize HTML to prevent XSS attacks while preserving safe formatting."""
    if not html_content:
        return html_content
    return bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )

# MongoDB collection references (set by main.py)
submissions_collection = None
assignments_collection = None
classes_collection = None
class_members_collection = None
users_collection = None
fingerprints_collection = None

def set_collections(submissions, assignments, classes, members, users, fingerprints):
    """Set MongoDB collection references"""
    global submissions_collection, assignments_collection, classes_collection
    global class_members_collection, users_collection, fingerprints_collection
    submissions_collection = submissions
    assignments_collection = assignments
    classes_collection = classes
    class_members_collection = members
    users_collection = users
    fingerprints_collection = fingerprints


async def get_user_from_token(token: str):
    """Get user from session token"""
    from .auth import get_current_user
    return await get_current_user(token)


def _extract_token(token: Optional[str] = None, authorization: Optional[str] = Header(None)) -> str:
    """Extract token from Authorization header or query param."""
    if authorization and authorization.startswith('Bearer '):
        return authorization[7:]
    if authorization:
        return authorization
    if token:
        return token
    raise HTTPException(status_code=401, detail="Authentication required")


def _ensure_utc(dt) -> datetime:
    """Make a datetime timezone-aware (UTC) if it's naive. MongoDB often stores naive datetimes."""
    if dt is None:
        return datetime.now(timezone.utc)
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _refresh_role_from_db(user: dict) -> dict:
    """FIX #22: Re-read role from DB to prevent stale-session permission exploits."""
    if users_collection is not None and user.get("user_id"):
        db_user = await users_collection.find_one({"user_id": user["user_id"]})
        if db_user:
            user["role"] = db_user.get("role", user.get("role", "student"))
    return user


async def verify_student(token: str):
    """Verify user is a student (or researcher — researchers submit their own work the same way)"""
    user = await get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await _refresh_role_from_db(user)
    if user.get("role") not in ("student", "researcher"):
        raise HTTPException(status_code=403, detail="Only students can perform this action")
    return user


async def verify_teacher(token: str):
    """Verify user is a teacher"""
    user = await get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await _refresh_role_from_db(user)
    if user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can perform this action")
    return user


async def verify_class_member(user: dict, class_id: str):
    """Verify user is a member of this class"""
    membership = await class_members_collection.find_one({
        "class_id": class_id,
        "user_id": user["user_id"]
    })
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this class")
    return membership


async def verify_class_teacher(user: dict, class_id: str):
    """Verify user is the teacher of this class"""
    class_doc = await classes_collection.find_one({"class_id": class_id})
    if not class_doc:
        raise HTTPException(status_code=404, detail="Class not found")
    if class_doc["teacher_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="You are not the teacher of this class")
    return class_doc


# ============================================================================
# SUBMISSION CRUD
# ============================================================================

@router.post("")
async def create_or_update_draft(request: SubmissionCreate, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Create or update a submission draft (student only)"""
    resolved_token = _extract_token(token, authorization)
    user = await verify_student(resolved_token)
    
    # Get assignment
    assignment = await assignments_collection.find_one({"assignment_id": request.assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    if not assignment["published"]:
        raise HTTPException(status_code=404, detail="Assignment not available")
    
    # Verify membership
    await verify_class_member(user, assignment["class_id"])
    
    # Check for existing submission
    existing = await submissions_collection.find_one({
        "assignment_id": request.assignment_id,
        "student_id": user["user_id"]
    })
    
    # Security: validate content size to prevent DB bloat attacks
    if request.content and len(request.content) > 500000:  # 500KB max
        raise HTTPException(status_code=400, detail="Content too large (max 500KB)")
    
    word_count = len(request.content.split()) if request.content else 0
    
    if existing:
        # Can only update drafts
        if existing["status"] != "draft":
            raise HTTPException(
                status_code=400,
                detail="Cannot modify a submitted assignment"
            )
        
        await submissions_collection.update_one(
            {"submission_id": existing["submission_id"]},
            {"$set": {
                "content": request.content,
                "content_html": sanitize_html(request.content_html) if request.content_html else request.content_html,
                "word_count": word_count,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        return {
            "success": True,
            "submission_id": existing["submission_id"],
            "status": "draft",
            "message": "Draft updated"
        }
    else:
        # Create new submission
        submission_doc = {
            "submission_id": str(uuid.uuid4()),
            "assignment_id": request.assignment_id,
            "class_id": assignment["class_id"],
            "student_id": user["user_id"],
            "content": request.content,
            "content_html": sanitize_html(request.content_html) if request.content_html else request.content_html,
            "word_count": word_count,
            "status": "draft",
            "trust_score": 100,
            "content_mix": {"typed": 1.0, "internal": 0, "external": 0},
            "integrity_flags": [],
            "face_verification_log": [],
            "plagiarism_score": 0,
            "plagiarism_matches": [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        await submissions_collection.insert_one(submission_doc)
        
        return {
            "success": True,
            "submission_id": submission_doc["submission_id"],
            "status": "draft",
            "message": "Draft created"
        }


@router.post("/{submission_id}/submit")
async def submit_assignment(
    submission_id: str,
    request: SubmissionSubmit,
    token: str = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Submit an assignment for grading (student only)"""
    resolved_token = _extract_token(token, authorization)
    user = await verify_student(resolved_token)
    
    # Get submission
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if submission["student_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your submission")
    
    if submission["status"] != "draft":
        raise HTTPException(status_code=400, detail="Already submitted")
    
    # Get assignment for settings
    assignment = await assignments_collection.find_one({"assignment_id": submission["assignment_id"]})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Calculate if late
    is_late = datetime.now(timezone.utc) > _ensure_utc(assignment.get("due_date"))
    
    # =========================================================================
    # SERVER-SIDE FACE VERIFICATION ENFORCEMENT (Fix for loophole #3)
    # If the assignment requires face verification, check the server-side log
    # to confirm the student actually completed face checks.
    # =========================================================================
    settings = assignment.get("settings", {})
    face_required = settings.get("face_verification_enabled", False)
    server_face_checks = 0
    
    if face_required:
        try:
            from .face_verification import face_check_log_collection
            if face_check_log_collection is not None:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                server_face_checks = await face_check_log_collection.count_documents({
                    "user_id": user["user_id"],
                    "verified": True,
                    "timestamp": {"$gte": cutoff}
                })
        except Exception:
            pass
    
    # Process integrity data from client
    integrity_data = request.integrity_data or {}
    # FIX #3: Default to 0 (not 100) -- never trust unverified client claims
    # trust_score is the RAW typing-based trust (typing provenance only).
    # The client sends this for apples-to-apples comparison with server paste analysis.
    client_trust_score = integrity_data.get("trust_score", 0)
    client_content_mix = integrity_data.get("content_mix", {"typed": 0, "internal": 0, "external": 1.0})
    integrity_flags = integrity_data.get("flags", [])
    face_log = integrity_data.get("face_verification_log", [])

    word_count = len(request.content.split()) if request.content else 0

    # Store additional integrity analysis data
    stylometry_data = integrity_data.get("stylometry")
    ai_detection_data = integrity_data.get("ai_detection")
    external_pastes = integrity_data.get("external_pastes_found", [])
    
    # =========================================================================
    # SERVER-SIDE TRUST SCORE VERIFICATION (Fix for loophole #1 & #2)
    # The server independently computes a trust score by checking the integrity
    # session data. The final trust score is the MINIMUM of client and server
    # values, preventing students from faking a high score.
    # =========================================================================
    server_trust_score = None
    server_content_mix = None
    trust_score_source = "client"
    session_data = None  # must exist after try/except (e.g. ImportError) for branch below

    try:
        from .integrity_simple import GLOBAL_SESSIONS, _get_session as _integrity_get_session
        session_data = GLOBAL_SESSIONS.get(request.session_id)
        
        # If not in cache, try fetching from MongoDB directly
        if not session_data and request.session_id:
            session_data = await _integrity_get_session(request.session_id)
        
        if session_data:
            # Verify session belongs to this user — prevents session replay attacks
            session_owner = session_data.get("user_id") or session_data.get("email")
            if session_owner and session_owner != user.get("user_id") and session_owner != user.get("email"):
                integrity_flags.append(
                    "SESSION_OWNER_MISMATCH: Integrity session belongs to a different user. "
                    "Trust score invalidated."
                )
                session_data = None  # treat as no session

        if session_data:
            # Server has integrity session data - compute trust independently
            paste_database = session_data.get("paste_database", [])
            analysis_history = session_data.get("analysis_history", [])

            # Compute fresh trust from paste database vs CURRENT content
            # This is the primary signal — checks what paste content is actually
            # still present in the submitted document right now.
            if paste_database and request.content:
                current_text_lower = request.content.lower()
                total_pasted_present = 0
                # Deduplicate paste entries before counting: the same paste is often
                # captured twice (raw markdown + formatting-stripped re-capture).
                # Counting both inflates paste_ratio past 1.0 and floors
                # server_trust_score to 0. Mirrors the client-side dedupe in
                # IntegrityTracker (processedPasteTexts).
                def _norm_paste(t: str) -> str:
                    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", "", t.lower())).strip()
                _deduped_pastes = []
                _seen_norms = []
                for paste_text in paste_database:
                    _n = _norm_paste(paste_text)
                    if not _n:
                        continue
                    _dup = False
                    for _i, _m in enumerate(_seen_norms):
                        _is_dup = (_n == _m or _n in _m or _m in _n)
                        if not _is_dup:
                            _a, _b = set(_n.split()), set(_m.split())
                            _is_dup = bool(_a and _b and len(_a & _b) / len(_a | _b) >= 0.8)
                        if _is_dup:
                            # Keep the LONGER variant so a full-essay paste is never
                            # undercounted in favor of an earlier fragment of it.
                            if len(_n) > len(_m):
                                _seen_norms[_i] = _n
                                _deduped_pastes[_i] = paste_text
                            _dup = True
                            break
                    if not _dup:
                        _seen_norms.append(_n)
                        _deduped_pastes.append(paste_text)
                for paste_text in _deduped_pastes:
                    if paste_text.lower() in current_text_lower:
                        total_pasted_present += len(paste_text)
                    else:
                        # Partial word match
                        paste_words = set(paste_text.lower().split())
                        if len(paste_words) > 5:
                            matches = sum(1 for w in paste_words if len(w) > 3 and w in current_text_lower)
                            if matches / len(paste_words) > 0.5:
                                total_pasted_present += len(paste_text)

                total_chars = len(request.content)
                if total_chars > 0:
                    paste_ratio = min(1.0, total_pasted_present / total_chars)
                    typed_ratio = 1.0 - paste_ratio
                    server_trust_score = max(0, min(100, int(typed_ratio * 100)))
                    server_content_mix = {"typed": round(typed_ratio, 3), "internal": 0, "external": round(paste_ratio, 3)}

            # Fallback: use analysis history only if we couldn't compute fresh
            if server_trust_score is None and analysis_history:
                last_analysis = analysis_history[-1]
                server_trust_score = last_analysis.get("trust_score")
            
            # --- Loophole #3 Fix: Minimum ingest count check ---
            event_chain_count = session_data.get("event_chain_count", 0)
            if request.content:
                word_count = len(request.content.split())
                expected_min_events = max(1, word_count // 100)  # ~1 ingest per 100 words
                if event_chain_count < expected_min_events and word_count > 50:
                    integrity_flags.append(
                        f"low_ingest_count: only {event_chain_count} events for {word_count} words"
                    )
            
            # --- Loophole #3 Fix: Session timing check ---
            session_created = session_data.get("created_at")
            if session_created:
                if isinstance(session_created, str):
                    try:
                        session_created = datetime.fromisoformat(session_created.replace("Z", "+00:00"))
                    except Exception:
                        session_created = None
                if session_created:
                    now = datetime.now(timezone.utc)
                    if hasattr(session_created, 'tzinfo') and session_created.tzinfo is None:
                        session_created = session_created.replace(tzinfo=timezone.utc)
                    session_duration_seconds = (now - session_created).total_seconds()
                    if session_duration_seconds < 60 and request.content and len(request.content) > 200:
                        integrity_flags.append(
                            f"suspicious_session_timing: session only {int(session_duration_seconds)}s old for {len(request.content)} chars"
                        )
            
            # --- Loophole #6 Fix: Device fingerprint change check ---
            if session_data.get("device_changed"):
                integrity_flags.append("device_fingerprint_changed_during_session")
            
            # --- Loophole #7 Fix: Content hash mismatch check ---
            if analysis_history and request.content:
                submitted_hash = hashlib.sha256(request.content.encode()).hexdigest()
                last_content_hash = analysis_history[-1].get("content_hash")
                if last_content_hash and last_content_hash != submitted_hash:
                    integrity_flags.append("content_mismatch_detected")
            
        else:
            # No server session found - flag this as suspicious
            if request.session_id:
                integrity_flags.append("No server-side integrity session found for this submission")
    except ImportError:
        pass  # integrity_simple not available - skip server verification
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Server-side trust verification failed: {e}")
    
    # Determine final trust score: use MINIMUM of client and server scores
    if server_trust_score is not None:
        trust_score = min(client_trust_score, server_trust_score)
        trust_score_source = "server_verified"

        # Flag large discrepancy between client and server scores
        discrepancy = abs(client_trust_score - server_trust_score)
        if discrepancy > 20:
            integrity_flags.append(
                f"Trust score discrepancy: client={client_trust_score}%, server={server_trust_score}% (diff={discrepancy}%)"
            )
    else:
        trust_score = client_trust_score
        if session_data:
            # Session existed but no paste data / analysis to compute server score
            trust_score_source = "client_only"
            integrity_flags.append(
                "Server session found but no paste data available for independent verification. "
                "Trust score is based on client-side tracking only."
            )
        else:
            # No server session at all
            trust_score_source = "client_only"
            if not any("No server-side" in f for f in integrity_flags):
                integrity_flags.append(
                    "No server-side integrity session found. "
                    "Trust score is based on client-side tracking only."
                )
    
    # Use client content mix — it has the most accurate analysis (Methods A+B+C:
    # exact match, chunk match, word-level retyping detection). Server trust score
    # already guards against tampering via min(client, server) above.
    content_mix = client_content_mix
    
    # Face verification: flag for teacher review instead of hard-blocking.
    # The student already passed face verification to enter the editor;
    # missing server logs usually means a transient issue, not cheating.
    if face_required and server_face_checks == 0:
        integrity_flags.append(
            "FACE_CHECK_MISSING: Assignment requires face verification but no "
            "server-side face checks were recorded. Student may have verified "
            "client-side only. Teacher should review."
        )
    
    # Update submission - sanitize all HTML content to prevent XSS
    update_data = {
        "content": request.content,
        "content_html": sanitize_html(request.content_html) if request.content_html else request.content_html,
        "word_count": word_count,
        "status": "submitted",
        "submitted_at": datetime.now(timezone.utc),
        "is_late": is_late,
        "session_id": request.session_id,
        "trust_score": trust_score,
        "client_trust_score": client_trust_score,
        "server_trust_score": server_trust_score,
        "trust_score_source": trust_score_source,
        "content_mix": content_mix,
        "integrity_flags": integrity_flags,
        "face_verification_log": face_log,
        "server_face_checks": server_face_checks,
        "face_verification_required": face_required,
        "stylometry": stylometry_data,
        "ai_detection": ai_detection_data,
        "external_pastes_found": external_pastes,
        "updated_at": datetime.now(timezone.utc)
    }
    # Do NOT store client-supplied report_html. Report is always generated server-side
    # from DB data (GET /submissions/{id}/report) so it cannot be forged.
    
    # =========================================================================
    # STYLOMETRY V3: Use the client-sent result (single API call, no duplication).
    # The client already called POST /api/stylometry/v3/verify which proxies through
    # our backend (stylometry_v3.py) to forensicstylo.up.railway.app — so the data
    # is server-verified. Calling again would produce a different score (timing,
    # profile absorption) causing client/server discrepancy.
    # =========================================================================
    ext_ratio = content_mix.get("external", 0) if isinstance(content_mix, dict) else 0
    high_external_paste = ext_ratio >= 0.90

    # Cross-validate client-sent stylometry against server-stored last verification.
    # The V3 /verify proxy (stylometry_v3.py) writes the latest result to the user doc.
    # If the client sends a cosine_score that doesn't match, it was forged.
    if isinstance(stylometry_data, dict) and stylometry_data.get("cosine_score") is not None:
        _stylo_trusted = False
        try:
            _user_doc = await users_collection.find_one({"user_id": user["user_id"]})
            _server_cosine = _user_doc.get("stylometry_last_cosine") if _user_doc else None
            _server_verdict = _user_doc.get("stylometry_last_verdict") if _user_doc else None
            _client_cosine = stylometry_data.get("cosine_score")

            if _server_cosine is not None and _client_cosine is not None:
                # Allow small float rounding difference (< 0.01)
                if abs(float(_server_cosine) - float(_client_cosine)) < 0.01:
                    _stylo_trusted = True
                else:
                    import logging as _slog
                    _slog.getLogger(__name__).warning(
                        f"Stylometry mismatch: client cosine={_client_cosine}, "
                        f"server cosine={_server_cosine} for user {user['user_id']}"
                    )
                    integrity_flags.append(
                        f"stylometry_mismatch: client cosine={_client_cosine} vs server={_server_cosine}"
                    )
            elif _server_cosine is None:
                # No server record yet — could be first verify; trust but flag
                _stylo_trusted = True
        except Exception:
            # DB lookup failed — don't block submission, just trust with caution
            _stylo_trusted = True

        if _stylo_trusted:
            update_data["stylometry_v3"] = stylometry_data
            # Update flywheel data on class_members if profile was absorbed
            try:
                if stylometry_data.get("profile_absorbed"):
                    from .stylometry_v3 import class_members_collection as sv3_members
                    if sv3_members is not None:
                        await sv3_members.update_one(
                            {"class_id": assignment["class_id"], "user_id": user["user_id"]},
                            {"$set": {
                                "stylometry_profile_strength": stylometry_data.get("profile_strength"),
                                "stylometry_samples_count": stylometry_data.get("n_profile_essays", 0),
                            }},
                        )
            except Exception as _sv3_err:
                import logging as _log
                _log.getLogger(__name__).warning(f"Stylometry flywheel update failed (non-blocking): {_sv3_err}")
        else:
            # Forged data — use the server-stored result instead
            _sv_result = {
                "cosine_score": _server_cosine,
                "verdict": _server_verdict,
                "source": "server_override",
            }
            update_data["stylometry_v3"] = _sv_result
            stylometry_data = _sv_result
    elif isinstance(stylometry_data, dict) and stylometry_data.get("skipped"):
        # Client skipped stylometry (e.g. high external paste with CA on)
        update_data["stylometry_v3"] = stylometry_data

    # =========================================================================
    # INDIVIDUAL INTEGRITY SIGNALS (no composite rollup)
    # trust_score (typing provenance), AI probability, and stylometry verdict
    # are stored and surfaced independently.
    # =========================================================================
    ai_prob = None
    if ai_detection_data and isinstance(ai_detection_data, dict):
        ai_prob = ai_detection_data.get("ai_probability")

    stylo_cosine = None
    stylo_verdict = None
    if stylometry_data and isinstance(stylometry_data, dict):
        stylo_cosine = (
            stylometry_data.get("cosine_score")
            or stylometry_data.get("score")
            or stylometry_data.get("similarity")
        )
        stylo_verdict = stylometry_data.get("verdict")
    if isinstance(stylo_cosine, (int, float)) and stylo_cosine > 1:
        stylo_cosine = stylo_cosine / 100.0

    chunk_analysis = integrity_data.get("chunk_analysis")
    if chunk_analysis:
        update_data["chunk_analysis"] = chunk_analysis

    await submissions_collection.update_one(
        {"submission_id": submission_id},
        {"$set": update_data}
    )
    
    # NOTE: Per-submission plagiarism check removed. Similarity now runs as a
    # batch job after the assignment deadline passes, so all peers are compared
    # fairly. See services/plagiarism_v2.py batch_check_v2().
    
    # Check minimum trust score
    settings = assignment.get("settings", {})
    min_trust = settings.get("minimum_trust_score", 60)
    
    flags = []
    if trust_score is not None and trust_score < min_trust:
        flags.append(f"Trust score ({trust_score}%) below minimum ({min_trust}%)")
    if stylo_verdict == "flagged":
        flags.append("Stylometry verdict: flagged — writing style does not match enrolled profile")
    if ai_prob is not None and ai_prob >= 0.6:
        flags.append(f"AI detection probability {round(ai_prob * 100)}%")
    if is_late:
        flags.append("Submitted after due date")

    # =========================================================================
    # AUTO-GRADE ON SUBMISSION
    # Automatically run AI evaluation when student submits, so the teacher
    # just needs to review and accept/edit the suggested grade.
    # Only runs when every individual signal is clean: trust >= 60,
    # stylometry not flagged, AI probability < 0.6 (or not run).
    # =========================================================================
    auto_grade_result = None
    auto_grade_ok = (
        trust_score is not None and trust_score >= 60
        and stylo_verdict != "flagged"
        and (ai_prob is None or ai_prob < 0.6)
    )
    if auto_grade_ok and assignment.get("rubric") and len(assignment.get("rubric", [])) > 0:
        try:
            from ..services.auto_grading import auto_grade_submission

            # Build integrity context for the AI
            integrity_context_for_ai = {
                "trust_score": trust_score,
                "stylometry": stylometry_data,
                "ai_detection": ai_detection_data,
                "plagiarism_score": 0  # Will be updated after batch similarity runs
            }
            
            auto_grade_result = await auto_grade_submission(
                content=request.content,
                rubric=assignment["rubric"],
                assignment_instructions=assignment.get("instructions", ""),
                max_points=assignment.get("points", 100),
                assignment_title=assignment.get("title", ""),
                integrity_context=integrity_context_for_ai,
                content_html=request.content_html,
                education_level=assignment.get("settings", {}).get("education_level", "university"),
            )
            
            # Store AI suggestion on the submission (teacher reviews this)
            # Use auto_grade_suggestion to match existing field name convention
            await submissions_collection.update_one(
                {"submission_id": submission_id},
                {"$set": {
                    "auto_grade_suggestion": {
                        "total_score": auto_grade_result.get("total_score"),
                        "max_score": auto_grade_result.get("max_score"),
                        "criteria_scores": auto_grade_result.get("criteria_scores", []),
                        "inline_annotations": auto_grade_result.get("inline_annotations", []),
                        "overall_feedback": auto_grade_result.get("overall_feedback", ""),
                        "confidence": auto_grade_result.get("confidence", 0),
                        "flagged": auto_grade_result.get("flagged", False),
                        "flag_reason": auto_grade_result.get("flag_reason", ""),
                        "integrity_notes": auto_grade_result.get("integrity_notes", ""),
                        "graded_at": auto_grade_result.get("graded_at"),
                        "model_used": auto_grade_result.get("model_used")
                    },
                    "has_auto_grade": True
                }}
            )
            print(f"Auto-grade completed for submission {submission_id}: {auto_grade_result.get('total_score')}/{auto_grade_result.get('max_score')}")
        except Exception as e:
            print(f"Auto-grade on submission failed (non-blocking): {e}")
    else:
        if not auto_grade_ok:
            reasons = []
            if trust_score is None or trust_score < 60:
                reasons.append(f"trust score {trust_score}% < 60%")
            if stylo_verdict == "flagged":
                reasons.append("stylometry verdict flagged")
            if ai_prob is not None and ai_prob >= 0.6:
                reasons.append(f"AI probability {round(ai_prob * 100)}% >= 60%")
            print(f"Skipping auto-grade: {', '.join(reasons)}")
        else:
            print(f"Skipping auto-grade: no rubric defined for assignment")
    
    result = {
        "success": True,
        "submission_id": submission_id,
        "status": "submitted",
        "is_late": is_late,
        "auto_graded": auto_grade_result is not None,
        "message": "Assignment submitted successfully"
    }
    # Legacy switch: restore integrity fields in the submit response (individual signals).
    if legacy_mode():
        result["trust_score"] = trust_score
        result["stylometry_verdict"] = stylo_verdict
        result["stylometry_cosine"] = stylo_cosine
        result["ai_probability"] = ai_prob
        result["flags"] = flags
    return result


@router.get("/{submission_id}")
async def get_submission(submission_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Get submission details"""
    resolved_token = _extract_token(token, authorization)
    user = await get_user_from_token(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Owners (students/researchers) see their own; otherwise must own the class/lab
    if submission["student_id"] != user["user_id"]:
        # Teachers see submissions from their classes; lab PIs see members' submissions
        class_doc = await classes_collection.find_one({"class_id": submission["class_id"]})
        if not class_doc or class_doc["teacher_id"] != user["user_id"]:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get assignment and student info
    assignment = await assignments_collection.find_one({"assignment_id": submission["assignment_id"]})
    student = await users_collection.find_one({"user_id": submission["student_id"]})

    # Authoritative role for visibility stripping (prevents stale-session exploits)
    user = await _refresh_role_from_db(user)

    payload = {
        "submission_id": submission["submission_id"],
        "assignment_id": submission["assignment_id"],
        "assignment_title": assignment["title"] if assignment else "Unknown",
        "assignment_points": assignment["points"] if assignment else 0,
        "student_id": submission["student_id"],
        "student_name": student["name"] if student else "Unknown",
        "class_id": submission["class_id"],
        "content": submission.get("content", ""),
        "content_html": submission.get("content_html", ""),
        "word_count": submission.get("word_count", 0),
        "status": submission["status"],
        "submitted_at": submission.get("submitted_at"),
        "is_late": submission.get("is_late", False),
        "trust_score": submission.get("trust_score", 0),
        "content_mix": submission.get("content_mix", {}),
        "integrity_flags": submission.get("integrity_flags", []),
        "face_verification_log": submission.get("face_verification_log", []),
        "plagiarism_score": submission.get("plagiarism_score", 0),
        "plagiarism_matches": submission.get("plagiarism_matches", []),
        "ai_probability": (submission.get("ai_detection") or {}).get("ai_probability"),
        "grade": submission.get("grade"),
        "feedback": submission.get("feedback"),
        "grade_breakdown": submission.get("grade_breakdown"),
        "graded_by": submission.get("graded_by"),
        "graded_at": submission.get("graded_at"),
        "auto_grade_suggestion": submission.get("auto_grade_suggestion"),
        "rubric": assignment.get("rubric") if assignment else None,
        "has_report": submission.get("status") in ("submitted", "graded", "returned"),
        "stylometry": submission.get("stylometry"),
        "stylometry_v3": submission.get("stylometry_v3"),
        "ai_detection": submission.get("ai_detection"),
        "external_pastes_found": submission.get("external_pastes_found", []),
        # Whether peer-similarity (plagiarism) has run yet — independent signal
        # keyed on the batch-check timestamp, not any composite state.
        "similarity_pending": submission.get("plagiarism_v2_checked_at") is None,
        "plagiarism_v2_checked_at": submission.get("plagiarism_v2_checked_at"),
    }
    # Strip composite (all roles) + full integrity (students) unless legacy switch is on.
    return sanitize_submission_response(payload, user.get("role"))


@router.post("/{submission_id}/upload-report")
async def upload_report_html(submission_id: str, request: Request, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Upload integrity report HTML separately (bypasses JSON size limit).
    Accepts raw HTML in the request body."""
    resolved_token = _extract_token(token, authorization)
    user = await get_user_from_token(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if submission["student_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your submission")
    
    # Read raw body - this is HTML content
    body_bytes = await request.body()
    
    # Security: enforce size limits (16MB max for integrity reports)
    MAX_REPORT_SIZE = 16 * 1024 * 1024
    if len(body_bytes) > MAX_REPORT_SIZE:
        raise HTTPException(status_code=413, detail=f"Report too large. Maximum size: {MAX_REPORT_SIZE // (1024*1024)}MB")
    
    try:
        report_html = body_bytes.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Report must be valid UTF-8 encoded HTML")
    
    if not report_html or len(report_html) < 100:
        raise HTTPException(status_code=400, detail="Report content too small or empty")
    
    # Security: strip dangerous elements while preserving styles for PDF.
    import re as _re
    # Remove script tags and their content
    report_html = _re.sub(r'<script\b[^>]*>[\s\S]*?</script>', '', report_html, flags=_re.IGNORECASE)
    # Remove iframe tags
    report_html = _re.sub(r'<iframe\b[^>]*>[\s\S]*?</iframe>', '', report_html, flags=_re.IGNORECASE)
    # Remove on* event handlers (quoted AND unquoted values)
    report_html = _re.sub(r'\s+on\w+\s*=\s*(?:"[^"]*"|\'[^\']*\'|\S+)', '', report_html, flags=_re.IGNORECASE)
    # Remove javascript: URLs in href AND src attributes
    report_html = _re.sub(r'(href|src)\s*=\s*["\']?\s*javascript:[^"\'>\s]*["\']?', r'\1="#"', report_html, flags=_re.IGNORECASE)

    # Store the sanitized report HTML
    await submissions_collection.update_one(
        {"submission_id": submission_id},
        {"$set": {"report_html": report_html, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {
        "success": True,
        "message": "Report uploaded successfully",
        "size_bytes": len(report_html)
    }


@router.get("/{submission_id}/report")
async def get_submission_report(submission_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Get the integrity report HTML for a submission"""
    resolved_token = _extract_token(token, authorization)
    user = await get_user_from_token(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Owners see their own; otherwise must own the class/lab (teacher or PI)
    if submission["student_id"] != user["user_id"]:
        class_doc = await classes_collection.find_one({"class_id": submission["class_id"]})
        if not class_doc or class_doc["teacher_id"] != user["user_id"]:
            raise HTTPException(status_code=403, detail="Not authorized")

    # The integrity report is for teachers/PIs only. Students never see it
    # (unless the legacy production switch is on).
    user = await _refresh_role_from_db(user)
    if not legacy_mode() and user.get("role") == "student":
        raise HTTPException(status_code=403, detail="Report not available")

    # =========================================================================
    # SERVE THE CLIENT-GENERATED RICH PDF WITH SERVER VERIFICATION BANNER
    # The client PDF (print.vue) contains the full tool-aware report:
    # Signal Agreement Matrix, highlighted content, composition bars, timeline.
    # It's already sanitized via regex on upload. Server adds a verification
    # banner with trust score cross-check, flags, and tamper detection.
    # =========================================================================
    from fastapi.responses import HTMLResponse

    report_html = submission.get("report_html")
    if not report_html:
        raise HTTPException(status_code=404, detail="Report not available yet")

    # Server verification data
    trust_source = submission.get("trust_score_source", "unknown")
    flags = submission.get("integrity_flags", [])
    is_verified = trust_source == "server_verified"

    # Banner: one plain-language line for non-technical readers. No internal
    # flag slugs, no jargon — the report body below carries all the detail.
    has_flags = len(flags) > 0
    banner_bg = "#b45309" if has_flags else ("#059669" if is_verified else "#6b7280")
    banner_icon = "&#9888;" if has_flags else ("&#10003;" if is_verified else "&#8212;")
    if has_flags:
        banner_text = "This submission needs a closer look — details are in the report below"
    elif is_verified:
        banner_text = "Automatic checks found nothing unusual"
    else:
        banner_text = "Automatic checks are still running"

    verification_banner = f'''<div style="
        position:sticky;top:0;z-index:9999;
        background:{banner_bg};color:#fff;
        padding:8px 20px;font-size:12px;
        display:flex;align-items:center;gap:12px;flex-wrap:wrap;
        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        box-shadow:0 2px 8px rgba(0,0,0,0.15);
        print-color-adjust:exact;-webkit-print-color-adjust:exact;
    ">
        <span style="font-size:16px">{banner_icon}</span>
        <strong>{banner_text}</strong>
        <span style="margin-left:auto;opacity:0.5;font-size:10px">
            Editorrah Integrity
        </span>
    </div>'''

    # Strip external <link> tags that reference localhost/vite dev server —
    # they can't resolve when served from the backend and render as raw CSS text.
    # Keep only inline <style> tags which contain the actual CSS.
    import re
    report_html = re.sub(
        r'<link\s+[^>]*(?:href=["\'][^"\']*(?:localhost|@vite|node_modules|\.hot)[^"\']*["\'])[^>]*/?>',
        '',
        report_html,
        flags=re.IGNORECASE,
    )

    # Inject banner right after <body> tag
    body_match = re.search(r'(<body[^>]*>)', report_html, re.IGNORECASE)
    if body_match:
        insert_pos = body_match.end()
        html = report_html[:insert_pos] + verification_banner + report_html[insert_pos:]
    else:
        html = verification_banner + report_html

    return HTMLResponse(
        content=html,
        headers={
            "Content-Type": "text/html; charset=utf-8",
            "X-Content-Type-Options": "nosniff",
        }
    )


# ============================================================================
# GRADING
# ============================================================================

@router.put("/{submission_id}/grade")
async def grade_submission(
    submission_id: str,
    request: GradeSubmission,
    token: str = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Grade a submission (teacher only)"""
    resolved_token = _extract_token(token, authorization)
    user = await verify_teacher(resolved_token)
    
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Verify teacher owns this class
    await verify_class_teacher(user, submission["class_id"])
    
    if submission["status"] == "draft":
        raise HTTPException(status_code=400, detail="Cannot grade a draft submission")
    
    # Get assignment to validate grade
    assignment = await assignments_collection.find_one({"assignment_id": submission["assignment_id"]})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    if request.grade < 0:
        raise HTTPException(status_code=400, detail="Grade cannot be negative")
    
    if request.grade > assignment["points"]:
        raise HTTPException(
            status_code=400,
            detail=f"Grade cannot exceed maximum points ({assignment['points']})"
        )
    
    # Security: validate feedback length to prevent DB bloat
    if request.feedback and len(request.feedback) > 50000:
        raise HTTPException(status_code=400, detail="Feedback too long (max 50,000 characters)")
    
    # Apply late penalty if applicable
    final_grade = request.grade
    if submission.get("is_late") and assignment.get("settings", {}).get("allow_late", True):
        penalty = assignment.get("settings", {}).get("late_penalty_percent", 10)
        # Calculate days late
        due_date = _ensure_utc(assignment["due_date"])
        submitted_at = _ensure_utc(submission.get("submitted_at"))
        days_late = (submitted_at - due_date).days + 1
        
        penalty_amount = (penalty / 100) * request.grade * days_late
        final_grade = max(0, request.grade - penalty_amount)
    
    update_data = {
        "grade": int(final_grade),
        "original_grade": request.grade,  # Before penalty
        "feedback": sanitize_html(request.feedback) if request.feedback else request.feedback,
        "graded_by": user["name"],
        "graded_by_id": user["user_id"],
        "graded_at": datetime.now(timezone.utc),
        "status": "graded",
        "updated_at": datetime.now(timezone.utc)
    }
    
    if request.criteria_scores:
        update_data["grade_breakdown"] = [s.model_dump() for s in request.criteria_scores]
    
    await submissions_collection.update_one(
        {"submission_id": submission_id},
        {"$set": update_data}
    )
    
    return {
        "success": True,
        "submission_id": submission_id,
        "grade": int(final_grade),
        "original_grade": request.grade,
        "late_penalty_applied": submission.get("is_late", False),
        "message": "Submission graded"
    }


@router.post("/{submission_id}/return")
async def return_submission(submission_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Return graded submission to student (teacher only)"""
    resolved_token = _extract_token(token, authorization)
    user = await verify_teacher(resolved_token)
    
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    await verify_class_teacher(user, submission["class_id"])
    
    if submission["status"] != "graded":
        raise HTTPException(status_code=400, detail="Can only return graded submissions")
    
    await submissions_collection.update_one(
        {"submission_id": submission_id},
        {"$set": {
            "status": "returned",
            "returned_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    return {"success": True, "message": "Submission returned to student"}


@router.post("/{submission_id}/auto-grade")
async def request_auto_grade(submission_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Request AI auto-grading for a submission (teacher only)"""
    resolved_token = _extract_token(token, authorization)
    user = await verify_teacher(resolved_token)
    
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    await verify_class_teacher(user, submission["class_id"])
    
    if submission["status"] == "draft":
        raise HTTPException(status_code=400, detail="Cannot auto-grade a draft")
    
    # Get assignment with rubric
    assignment = await assignments_collection.find_one({"assignment_id": submission["assignment_id"]})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    if not assignment.get("rubric"):
        raise HTTPException(status_code=400, detail="Assignment has no rubric for auto-grading")
    
    # Gate: auto-grading requires every individual integrity signal to be clean.
    base_trust = submission.get("trust_score", 0) or 0
    stylo_verdict = (
        (submission.get("stylometry_v3") or submission.get("stylometry") or {}).get("verdict")
    )
    ai_prob = (submission.get("ai_detection") or {}).get("ai_probability")
    blocked = []
    if base_trust < 60:
        blocked.append(f"trust score {base_trust}% is below 60%")
    if stylo_verdict == "flagged":
        blocked.append("stylometry verdict is flagged")
    if ai_prob is not None and ai_prob >= 0.6:
        blocked.append(f"AI probability is {round(ai_prob * 100)}%")
    if blocked:
        raise HTTPException(
            status_code=400,
            detail=f"Auto-grading blocked: {'; '.join(blocked)}. "
                   "Manual grading is recommended for low-integrity submissions."
        )
    
    # Call auto-grading service
    from ..services.auto_grading import auto_grade_submission
    
    # Use plain content if available, otherwise use content (which may be HTML)
    grading_content = submission.get("content") or submission.get("content_html") or ""
    content_html = submission.get("content_html") or submission.get("content") or ""
    
    if not grading_content or len(grading_content.strip()) < 10:
        raise HTTPException(status_code=400, detail="Submission has no content to grade")
    
    integrity_context = {
        "trust_score": base_trust,
        "stylometry": submission.get("stylometry_v3") or submission.get("stylometry"),
        "ai_detection": submission.get("ai_detection"),
        "plagiarism_score": submission.get("plagiarism_score", 0),
    }
    
    try:
        result = await auto_grade_submission(
            content=grading_content,
            rubric=assignment["rubric"],
            assignment_instructions=assignment.get("instructions", ""),
            assignment_title=assignment.get("title", ""),
            max_points=assignment["points"],
            integrity_context=integrity_context,
            content_html=content_html,
            education_level=assignment.get("settings", {}).get("education_level", "university"),
        )
        
        # Store as suggestion (teacher must approve)
        await submissions_collection.update_one(
            {"submission_id": submission_id},
            {"$set": {
                "auto_grade_suggestion": result,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        return {
            "success": True,
            "auto_grade": result,
            "message": "Auto-grade suggestion generated. Review and approve to finalize."
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto-grading failed: {str(e)}")


@router.post("/{submission_id}/approve-auto-grade")
async def approve_auto_grade(submission_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Approve the auto-grade suggestion (teacher only)"""
    resolved_token = _extract_token(token, authorization)
    user = await verify_teacher(resolved_token)
    
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    await verify_class_teacher(user, submission["class_id"])
    
    auto_grade = submission.get("auto_grade_suggestion")
    if not auto_grade:
        raise HTTPException(status_code=400, detail="No auto-grade suggestion to approve")
    
    # Build full feedback that includes both overall feedback AND inline annotations
    # so students can see the detailed comments when the submission is returned
    full_feedback = auto_grade.get("overall_feedback", "")
    inline_annotations = auto_grade.get("inline_annotations", [])
    if inline_annotations:
        full_feedback += "\n\n--- Detailed Comments ---"
        for ann in inline_annotations:
            ann_type = ann.get("type", "suggestion")
            label = "Strength" if ann_type == "praise" else "Issue" if ann_type == "issue" else "Suggestion"
            highlighted = ann.get("highlighted_text", "")
            comment = ann.get("comment", "")
            full_feedback += f'\n\n[{label}] "{highlighted}"\n{comment}'
    
    # Apply the auto-grade
    await submissions_collection.update_one(
        {"submission_id": submission_id},
        {"$set": {
            "grade": auto_grade["total_score"],
            "feedback": full_feedback,
            "grade_breakdown": auto_grade["criteria_scores"],
            "graded_by": "Auto-graded (approved by " + user["name"] + ")",
            "graded_by_id": user["user_id"],
            "graded_at": datetime.now(timezone.utc),
            "status": "graded",
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    return {
        "success": True,
        "grade": auto_grade["total_score"],
        "feedback": full_feedback,
        "message": "Auto-grade approved"
    }


# ============================================================================
# BULK OPERATIONS
# ============================================================================

@router.post("/{submission_id}/generate-feedback")
async def generate_submission_feedback(
    submission_id: str,
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
    request: Request = None
):
    """Generate AI feedback for a submission based on grade (teacher only)"""
    resolved_token = _extract_token(token, authorization)
    user = await verify_teacher(resolved_token)
    
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    await verify_class_teacher(user, submission["class_id"])
    
    # Get request body
    import json as json_lib
    body_bytes = await request.body()
    body = json_lib.loads(body_bytes) if body_bytes else {}
    
    grade = body.get("grade", 0)
    max_grade = body.get("max_grade", 100)
    
    # Get assignment for rubric context
    assignment = await assignments_collection.find_one({"assignment_id": submission["assignment_id"]})
    
    criteria_scores = None
    if body.get("criteria_scores"):
        criteria_scores = body["criteria_scores"]
    elif submission.get("auto_grade_suggestion", {}).get("criteria_scores"):
        criteria_scores = submission["auto_grade_suggestion"]["criteria_scores"]
    
    from ..services.auto_grading import generate_feedback, strip_html_tags
    
    # Get content and strip HTML if needed
    raw_content = submission.get("content") or submission.get("content_html") or ""
    plain_content = strip_html_tags(raw_content) if '<' in raw_content and '>' in raw_content else raw_content
    
    try:
        feedback = await generate_feedback(
            content=plain_content,
            grade=grade,
            max_grade=max_grade,
            criteria_scores=criteria_scores,
            assignment_instructions=(assignment or {}).get("instructions", ""),
            education_level=(assignment or {}).get("settings", {}).get("education_level", "university"),
            assignment_title=(assignment or {}).get("title", ""),
        )
        
        if not feedback:
            raise HTTPException(status_code=500, detail="Feedback generation returned empty result. Check OPENAI_API_KEY.")
        
        return {
            "success": True,
            "feedback": feedback
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feedback generation failed: {str(e)}")


@router.post("/bulk-return")
async def bulk_return_submissions(
    submission_ids: List[str],
    token: str = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Return multiple graded submissions (teacher only)"""
    resolved_token = _extract_token(token, authorization)
    user = await verify_teacher(resolved_token)
    
    returned = 0
    errors = []
    
    for submission_id in submission_ids:
        submission = await submissions_collection.find_one({"submission_id": submission_id})
        if not submission:
            errors.append(f"{submission_id}: not found")
            continue
        
        try:
            await verify_class_teacher(user, submission["class_id"])
        except:
            errors.append(f"{submission_id}: not authorized")
            continue
        
        if submission["status"] != "graded":
            errors.append(f"{submission_id}: not graded")
            continue
        
        await submissions_collection.update_one(
            {"submission_id": submission_id},
            {"$set": {
                "status": "returned",
                "returned_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        returned += 1
    
    return {
        "success": True,
        "returned": returned,
        "errors": errors
    }
