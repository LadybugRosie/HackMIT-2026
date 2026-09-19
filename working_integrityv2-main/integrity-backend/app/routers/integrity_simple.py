"""
SIMPLE INTEGRITY BACKEND - Permanent paste database with text matching
NOW WITH: MongoDB persistence, authentication, session ownership, append-only paste DB

Fixes applied:
 #1  - All endpoints require authentication
 #2  - Sessions persisted in MongoDB (survive restarts/scaling)
 #4  - Paste database is append-only (client cannot erase evidence)
 #5  - Sessions bound to user_id (cross-student tampering blocked)
 #19 - TTL index on sessions (auto-cleanup, no memory leak)
"""

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import time
import hashlib
import json
import os
import logging
from datetime import datetime, timezone, timedelta

from app.utils.signer import sign, verify, create_signed_response
from app.utils.event_chain import EventChain

logger = logging.getLogger(__name__)

router = APIRouter()

# MongoDB collection (set by main.py)
integrity_sessions_collection = None

def set_integrity_sessions_collection(collection):
    global integrity_sessions_collection
    integrity_sessions_collection = collection


# ============================================================================
# BACKWARD COMPAT: GLOBAL_SESSIONS reads from MongoDB now
# submissions.py imports GLOBAL_SESSIONS -- we keep the name but make it a
# MongoDB-backed wrapper so the trust-score algorithm in submissions.py is
# unchanged.
# ============================================================================
class _LRUCache:
    """Bounded LRU cache to prevent unbounded memory growth with many sessions."""
    def __init__(self, max_size: int = 10_000):
        from collections import OrderedDict
        self._data: 'OrderedDict[str, Any]' = OrderedDict()
        self._max_size = max_size

    def get(self, key: str, default=None):
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        return default

    def set(self, key: str, value):
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        while len(self._data) > self._max_size:
            self._data.popitem(last=False)  # Evict least-recently-used

    def __contains__(self, key: str):
        return key in self._data

    def __getitem__(self, key: str):
        return self.get(key)


class _MongoSessionProxy(dict):
    """Dict-like proxy that reads from MongoDB synchronously for .get() calls
    made by submissions.py during the submit flow.  Uses a bounded LRU cache
    to prevent unbounded memory growth across workers."""

    def __init__(self):
        super().__init__()
        self._cache = _LRUCache(max_size=10_000)

    def _update_cache(self, session_id: str, data: dict):
        self._cache.set(session_id, data)

    def get(self, session_id, default=None):
        return self._cache.get(session_id, default)

    def __contains__(self, session_id):
        return session_id in self._cache

    def __getitem__(self, session_id):
        return self._cache[session_id]

GLOBAL_SESSIONS = _MongoSessionProxy()

# Event chains per session (bounded LRU to prevent memory leaks)
EVENT_CHAINS: _LRUCache = _LRUCache(max_size=10_000)


# ============================================================================
# AUTH HELPER
# ============================================================================
async def _get_current_user(token: Optional[str] = None, authorization: Optional[str] = None):
    """Extract and verify the user from token/header."""
    from .auth import get_current_user
    # Prefer Authorization header
    resolved_token = None
    if authorization:
        if authorization.startswith('Bearer '):
            resolved_token = authorization[7:]
        else:
            resolved_token = authorization
    elif token:
        resolved_token = token
    if not resolved_token:
        return None
    return await get_current_user(resolved_token)


def _require_user(user):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required for integrity tracking")
    return user


# ============================================================================
# MODELS
# ============================================================================
class SessionStart(BaseModel):
    session_id: Optional[str] = None  # Optional: server generates if not provided
    doc_id: Optional[str] = None
    strict_mode: Optional[bool] = False
    device_fingerprint: Optional[str] = None  # Loophole #6: device binding

class AnalyzeRequest(BaseModel):
    session_id: str
    doc_id: str
    current_text: str
    paste_database: List[str]
    analysis: Dict

class DatabaseSaveRequest(BaseModel):
    session_id: str
    paste_database: Dict[str, Any]


# ============================================================================
# MONGODB HELPERS
# ============================================================================
async def _get_session(session_id: str) -> Optional[dict]:
    """Fetch session from MongoDB and update the in-memory cache."""
    if integrity_sessions_collection is None:
        return None
    doc = await integrity_sessions_collection.find_one({"session_id": session_id})
    if doc:
        GLOBAL_SESSIONS._update_cache(session_id, doc)
    return doc


async def _upsert_session(session_id: str, update_fields: dict):
    """Update session in MongoDB and sync the cache."""
    if integrity_sessions_collection is None:
        return
    await integrity_sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": {**update_fields, "updated_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    # Refresh cache
    await _get_session(session_id)


async def _append_pastes(session_id: str, new_pastes: List[str]):
    """Append-only paste addition. Cannot remove existing pastes."""
    if integrity_sessions_collection is None or not new_pastes:
        return
    await integrity_sessions_collection.update_one(
        {"session_id": session_id},
        {
            "$addToSet": {"paste_database": {"$each": new_pastes}},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }
    )
    # Refresh cache
    await _get_session(session_id)


async def _push_analysis(session_id: str, record: dict):
    """Append an analysis record to the session history."""
    if integrity_sessions_collection is None:
        return
    await integrity_sessions_collection.update_one(
        {"session_id": session_id},
        {
            "$push": {"analysis_history": record},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }
    )
    await _get_session(session_id)


# ============================================================================
# ROUTES
# ============================================================================

@router.post("/session/start")
async def start_session(
    request: SessionStart,
    token: str = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Start a new integrity session with permanent database"""
    user = _require_user(await _get_current_user(token, authorization))

    # Auto-generate session_id if not provided
    if not request.session_id:
        import uuid
        request.session_id = f"session-{uuid.uuid4().hex[:12]}-{int(time.time())}"

    existing = await _get_session(request.session_id)

    # Cross-browser fix: before creating a brand-new session, check if this
    # user already has a session for the same doc_id.  Reusing it preserves
    # the paste_database and client_state so the trust score survives browser
    # switches / incognito reopens.
    if not existing and request.doc_id:
        existing_for_doc = await integrity_sessions_collection.find_one(
            {"user_id": user["user_id"], "doc_id": request.doc_id},
            sort=[("updated_at", -1)]
        )
        if existing_for_doc:
            existing = existing_for_doc
            request.session_id = existing_for_doc["session_id"]
            GLOBAL_SESSIONS._update_cache(request.session_id, existing_for_doc)
            logger.info(f"REUSED existing session for doc {request.doc_id}: {request.session_id}")

    if not existing:
        # Create new session bound to user
        session_doc = {
            "session_id": request.session_id,
            "user_id": user["user_id"],
            "user_email": user["email"],
            "doc_id": request.doc_id,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "strict_mode": request.strict_mode,
            "paste_database": [],
            "keystroke_count": 0,
            "total_pastes": 0,
            "analysis_history": [],
            "event_chain_events": [],
            "device_fingerprint": request.device_fingerprint,  # Loophole #6
            "device_changed": False,
            "event_chain_count": 0,
            "client_state": None,
            "client_state_ts": None
        }
        await integrity_sessions_collection.insert_one(session_doc)
        GLOBAL_SESSIONS._update_cache(request.session_id, session_doc)

        # Initialize event chain
        EVENT_CHAINS.set(request.session_id, EventChain(request.session_id))
        logger.info(f"NEW Session created: {request.session_id} for user {user['email']}")
    else:
        # Verify ownership
        if existing.get("user_id") != user["user_id"]:
            raise HTTPException(status_code=403, detail="This session belongs to another user")
        logger.info(f"EXISTING Session retrieved: {request.session_id} ({len(existing.get('paste_database', []))} pastes)")

        # Rebuild event chain from stored events if needed
        if request.session_id not in EVENT_CHAINS:
            chain = EventChain(request.session_id)
            for evt in existing.get("event_chain_events", []):
                chain.events.append(evt)
            EVENT_CHAINS.set(request.session_id, chain)

    session = await _get_session(request.session_id)
    chain = EVENT_CHAINS.get(request.session_id)
    chain_summary = chain.get_chain_summary() if chain else None

    response = {
        "status": "ok",
        "session_id": request.session_id,
        "existing_pastes": len(session.get("paste_database", [])),
        "chain_head": chain_summary['head_hash'] if chain_summary else None
    }

    return create_signed_response(response)


@router.post("/database/save")
async def save_database(
    request: DatabaseSaveRequest,
    token: str = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Save paste database from frontend -- APPEND-ONLY.
    New pastes are added; existing pastes can never be removed."""
    user = _require_user(await _get_current_user(token, authorization))

    session = await _get_session(request.session_id)
    if not session:
        # Auto-create a session tied to this user
        await _upsert_session(request.session_id, {
            "session_id": request.session_id,
            "user_id": user["user_id"],
            "user_email": user["email"],
            "created_at": datetime.now(timezone.utc),
            "paste_database": [],
            "analysis_history": [],
            "event_chain_events": []
        })
        session = await _get_session(request.session_id)

    # Verify ownership
    if session and session.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="This session belongs to another user")

    # APPEND-ONLY: only ADD new pastes, never replace
    if 'pastes' in request.paste_database:
        incoming_pastes = request.paste_database['pastes']
        if isinstance(incoming_pastes, list) and incoming_pastes:
            await _append_pastes(request.session_id, incoming_pastes)
            updated = await _get_session(request.session_id)
            logger.info(f"Database appended for session {request.session_id}: +{len(incoming_pastes)} pastes, total={len(updated.get('paste_database', []))}")

    return {"status": "saved"}


@router.post("/analyze")
async def analyze_integrity(
    request: AnalyzeRequest,
    token: str = Query(None),
    authorization: Optional[str] = Header(None)
):
    """
    Analyze integrity by comparing current text against PERMANENT paste database.
    Key principle: Once pasted, ALWAYS in database. Trust score based on what's STILL in editor.

    ** TRUST SCORE ALGORITHM IS UNCHANGED **
    """
    user = _require_user(await _get_current_user(token, authorization))

    session = await _get_session(request.session_id)

    if not session:
        # Auto-create
        await _upsert_session(request.session_id, {
            "session_id": request.session_id,
            "user_id": user["user_id"],
            "user_email": user["email"],
            "created_at": datetime.now(timezone.utc),
            "paste_database": [],
            "analysis_history": [],
            "event_chain_events": []
        })
        session = await _get_session(request.session_id)

    # Verify ownership
    if session.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="This session belongs to another user")

    # Ensure event chain exists
    if request.session_id not in EVENT_CHAINS:
        chain = EventChain(request.session_id)
        for evt in session.get("event_chain_events", []):
            chain.events.append(evt)
        EVENT_CHAINS.set(request.session_id, chain)

    chain = EVENT_CHAINS.get(request.session_id)

    # Add analysis event to chain
    analysis_event = {
        "type": "analyze",
        "text_length": len(request.current_text),
        "paste_count": len(request.paste_database),
        "analysis": request.analysis
    }
    chain.add_event(analysis_event)

    # Persist chain events to MongoDB
    await integrity_sessions_collection.update_one(
        {"session_id": request.session_id},
        {"$set": {"event_chain_events": chain.events}}
    )

    # APPEND-ONLY: merge incoming pastes into permanent DB
    if request.paste_database:
        await _append_pastes(request.session_id, request.paste_database)

    # Re-fetch to get the authoritative paste database from MongoDB
    session = await _get_session(request.session_id)
    server_paste_db = session.get("paste_database", [])

    # =====================================================================
    # MATCHING ALGORITHM — bidirectional with proportional accounting
    # =====================================================================
    current_text_lower = request.current_text.lower()
    total_chars = len(request.current_text)
    total_pasted_chars_present = 0
    pastes_found = 0
    pastes_removed = 0

    for paste_text in server_paste_db:
        paste_lower = paste_text.lower()

        # --- Method 1: full paste is a substring of current doc ---
        if paste_lower in current_text_lower:
            total_pasted_chars_present += len(paste_text)
            pastes_found += 1
            continue

        # --- Method 2: current doc is a substring of paste (partial-delete case) ---
        if total_chars > 0 and current_text_lower in paste_lower:
            total_pasted_chars_present += total_chars
            pastes_found += 1
            continue

        # --- Method 3: bidirectional word matching (proportional, no cliff) ---
        paste_words = set(paste_lower.split())
        doc_words = set(current_text_lower.split())
        significant_paste_words = {w for w in paste_words if len(w) > 3}
        significant_doc_words = {w for w in doc_words if len(w) > 3}

        if significant_paste_words and significant_doc_words:
            common = significant_paste_words & significant_doc_words
            paste_dir = len(common) / len(significant_paste_words)
            doc_dir = len(common) / len(significant_doc_words)

            if doc_dir > 0.3 or paste_dir > 0.3:
                doc_chars_from_paste = int(total_chars * doc_dir)
                total_pasted_chars_present += doc_chars_from_paste
                pastes_found += 1
                continue

        # --- Method 4: character n-gram matching (catches rearranged/modified text) ---
        if total_chars > 10 and len(paste_text) > 10:
            gram_size = 8
            paste_clean = paste_lower.replace(" ", "")
            doc_clean = current_text_lower.replace(" ", "")
            paste_grams = set()
            for i in range(len(paste_clean) - gram_size + 1):
                paste_grams.add(paste_clean[i:i + gram_size])
            if paste_grams:
                doc_gram_hits = 0
                doc_gram_total = max(1, len(doc_clean) - gram_size + 1)
                for i in range(doc_gram_total):
                    if doc_clean[i:i + gram_size] in paste_grams:
                        doc_gram_hits += 1
                doc_gram_ratio = doc_gram_hits / doc_gram_total
                if doc_gram_ratio > 0.15:
                    total_pasted_chars_present += int(total_chars * doc_gram_ratio)
                    pastes_found += 1
                    continue

        pastes_removed += 1

    # Cap to document length (multiple pastes can overlap)
    total_pasted_chars_present = min(total_pasted_chars_present, total_chars) if total_chars > 0 else 0

    # =====================================================================
    # TRUST SCORE — server-side only, ignores client-supplied session totals
    # =====================================================================
    if total_chars > 0:
        paste_ratio = total_pasted_chars_present / total_chars
        typed_ratio = 1.0 - paste_ratio
        if server_paste_db and total_pasted_chars_present == 0:
            # Pastes exist in DB but nothing matched — content is unattributable.
            # Default to untrusted rather than assuming it was typed.
            trust_score = 0
        else:
            trust_score = max(0, min(100, int(typed_ratio * 100)))
    else:
        paste_ratio = 0.0
        typed_ratio = 1.0
        trust_score = 100

    # Store analysis in history
    # Loophole #7 Fix: Store content hash for mismatch detection at submission time
    content_hash = hashlib.sha256(request.current_text.encode()).hexdigest()
    
    analysis_record = {
        "timestamp": time.time(),
        "total_chars": total_chars,
        "pasted_chars_present": total_pasted_chars_present,
        "trust_score": trust_score,
        "pastes_found": pastes_found,
        "pastes_removed": pastes_removed,
        "content_hash": content_hash
    }
    await _push_analysis(request.session_id, analysis_record)

    # =====================================================================
    # RESPONSE  (*** UNCHANGED structure ***)
    # =====================================================================
    response = {
        "scores": {
            "trust": trust_score,
            "composition": 100 - int(paste_ratio * 100),
            "authenticity": trust_score
        },
        "mix": {
            "typed": typed_ratio,
            "internal": 0,
            "external": paste_ratio
        },
        "flags": [],
        "ext_spans": [],
        "metadata": {
            "total_pastes_in_db": len(server_paste_db),
            "pastes_still_present": pastes_found,
            "pastes_removed": pastes_removed,
            "pasted_chars": total_pasted_chars_present,
            "total_chars": total_chars
        }
    }

    if paste_ratio > 0.7:
        response["flags"].append("high_paste")
        response["flags"].append("low_originality")
    elif paste_ratio > 0.5:
        response["flags"].append("moderate_paste")

    if pastes_removed > pastes_found:
        response["flags"].append("significant_editing")

    # Add chain info to response
    response["chain_head"] = chain.get_head_hash()
    response["chain_valid"] = chain.verify()[0]
    response["chain_event_count"] = len(chain.events)

    return create_signed_response(response)


@router.get("/session/{session_id}/history")
async def get_session_history(
    session_id: str,
    token: str = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Get analysis history for a session"""
    user = _require_user(await _get_current_user(token, authorization))

    session = await _get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("user_id") != user["user_id"]:
        # Teachers can also view (if they have teacher role)
        if user.get("role") != "teacher":
            raise HTTPException(status_code=403, detail="Not your session")

    return {
        "session_id": session_id,
        "created_at": session.get("created_at"),
        "total_pastes": len(session.get("paste_database", [])),
        "analysis_count": len(session.get("analysis_history", [])),
        "analysis_history": session.get("analysis_history", [])
    }


@router.get("/session/lookup")
async def lookup_session(
    doc_id: str = Query(..., description="Document/assignment ID to find session for"),
    token: str = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Find existing session by user + doc_id for cross-browser restore.
    Returns client_state snapshot if available."""
    user = _require_user(await _get_current_user(token, authorization))

    session = await integrity_sessions_collection.find_one(
        {"user_id": user["user_id"], "doc_id": doc_id},
        sort=[("updated_at", -1)]
    )

    if not session:
        return {"found": False}

    return {
        "found": True,
        "session_id": session["session_id"],
        "client_state": session.get("client_state"),
        "client_state_ts": session.get("client_state_ts"),
        "existing_pastes": len(session.get("paste_database", [])),
    }


# Compatibility endpoint
@router.post("/ingest")
async def ingest_compatibility(
    request: dict,
    token: str = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Compatibility endpoint - returns default scores with signing"""
    user = _require_user(await _get_current_user(token, authorization))

    session_id = request.get("session_id")

    # Ensure chain exists
    if session_id and session_id not in EVENT_CHAINS:
        EVENT_CHAINS.set(session_id, EventChain(session_id))

    # Add events to chain if provided
    if session_id and "events" in request:
        chain = EVENT_CHAINS.get(session_id)
        for event in request.get("events", []):
            chain.add_event({
                "type": event.get("t", "unknown"),
                "timestamp": event.get("ts", time.time()),
                "data": event
            })

    # Session ownership check — prevents cross-user session manipulation
    if session_id:
        _sess = await _get_session(session_id)
        if _sess:
            _owner = _sess.get("user_id") or _sess.get("email")
            if _owner and _owner != user.get("user_id", "") and _owner != user.get("email", ""):
                return {"status": "rejected", "reason": "session_owner_mismatch"}

    # --- Loophole #6 Fix: Check device fingerprint on ingest ---
    incoming_fp = request.get("device_fingerprint")
    if session_id and incoming_fp:
        session = await _get_session(session_id)
        if session:
            stored_fp = session.get("device_fingerprint")
            if stored_fp and stored_fp != incoming_fp:
                # Device changed - flag it
                await integrity_sessions_collection.update_one(
                    {"session_id": session_id},
                    {"$set": {"device_changed": True}}
                )
            elif not stored_fp:
                # First time seeing a fingerprint for this session, store it
                await integrity_sessions_collection.update_one(
                    {"session_id": session_id},
                    {"$set": {"device_fingerprint": incoming_fp}}
                )
    
    # Increment event_chain_count for Loophole #3 ingest count tracking
    if session_id:
        update_ops = {"$inc": {"event_chain_count": 1}}

        # Persist client-side DB snapshot for cross-browser restore
        client_state = request.get("client_state")
        if client_state and isinstance(client_state, dict):
            import json as _json

            # Only allow the expected top-level keys to prevent arbitrary data injection
            _ALLOWED_KEYS = {"TYPED_DB", "EXTERNAL_DB", "INTERNAL_DB", "TIMELINE_DB", "ts"}
            client_state = {k: v for k, v in client_state.items() if k in _ALLOWED_KEYS}

            try:
                state_size = len(_json.dumps(client_state, default=str))
            except Exception:
                state_size = 999_999
            if state_size <= 512_000:  # 512KB limit
                update_ops["$set"] = {
                    "client_state": client_state,
                    "client_state_ts": client_state.get("ts") if isinstance(client_state, dict) else None,
                    "updated_at": datetime.now(timezone.utc)
                }

        await integrity_sessions_collection.update_one(
            {"session_id": session_id},
            update_ops
        )

    response = {
        "status": "ingested",
        "flags": [],
        "ext_spans": []
    }

    if session_id:
        chain = EVENT_CHAINS.get(session_id)
        if chain:
            response["chain_head"] = chain.get_head_hash()
            response["chain_valid"] = chain.verify()[0]

    return create_signed_response(response)


@router.post("/export/check")
async def check_export_permission(
    request: dict,
    token: str = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Check if export is allowed based on current trust score"""
    user = _require_user(await _get_current_user(token, authorization))
    
    session_id = request.get("session_id")
    min_trust = request.get("min_trust", 60)
    
    if not session_id:
        return {"ok": False, "trust": 0, "reason": "No integrity session — cannot verify trust"}
    
    session = await _get_session(session_id)
    if not session:
        return {"ok": False, "trust": 0, "reason": "No server-side session data found"}
    
    analysis_history = session.get("analysis_history", [])
    if analysis_history:
        last = analysis_history[-1]
        trust = last.get("trust_score", 0)
    else:
        return {"ok": False, "trust": 0, "reason": "No analysis has been run yet"}
    
    ok = trust >= min_trust
    reason = f"Trust score {trust}% {'meets' if ok else 'below'} minimum {min_trust}%"
    
    return {"ok": ok, "trust": trust, "reason": reason}


@router.post("/verify")
async def verify_signature(request: dict):
    """Verify a signed payload (public -- no auth needed for verification)"""
    payload = {k: v for k, v in request.items() if k != "signature"}
    signature = request.get("signature")

    if not signature:
        return {"verified": False, "error": "No signature provided"}

    is_valid = verify(payload, signature)

    return {
        "verified": is_valid,
        "message": "Signature valid" if is_valid else "Signature invalid - possible tampering"
    }


@router.get("/chain/{session_id}")
async def get_chain_status(
    session_id: str,
    token: str = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Get chain status for a session"""
    user = _require_user(await _get_current_user(token, authorization))

    session = await _get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session chain not found")

    if session.get("user_id") != user["user_id"] and user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Not your session")

    # Rebuild chain from stored events if needed
    if session_id not in EVENT_CHAINS:
        chain = EventChain(session_id)
        for evt in session.get("event_chain_events", []):
            chain.events.append(evt)
        EVENT_CHAINS.set(session_id, chain)

    chain = EVENT_CHAINS.get(session_id)
    summary = chain.get_chain_summary()
    recent_hashes = chain.get_recent_hashes(10)

    return {
        **summary,
        "recent_hashes": recent_hashes
    }
