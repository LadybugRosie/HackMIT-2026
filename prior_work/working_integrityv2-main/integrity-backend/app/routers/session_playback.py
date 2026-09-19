"""
Session Playback Router — Store and retrieve session recordings for review.

Two recording layers:
  • Snapshots (v1): periodic whole-document states — coarse fallback + forensics.
  • Events (v2):   discrete edit events {t, p, d, i, k} — true char-by-char
                   fidelity with per-author attribution. Stored as append-only
                   CHUNK documents (one per sync batch) so no single Mongo doc
                   ever grows unbounded and long sessions are never truncated.

Endpoints:
  POST /api/session-playback/{submission_id}            — snapshot upload at submit (links event chunks)
  GET  /api/session-playback/{submission_id}            — snapshots for playback
  GET  /api/session-playback/{submission_id}/events     — merged multi-author event stream
  GET  /api/session-playback/{submission_id}/exists     — playback data existence check
  POST /api/session-playback/assignment/{id}/sync       — periodic snapshot sync while editing
  POST /api/session-playback/assignment/{id}/events/sync — periodic event sync while editing
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/session-playback", tags=["session-playback"])

# MongoDB collections — set by main.py on startup
snapshots_collection = None
submissions_collection = None
assignments_collection = None
classes_collection = None
events_collection = None   # session_events — chunked edit-event stream
users_collection = None    # for author display names in playback

# Limits
MAX_SNAPSHOTS = 5000
MAX_PLAINTEXT_LEN = 100_000   # 100KB per snapshot plaintext
MAX_CONTENT_LEN = 500_000     # 500KB per snapshot HTML content
MAX_PAYLOAD_SNAPSHOTS_SIZE = 10_000_000  # ~10MB total payload cap
MAX_EVENTS_PER_BATCH = 5000
MAX_EVENTS_TOTAL = 200_000    # per (student, assignment) — hours of typing
MAX_EVENT_TEXT = 150_000      # inserted-text cap (checkpoints carry full text)


def set_collections(snapshots, submissions, assignments, classes, events=None, users=None):
    """Set MongoDB collection references (called from main.py)."""
    global snapshots_collection, submissions_collection, assignments_collection, classes_collection
    global events_collection, users_collection
    snapshots_collection = snapshots
    submissions_collection = submissions
    assignments_collection = assignments
    classes_collection = classes
    events_collection = events
    users_collection = users


async def _get_user_from_token(token: str):
    """Get user from session token."""
    from .auth import get_current_user
    return await get_current_user(token)


def _extract_token(authorization: Optional[str] = Header(None)) -> str:
    """Extract token from Authorization header."""
    if authorization and authorization.startswith('Bearer '):
        return authorization[7:]
    if authorization:
        return authorization
    raise HTTPException(status_code=401, detail="Authentication required")


async def _verify_teacher_of_submission(user_id: str, submission_id: str):
    """Verify the user is the teacher who owns the class this submission belongs to."""
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    assignment = await assignments_collection.find_one(
        {"assignment_id": submission.get("assignment_id")}
    )
    if not assignment:
        raise HTTPException(status_code=403, detail="Assignment not found")
    class_doc = await classes_collection.find_one(
        {"class_id": assignment.get("class_id")}
    )
    if not class_doc or class_doc.get("teacher_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return submission


def _author_ids_of(submission: dict) -> list:
    """Owner + every collab co-author of a submission."""
    ids = {submission.get("student_id")}
    for a in submission.get("report_authors") or []:
        if a.get("user_id"):
            ids.add(a["user_id"])
    return [i for i in ids if i]


async def _verify_playback_access(user: dict, submission_id: str) -> dict:
    """
    Who may watch a session playback: the class teacher / lab PI, the
    submission owner, and — for collaborative reports — every co-author.
    Returns the submission document.
    """
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    user_id = user.get("user_id")
    role = user.get("role", "student")

    if role == "teacher":
        await _verify_teacher_of_submission(user_id, submission_id)
        return submission
    if role in ("student", "researcher"):
        if user_id in _author_ids_of(submission):
            return submission
        # Lab PIs (class owners) may view their members' playback
        await _verify_teacher_of_submission(user_id, submission_id)
        return submission
    raise HTTPException(status_code=403, detail="Not authorized")


def _safe_int(val, default=0, lo=0, hi=10_000_000):
    """Convert to int with range clamping. Handles inf/nan safely."""
    try:
        n = int(val)
        return max(lo, min(hi, n))
    except (ValueError, OverflowError, TypeError):
        return default


def _sanitize_snapshot(snap: dict) -> dict:
    """Whitelist and cap snapshot fields to prevent injection/bloat."""
    sanitized = {}
    # Whitelist allowed fields with type checks and size caps
    if isinstance(snap.get("timestamp"), (int, float)):
        sanitized["timestamp"] = snap["timestamp"]
    if isinstance(snap.get("plaintext"), str):
        sanitized["plaintext"] = snap["plaintext"][:MAX_PLAINTEXT_LEN]
    if isinstance(snap.get("content"), str):
        sanitized["content"] = snap["content"][:MAX_CONTENT_LEN]
    if isinstance(snap.get("wordCount"), (int, float)):
        sanitized["wordCount"] = _safe_int(snap["wordCount"])
    if isinstance(snap.get("cursorPos"), (int, float)):
        sanitized["cursorPos"] = _safe_int(snap["cursorPos"])
    if isinstance(snap.get("typedCount"), (int, float)):
        sanitized["typedCount"] = _safe_int(snap["typedCount"])
    if isinstance(snap.get("pasteCount"), (int, float)):
        sanitized["pasteCount"] = _safe_int(snap["pasteCount"])
    if isinstance(snap.get("timelineSegments"), list):
        # Cap segments and sanitize each
        segs = []
        for s in snap["timelineSegments"][:200]:
            if isinstance(s, dict):
                seg = {}
                if isinstance(s.get("text"), str):
                    seg["text"] = s["text"][:10000]
                if isinstance(s.get("timestamp"), (int, float)):
                    seg["timestamp"] = s["timestamp"]
                if isinstance(s.get("duration"), (int, float)):
                    seg["duration"] = s["duration"]
                if isinstance(s.get("wpm"), (int, float)):
                    seg["wpm"] = s["wpm"]
                if isinstance(s.get("type"), str) and s["type"] in ("typed", "paste", "paste_internal"):
                    seg["type"] = s["type"]
                segs.append(seg)
        sanitized["timelineSegments"] = segs
    if snap.get("_full") is True:
        sanitized["_full"] = True
    return sanitized


def _sanitize_event(ev: dict) -> Optional[dict]:
    """
    Whitelist one edit event: { t, p, d, i, k, seq }.
    Returns None when the event is structurally unusable (no finite time).
    """
    if not isinstance(ev, dict):
        return None
    t = ev.get("t")
    if not isinstance(t, (int, float)) or isinstance(t, bool):
        return None
    out = {
        "t": t,
        "p": _safe_int(ev.get("p"), default=0),
        "d": _safe_int(ev.get("d"), default=0, hi=1_000_000),
        "i": ev.get("i")[:MAX_EVENT_TEXT] if isinstance(ev.get("i"), str) else "",
        "k": ev.get("k") if ev.get("k") in ("type", "paste", "ckpt") else "type",
        "seq": _safe_int(ev.get("seq"), default=0, hi=100_000_000),
    }
    return out


async def _fetch_merged_events(submission: dict, limit: int = MAX_EVENTS_TOTAL):
    """
    Merge the event chunks of EVERY author of a submission (collab-aware)
    into one chronological stream, stamping each event with its author id.
    Returns (events, authors_map) — authors_map: {user_id: display_name}.
    """
    if events_collection is None:
        return [], {}

    submission_id = submission.get("submission_id")
    assignment_id = submission.get("assignment_id")
    author_ids = _author_ids_of(submission)

    ors = [{"submission_id": submission_id}]
    if assignment_id and author_ids:
        # Collab sessions are keyed off the topic: pick up every co-author's
        # chunks for this assignment whether or not they submitted yet.
        ors.append({"assignment_id": assignment_id, "student_id": {"$in": author_ids}})

    chunks = await events_collection.find(
        {"$or": ors}, {"_id": 0}
    ).sort([("first_t", 1), ("chunk_seq", 1)]).to_list(length=2000)

    merged = []
    names = {}
    for chunk in chunks:
        uid = chunk.get("student_id")
        if chunk.get("author_name") and uid:
            names[uid] = chunk["author_name"]
        for ev in chunk.get("events", []):
            merged.append({**ev, "a": uid})

    merged.sort(key=lambda e: (e.get("t", 0), e.get("seq", 0)))
    if len(merged) > limit:
        merged = merged[:limit]

    # Fill author names from the users collection when chunks predate names
    if users_collection is not None:
        for uid in author_ids:
            if uid and uid not in names:
                u = await users_collection.find_one({"user_id": uid})
                if u and u.get("name"):
                    names[uid] = u["name"]

    return merged, names


@router.post("/{submission_id}")
async def store_snapshots(
    submission_id: str,
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None)
):
    """
    Store session playback snapshots for a submission.
    Called by the frontend after successful submission.
    Only the student who owns the submission can upload.
    Rejects upload if submission is already graded (anti-fabrication).
    """
    token = _extract_token(authorization)
    user = await _get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Verify submission exists and belongs to this student
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.get("student_id") != user.get("user_id"):
        raise HTTPException(status_code=403, detail="Not your submission")

    # Reject upload if already graded — prevents post-grading fabrication
    if submission.get("status") in ("graded", "returned"):
        raise HTTPException(status_code=409, detail="Cannot upload playback data for graded submissions")

    raw_snapshots = body.get("snapshots", [])
    if not raw_snapshots or not isinstance(raw_snapshots, list):
        raise HTTPException(status_code=400, detail="No snapshots provided")

    # Enforce total payload size limit
    import json as _json
    try:
        payload_size = len(_json.dumps(raw_snapshots, default=str))
        if payload_size > MAX_PAYLOAD_SNAPSHOTS_SIZE:
            raise HTTPException(status_code=413, detail=f"Payload too large ({payload_size} bytes)")
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid snapshot data")

    # Cap count
    if len(raw_snapshots) > MAX_SNAPSHOTS:
        raw_snapshots = raw_snapshots[:MAX_SNAPSHOTS]

    # Sanitize each snapshot (whitelist fields, cap sizes)
    final_batch = [_sanitize_snapshot(s) for s in raw_snapshots if isinstance(s, dict)]

    # Merge with previously synced assignment-keyed snapshots
    assignment_id = submission.get("assignment_id")
    student_id = user["user_id"]
    all_snapshots = []

    if assignment_id:
        existing_doc = await snapshots_collection.find_one(
            {"student_id": student_id, "assignment_id": assignment_id, "submission_id": {"$exists": False}}
        )
        if existing_doc:
            all_snapshots = existing_doc.get("snapshots", [])

    # Merge with any previously uploaded submission-keyed snapshots so a
    # re-upload (e.g. resubmission) never silently discards the first session
    existing_sub_doc = await snapshots_collection.find_one({"submission_id": submission_id})
    if existing_sub_doc:
        all_snapshots = existing_sub_doc.get("snapshots", []) + all_snapshots

    all_snapshots.extend(final_batch)

    # Dedupe by timestamp (sync + submit paths can overlap)
    seen_ts = set()
    deduped = []
    for s in all_snapshots:
        ts = s.get("timestamp")
        if ts in seen_ts:
            continue
        seen_ts.add(ts)
        deduped.append(s)
    all_snapshots = deduped

    # Cap total — sort chronologically and keep the NEWEST snapshots so the
    # final submission state is never lost (previously kept the oldest slice)
    if len(all_snapshots) > MAX_SNAPSHOTS:
        all_snapshots.sort(key=lambda s: s.get("timestamp", 0))
        all_snapshots = all_snapshots[-MAX_SNAPSHOTS:]

    if not all_snapshots:
        return {"status": "ok", "snapshot_count": 0}

    doc = {
        "submission_id": submission_id,
        "student_id": student_id,
        "assignment_id": assignment_id,
        "version": int(body.get("version", 1)) if isinstance(body.get("version"), (int, float)) else 1,
        "snapshots": all_snapshots,
        "snapshot_count": len(all_snapshots),
        "total_duration_ms": int(body.get("totalDurationMs", 0)) if isinstance(body.get("totalDurationMs"), (int, float)) else 0,
        "created_at": datetime.now(timezone.utc),
    }

    # Upsert submission-keyed doc
    await snapshots_collection.update_one(
        {"submission_id": submission_id},
        {"$set": doc},
        upsert=True
    )

    # Clean up the assignment-keyed doc (data now lives under submission_id)
    if assignment_id:
        await snapshots_collection.delete_one(
            {"student_id": student_id, "assignment_id": assignment_id, "submission_id": {"$exists": False}}
        )

    # Link this student's synced event chunks to the submission so event
    # playback works even if the assignment/topic is later archived.
    if events_collection is not None and assignment_id:
        try:
            await events_collection.update_many(
                {"student_id": student_id, "assignment_id": assignment_id,
                 "submission_id": {"$exists": False}},
                {"$set": {"submission_id": submission_id}},
            )
        except Exception as e:
            logger.warning(f"Event chunk linking failed for {submission_id}: {e}")

    logger.info(f"Stored {len(all_snapshots)} snapshots for submission {submission_id} (merged from sync)")
    return {"status": "ok", "snapshot_count": len(all_snapshots)}


@router.post("/assignment/{assignment_id}/sync")
async def sync_assignment_snapshots(
    assignment_id: str,
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None)
):
    """
    Periodically sync snapshots during editing (before submission exists).
    Keyed by (student_id, assignment_id). Appends new snapshots to existing doc.
    Called by SessionRecorder every 30 seconds.
    """
    token = _extract_token(authorization)
    user = await _get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    raw_snapshots = body.get("snapshots", [])
    if not raw_snapshots or not isinstance(raw_snapshots, list):
        return {"status": "ok", "snapshot_count": 0}

    # Sanitize
    snapshots = [_sanitize_snapshot(s) for s in raw_snapshots[:500] if isinstance(s, dict)]
    if not snapshots:
        return {"status": "ok", "snapshot_count": 0}

    student_id = user["user_id"]
    query = {"student_id": student_id, "assignment_id": assignment_id, "submission_id": {"$exists": False}}

    # Check existing count to enforce cap
    existing = await snapshots_collection.find_one(query, {"snapshot_count": 1})
    existing_count = existing.get("snapshot_count", 0) if existing else 0

    # Cap total snapshots
    allowed = MAX_SNAPSHOTS - existing_count
    if allowed <= 0:
        return {"status": "ok", "snapshot_count": existing_count, "capped": True}
    snapshots = snapshots[:allowed]

    if existing:
        # Append to existing doc
        await snapshots_collection.update_one(
            query,
            {
                "$push": {"snapshots": {"$each": snapshots}},
                "$inc": {"snapshot_count": len(snapshots)},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            }
        )
    else:
        # Create new doc
        await snapshots_collection.insert_one({
            "student_id": student_id,
            "assignment_id": assignment_id,
            "version": 1,
            "snapshots": snapshots,
            "snapshot_count": len(snapshots),
            "total_duration_ms": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })

    new_count = existing_count + len(snapshots)
    logger.info(f"Synced {len(snapshots)} snapshots for assignment {assignment_id} (total: {new_count})")
    return {"status": "ok", "snapshot_count": new_count}


@router.post("/assignment/{assignment_id}/events/sync")
async def sync_assignment_events(
    assignment_id: str,
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None)
):
    """
    Periodically sync discrete edit events during editing.
    Each batch becomes ONE append-only chunk document keyed by
    (student_id, assignment_id, chunk_seq) — no doc-growth limit issues,
    no silent truncation of long sessions.
    """
    token = _extract_token(authorization)
    user = await _get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    if events_collection is None:
        raise HTTPException(status_code=503, detail="Event storage unavailable")

    raw_events = body.get("events", [])
    if not raw_events or not isinstance(raw_events, list):
        return {"status": "ok", "event_count": 0}

    events = [e for e in (_sanitize_event(ev) for ev in raw_events[:MAX_EVENTS_PER_BATCH]) if e]
    if not events:
        return {"status": "ok", "event_count": 0}

    student_id = user["user_id"]
    scope = {"student_id": student_id, "assignment_id": assignment_id}

    # Enforce the total-events cap across this student's chunks
    pipeline = [
        {"$match": scope},
        {"$group": {"_id": None, "total": {"$sum": "$event_count"}, "max_seq": {"$max": "$chunk_seq"}}},
    ]
    agg = await events_collection.aggregate(pipeline).to_list(length=1)
    existing_total = agg[0]["total"] if agg else 0
    next_seq = (agg[0]["max_seq"] if agg else 0) or 0

    allowed = MAX_EVENTS_TOTAL - existing_total
    if allowed <= 0:
        return {"status": "ok", "event_count": existing_total, "capped": True}
    events = events[:allowed]

    await events_collection.insert_one({
        "student_id": student_id,
        "author_name": user.get("name") or "Unknown",
        "assignment_id": assignment_id,
        "chunk_seq": next_seq + 1,
        "events": events,
        "event_count": len(events),
        "first_t": events[0].get("t"),
        "last_t": events[-1].get("t"),
        "created_at": datetime.now(timezone.utc),
    })

    return {"status": "ok", "event_count": existing_total + len(events)}


@router.get("/assignment/{assignment_id}")
async def get_assignment_snapshots(
    assignment_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get snapshots for an assignment (during editing, before submission).
    Used by SessionRecorder to restore from server on new browser.
    """
    token = _extract_token(authorization)
    user = await _get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    doc = await snapshots_collection.find_one(
        {"student_id": user["user_id"], "assignment_id": assignment_id, "submission_id": {"$exists": False}},
        {"_id": 0}
    )
    if not doc:
        return {"found": False, "snapshots": [], "snapshot_count": 0}
    return {"found": True, "snapshots": doc.get("snapshots", []), "snapshot_count": doc.get("snapshot_count", 0)}


@router.get("/{submission_id}")
async def get_snapshots(
    submission_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Retrieve session playback snapshots for a submission.
    Teachers can view snapshots for submissions in their classes.
    Students can view their own snapshots.
    """
    token = _extract_token(authorization)
    user = await _get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Owner, collab co-authors, class teacher and lab PI may watch.
    submission = await _verify_playback_access(user, submission_id)

    doc = await snapshots_collection.find_one(
        {"submission_id": submission_id},
        {"_id": 0}
    )

    # Fallback: for submissions created before the frontend uploaded snapshots
    # under submission_id, look up by (student_id, assignment_id) instead.
    if not doc:
        assignment_id = submission.get("assignment_id")
        student_id = submission.get("student_id")
        if assignment_id and student_id:
            doc = await snapshots_collection.find_one(
                {"student_id": student_id, "assignment_id": assignment_id, "submission_id": {"$exists": False}},
                {"_id": 0}
            )

    if not doc:
        raise HTTPException(status_code=404, detail="No playback data found for this submission")

    return doc


@router.get("/{submission_id}/events")
async def get_events(
    submission_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Retrieve the merged edit-event stream for a submission — every author's
    events (collab-aware), chronologically ordered, each stamped with its
    author id, plus a {user_id: display_name} map for the viewer.
    """
    token = _extract_token(authorization)
    user = await _get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    submission = await _verify_playback_access(user, submission_id)
    events, authors = await _fetch_merged_events(submission)

    return {
        "found": len(events) > 0,
        "event_count": len(events),
        "events": events,
        "authors": authors,
    }


@router.get("/{submission_id}/exists")
async def check_playback_exists(
    submission_id: str,
    authorization: Optional[str] = Header(None)
):
    """Check if playback data exists for a submission. Same auth as get_snapshots."""
    token = _extract_token(authorization)
    user = await _get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    submission = await _verify_playback_access(user, submission_id)

    doc = await snapshots_collection.find_one(
        {"submission_id": submission_id},
        {"snapshot_count": 1}
    )
    # Same fallback as GET — pre-submission synced data counts as existing,
    # so "View replay" buttons never hide data the GET would actually return.
    if not doc:
        assignment_id = submission.get("assignment_id")
        student_id = submission.get("student_id")
        if assignment_id and student_id:
            doc = await snapshots_collection.find_one(
                {"student_id": student_id, "assignment_id": assignment_id, "submission_id": {"$exists": False}},
                {"snapshot_count": 1}
            )

    has_events = False
    if events_collection is not None:
        ors = [{"submission_id": submission_id}]
        if submission.get("assignment_id"):
            ors.append({
                "assignment_id": submission["assignment_id"],
                "student_id": {"$in": _author_ids_of(submission)},
            })
        has_events = await events_collection.find_one({"$or": ors}, {"_id": 1}) is not None

    return {
        "exists": doc is not None or has_events,
        "snapshot_count": doc.get("snapshot_count", 0) if doc else 0,
        "has_events": has_events,
    }


@router.get("/{submission_id}/forensics")
async def get_forensics(
    submission_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Compute draft evolution forensics for a submission.
    Returns 9 signals across 3 tiers for teacher review.
    Caches result to avoid recomputation on repeat views.
    """
    token = _extract_token(authorization)
    user = await _get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    await _verify_playback_access(user, submission_id)

    # Load snapshot doc (same fallback as get_snapshots)
    doc = await snapshots_collection.find_one(
        {"submission_id": submission_id}, {"_id": 0}
    )
    if not doc:
        submission = await submissions_collection.find_one({"submission_id": submission_id})
        if submission:
            aid = submission.get("assignment_id")
            sid = submission.get("student_id")
            if aid and sid:
                doc = await snapshots_collection.find_one(
                    {"student_id": sid, "assignment_id": aid, "submission_id": {"$exists": False}},
                    {"_id": 0}
                )
    if not doc:
        raise HTTPException(status_code=404, detail="No playback data found for this submission")

    # Check cache — invalidate if algorithm version changed
    from ..services.draft_forensics import FORENSICS_VERSION
    cached = doc.get("forensics_cache")
    if cached and cached.get("forensics_version") == FORENSICS_VERSION:
        return cached

    # Reconstruct plaintext for delta-compressed snapshots.
    # Work on copies — never mutate the loaded document's snapshot dicts,
    # otherwise cached/forensic state can drift from stored data.
    raw_snaps = []
    prev = ""
    for s in doc.get("snapshots", []):
        snap = dict(s)
        if snap.get("plaintext") is not None:
            prev = snap["plaintext"]
        else:
            snap["plaintext"] = prev
        raw_snaps.append(snap)

    # Get student_id from doc or submission
    student_id = doc.get("student_id")
    if not student_id:
        submission = await submissions_collection.find_one({"submission_id": submission_id})
        student_id = submission.get("student_id") if submission else None
    if not student_id:
        raise HTTPException(status_code=500, detail="Could not determine student")

    # Compute forensics
    from ..services.draft_forensics import compute_forensics
    result = await compute_forensics(
        snapshots=raw_snaps,
        student_id=student_id,
        submission_id=submission_id,
        snapshots_collection=snapshots_collection,
        submissions_collection=submissions_collection,
    )

    # Attach student context and teacher override if they exist
    student_context = doc.get("student_context")
    teacher_override = doc.get("teacher_override")
    if student_context:
        result["student_context"] = student_context
    if teacher_override:
        result["teacher_override"] = teacher_override

    # Cache result
    try:
        await snapshots_collection.update_one(
            {"submission_id": submission_id},
            {"$set": {"forensics_cache": result}}
        )
    except Exception:
        pass  # Non-critical — cache miss just means recomputation

    return result


@router.post("/{submission_id}/forensics/student-context")
async def submit_student_context(
    submission_id: str,
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None)
):
    """
    Student provides context for flagged forensic signals.
    e.g., "I used Grammarly", "New topic for me", "I pasted my own outline".
    Stored alongside the forensics data for teacher review.
    """
    token = _extract_token(authorization)
    user = await _get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Only the student who owns the submission can provide context
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission or submission.get("student_id") != user.get("user_id"):
        raise HTTPException(status_code=403, detail="Not your submission")

    context_text = str(body.get("context", ""))[:2000]  # Cap at 2000 chars
    if not context_text.strip():
        raise HTTPException(status_code=400, detail="Context cannot be empty")

    context_entry = {
        "text": context_text.strip(),
        "submitted_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "student_id": user["user_id"],
    }

    await snapshots_collection.update_one(
        {"submission_id": submission_id},
        {"$set": {"student_context": context_entry, "forensics_cache": None}},
        upsert=False
    )

    return {"status": "ok", "message": "Context saved — your teacher will see this alongside the analysis."}


@router.post("/{submission_id}/forensics/teacher-override")
async def submit_teacher_override(
    submission_id: str,
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None)
):
    """
    Teacher reviews forensics and records their assessment.
    Overrides the automated verdict with the teacher's judgment.
    """
    token = _extract_token(authorization)
    user = await _get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    if user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Teachers only")
    await _verify_teacher_of_submission(user["user_id"], submission_id)

    verdict = str(body.get("verdict", ""))
    if verdict not in ("cleared", "flagged", "review"):
        raise HTTPException(status_code=400, detail="Verdict must be 'cleared', 'flagged', or 'review'")

    notes = str(body.get("notes", ""))[:2000]

    override = {
        "verdict": verdict,
        "notes": notes.strip(),
        "teacher_id": user["user_id"],
        "submitted_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }

    await snapshots_collection.update_one(
        {"submission_id": submission_id},
        {"$set": {"teacher_override": override}},
        upsert=False
    )

    return {"status": "ok", "override": override}
