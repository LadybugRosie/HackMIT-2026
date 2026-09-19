"""
Research Router — Researcher accounts: labs, topics, deliverables, sharing.

Architecture (reuses the classroom machinery):
  - A Lab IS a class document with kind="lab" (PI = teacher_id, members in class_members).
  - A Topic IS an auto-published assignment with kind="research_topic" in a lab,
    so the entire existing editor / submit / report / stylometry / playback
    pipeline works unchanged for researchers.

Endpoints (auth, researcher-focused):
  GET    /api/research/labs                       — labs the researcher belongs to
  POST   /api/research/labs                       — create a lab (researcher becomes PI)
  POST   /api/research/labs/join                  — join a lab by code
  GET    /api/research/labs/{lab_id}/members      — PI oversight: members + submissions
  GET    /api/research/topics                     — researcher's topics with status
  POST   /api/research/topics                     — create topic (synthetic assignment + draft)
  POST   /api/research/submissions/{id}/generate-pdf  — WeasyPrint PDF of the document
  GET    /api/research/submissions/{id}/pdf       — download stored PDF
  POST   /api/research/submissions/{id}/video     — upload replay WebM → ffmpeg → MP4
  GET    /api/research/submissions/{id}/video     — stream stored MP4
  POST   /api/research/submissions/{id}/share     — create public share link
  DELETE /api/research/submissions/{id}/share     — revoke share links
  GET    /api/research/status                     — capability check (ffmpeg/pdf)

Public (no auth — share-token gated, pattern: password_reset_tokens):
  GET /api/share/{share_token}            — share payload (meta + snapshots + report)
  GET /api/share/{share_token}/video      — stream the MP4 publicly
"""

import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Response
from pydantic import BaseModel, Field

from ..services import media
from ..services.integrity_visibility import effective_ai_probability

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])
share_router = APIRouter(prefix="/api/share", tags=["share"])

# MongoDB collections — set by main.py on startup
classes_collection = None
class_members_collection = None
assignments_collection = None
submissions_collection = None
snapshots_collection = None
users_collection = None
share_tokens_collection = None

SHARE_TOKEN_TTL_DAYS = 30
MAX_VIDEO_BYTES = 80 * 1024 * 1024
TOPIC_FAR_FUTURE_YEARS = 10  # topics have no real deadline


def set_collections(classes, members, assignments, submissions, snapshots, users, share_tokens):
    """Set MongoDB collection references (called from main.py)."""
    global classes_collection, class_members_collection, assignments_collection
    global submissions_collection, snapshots_collection, users_collection, share_tokens_collection
    classes_collection = classes
    class_members_collection = members
    assignments_collection = assignments
    submissions_collection = submissions
    snapshots_collection = snapshots
    users_collection = users
    share_tokens_collection = share_tokens


# ============================================================================
# AUTH HELPERS (same idiom as session_playback.py)
# ============================================================================

def _extract_token(authorization: Optional[str] = None) -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    if authorization:
        return authorization
    raise HTTPException(status_code=401, detail="Authentication required")


async def _get_user(authorization: Optional[str]):
    from .auth import get_current_user
    user = await get_current_user(_extract_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    # FIX #22 idiom: re-read role from DB to prevent stale-session permissions
    if users_collection is not None and user.get("user_id"):
        db_user = await users_collection.find_one({"user_id": user["user_id"]})
        if db_user:
            user["role"] = db_user.get("role", user.get("role", "student"))
    return user


async def verify_researcher(authorization: Optional[str]):
    user = await _get_user(authorization)
    if user.get("role") != "researcher":
        raise HTTPException(status_code=403, detail="Only researchers can perform this action")
    return user


def _author_ids(submission: dict) -> list:
    """All user_ids who may access a submission: owner + co-authors."""
    ids = {submission.get("student_id")}
    for a in submission.get("report_authors") or []:
        if a.get("user_id"):
            ids.add(a["user_id"])
    return [i for i in ids if i]


async def _ensure_report_authors(submission: dict, segments) -> dict:
    """Guarantee the submission has a report_authors list so per-author
    stylometry has somewhere to attach.

    Topics created before the multi-author model (or any submission that never
    went through invite) start with an empty report_authors. Seed it from the
    submitted segments plus the owner. Concurrency-safe: the atomic conditional
    means only the first of the parallel verify/compute calls actually seeds.
    """
    if submission.get("report_authors"):
        return submission
    owner_id = submission.get("primary_author_id") or submission.get("student_id")
    ids = []
    if owner_id:
        ids.append(owner_id)
    for s in segments or []:
        uid = getattr(s, "user_id", None)
        if uid and uid not in ids:
            ids.append(uid)
    if not ids:
        return submission
    authors = []
    for uid in ids:
        u = await users_collection.find_one({"user_id": uid}) if users_collection is not None else None
        authors.append({
            "user_id": uid,
            "name": (u or {}).get("name") or "Researcher",
            "email": (u or {}).get("email"),
            "joined_at": datetime.now(timezone.utc),
            "stylometry_v3": None,
            "contribution": None,
        })
    set_fields = {"report_authors": authors}
    if not submission.get("primary_author_id") and owner_id:
        set_fields["primary_author_id"] = owner_id
    if len(authors) > 1:
        set_fields["is_shared"] = True
    await submissions_collection.update_one(
        {"submission_id": submission["submission_id"],
         "$or": [{"report_authors": {"$exists": False}},
                 {"report_authors": None},
                 {"report_authors": []}]},
        {"$set": set_fields},
    )
    fresh = await submissions_collection.find_one({"submission_id": submission["submission_id"]})
    return fresh or submission


def _map_doc_stylometry(sub_sty: dict) -> Optional[dict]:
    """Map a whole-document stylometry_v3 onto the per-author verdict shape."""
    if not sub_sty:
        return None
    cosine = sub_sty.get("cosine_score")
    if cosine is None:
        cosine = sub_sty.get("similarity")
    return {
        "verdict": sub_sty.get("verdict"),
        "cosine_score": cosine,
        "probability": sub_sty.get("probability"),
        "profile_strength": sub_sty.get("profile_strength") or sub_sty.get("confidence"),
        "status": "success",
    }


def _extract_author_segments_from_html(html: str) -> list:
    """Parse a document's authorship marks into ordered per-author runs.

    The Authorship Tiptap mark renders each author's text as
    <span data-author-id="UID" ...>text</span>. Returns an ordered list of
    {user_id, text} runs (consecutive same-author runs merged) — this is the
    'who wrote what' data, in document order.
    """
    if not html:
        return []
    runs = []
    for m in re.finditer(r'data-author-id="([^"]+)"[^>]*>(.*?)</span>', html, re.DOTALL):
        uid = m.group(1)
        text = re.sub(r'<[^>]+>', '', m.group(2))
        text = re.sub(r'\s+', ' ', text)
        if not text.strip():
            continue
        if runs and runs[-1]["user_id"] == uid:
            runs[-1]["text"] += text
        else:
            runs.append({"user_id": uid, "text": text})
    return runs


async def _heal_authors_from_content(submission: dict) -> dict:
    """Reconstruct the full author list (and per-author stylometry) from the
    document's authorship marks, so the results page shows EVERY contributor —
    not just whoever happened to be saved in report_authors.

    Idempotent: once every marked author is present with a verdict, it no-ops.
    Single-author documents (no marks) fall back to the whole-document result.
    """
    submission = await _ensure_report_authors(submission, [])
    content = submission.get("content") or ""
    runs = _extract_author_segments_from_html(content)

    # Aggregate each author's contributed text + word count, in document order.
    seg_text, order = {}, []
    for r in runs:
        uid = r["user_id"]
        if uid not in seg_text:
            seg_text[uid] = ""
            order.append(uid)
        seg_text[uid] += r["text"]

    existing = {a.get("user_id"): a for a in (submission.get("report_authors") or [])}
    owner = submission.get("primary_author_id") or submission.get("student_id")
    author_ids = order or list(existing.keys()) or ([owner] if owner else [])
    if not author_ids:
        return submission

    # Already healed? every contributor present with a verdict.
    if (set(author_ids) <= set(existing.keys())
            and len(existing) == len(author_ids)
            and all(existing[uid].get("stylometry_v3") for uid in author_ids)):
        return submission

    lab_id = submission.get("class_id")
    total_words = sum(len(t.split()) for t in seg_text.values())
    from .chunk_analyze import _stylo_verify_chunk

    new_authors = []
    for uid in author_ids:
        u = await users_collection.find_one({"user_id": uid}) if users_collection is not None else None
        prev = existing.get(uid, {})
        text = seg_text.get(uid, "")
        words = len(text.split()) if text else (submission.get("word_count") or 0 if len(author_ids) == 1 else 0)

        sty = prev.get("stylometry_v3")
        if not sty:
            enrolled = await _is_stylometry_enrolled(uid, lab_id)
            if enrolled and len(text.strip()) >= 50:
                try:
                    r = await _stylo_verify_chunk(uid, lab_id, text, absorb=False)
                    sty = {
                        "verdict": r.get("verdict"), "cosine_score": r.get("cosine_score"),
                        "probability": r.get("probability"),
                        "profile_strength": r.get("profile_strength"), "status": r.get("status"),
                    }
                except Exception:
                    sty = None
            # Single author with no usable segment → derive from whole-document.
            if not sty and len(author_ids) == 1:
                sty = _map_doc_stylometry(submission.get("stylometry_v3"))

        denom = total_words if total_words else (words or 1)
        new_authors.append({
            "user_id": uid,
            "name": (u or {}).get("name") or prev.get("name") or "Researcher",
            "email": (u or {}).get("email") or prev.get("email"),
            "joined_at": prev.get("joined_at") or datetime.now(timezone.utc),
            "stylometry_v3": sty,
            "contribution": {
                "final_words": words,
                "final_pct": round(words / denom * 100, 1) if denom else 0,
                "keystrokes": (prev.get("contribution") or {}).get("keystrokes", 0),
                "effort_pct": (prev.get("contribution") or {}).get("effort_pct", 0),
            },
        })

    set_fields = {"report_authors": new_authors, "is_shared": len(new_authors) > 1}
    if not submission.get("primary_author_id") and owner:
        set_fields["primary_author_id"] = owner
    await submissions_collection.update_one(
        {"submission_id": submission["submission_id"]}, {"$set": set_fields}
    )
    return await submissions_collection.find_one({"submission_id": submission["submission_id"]}) or submission


async def _is_lab_pi(user_id: str, class_id: str) -> bool:
    class_doc = await classes_collection.find_one({"class_id": class_id})
    return bool(class_doc and class_doc.get("teacher_id") == user_id)


async def _is_stylometry_enrolled(user_id: str, lab_id: str) -> bool:
    """A user is enrolled iff their lab membership carries the stylometry flag."""
    m = await class_members_collection.find_one({
        "class_id": lab_id, "user_id": user_id, "stylometry_enrolled": True
    })
    return bool(m)


async def _verify_own_submission(user: dict, submission_id: str) -> dict:
    """Read/edit access: owner, any co-author, or the lab PI."""
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if user["user_id"] in _author_ids(submission):
        return submission
    if await _is_lab_pi(user["user_id"], submission.get("class_id")):
        return submission
    raise HTTPException(status_code=403, detail="Not your submission")


# ============================================================================
# MODELS
# ============================================================================

class LabCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)


class LabJoin(BaseModel):
    lab_code: str = Field(..., min_length=4, max_length=10)


class TopicCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    lab_id: Optional[str] = None  # defaults to the researcher's first lab
    collaborative: bool = False   # multi-author report (real-time collab)
    description: Optional[str] = Field(None, max_length=2000)


class ShareCreate(BaseModel):
    scope: list[str] = Field(default=["video", "playback", "report"])


# ============================================================================
# LABS
# ============================================================================

async def _lab_response(lab: dict, member_count: int) -> dict:
    return {
        "lab_id": lab["class_id"],
        "name": lab["name"],
        "description": lab.get("description"),
        "lab_code": lab["class_code"],
        "pi_id": lab["teacher_id"],
        "pi_name": lab.get("teacher_name", "Unknown"),
        "member_count": member_count,
        "created_at": lab.get("created_at"),
    }


@router.get("/labs")
async def list_labs(authorization: Optional[str] = Header(None)):
    """Labs the researcher belongs to."""
    user = await verify_researcher(authorization)
    memberships = await class_members_collection.find(
        {"user_id": user["user_id"]}
    ).to_list(length=100)
    class_ids = [m["class_id"] for m in memberships]
    if not class_ids:
        return {"labs": []}
    labs = await classes_collection.find(
        {"class_id": {"$in": class_ids}, "kind": "lab", "archived": False}
    ).to_list(length=100)
    result = []
    for lab in labs:
        count = await class_members_collection.count_documents({"class_id": lab["class_id"]})
        entry = await _lab_response(lab, count)
        entry["is_pi"] = lab["teacher_id"] == user["user_id"]
        result.append(entry)
    return {"labs": result}


@router.post("/labs")
async def create_lab(request: LabCreate, authorization: Optional[str] = Header(None)):
    """Create a lab; the creating researcher becomes its PI."""
    user = await verify_researcher(authorization)
    from .classes import generate_class_code
    lab_code = generate_class_code()
    while await classes_collection.find_one({"class_code": lab_code}):
        lab_code = generate_class_code()
    lab_doc = {
        "class_id": str(uuid.uuid4()),
        "kind": "lab",
        "name": request.name.strip(),
        "section": None,
        "subject": "Research",
        "description": request.description.strip() if request.description else None,
        "color": "#7c3aed",
        "class_code": lab_code,
        "teacher_id": user["user_id"],
        "teacher_name": user["name"],
        "settings": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "archived": False,
    }
    await classes_collection.insert_one(lab_doc)
    await class_members_collection.insert_one({
        "class_id": lab_doc["class_id"],
        "user_id": user["user_id"],
        "user_name": user["name"],
        "user_email": user.get("email"),
        "role": "researcher",
        "joined_at": datetime.now(timezone.utc),
    })
    return await _lab_response(lab_doc, 1)


@router.post("/labs/join")
async def join_lab(request: LabJoin, authorization: Optional[str] = Header(None)):
    """Join a lab by its code."""
    user = await verify_researcher(authorization)
    lab = await classes_collection.find_one({
        "class_code": request.lab_code.strip().upper(),
        "kind": "lab",
        "archived": False,
    })
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found — check the code")
    existing = await class_members_collection.find_one({
        "class_id": lab["class_id"], "user_id": user["user_id"]
    })
    if existing:
        raise HTTPException(status_code=400, detail="Already a member of this lab")
    await class_members_collection.insert_one({
        "class_id": lab["class_id"],
        "user_id": user["user_id"],
        "user_name": user["name"],
        "user_email": user.get("email"),
        "role": "researcher",
        "joined_at": datetime.now(timezone.utc),
    })
    count = await class_members_collection.count_documents({"class_id": lab["class_id"]})
    return await _lab_response(lab, count)


@router.get("/labs/{lab_id}/members")
async def lab_members(lab_id: str, authorization: Optional[str] = Header(None)):
    """PI oversight: members with their topics and submission integrity summary."""
    user = await _get_user(authorization)
    lab = await classes_collection.find_one({"class_id": lab_id, "kind": "lab"})
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    membership = await class_members_collection.find_one({
        "class_id": lab_id, "user_id": user["user_id"]
    })
    is_pi = lab["teacher_id"] == user["user_id"]
    if not membership and not is_pi:
        raise HTTPException(status_code=403, detail="Not a member of this lab")

    members = await class_members_collection.find({"class_id": lab_id}).to_list(length=200)
    member_ids = [m["user_id"] for m in members]
    submissions = await submissions_collection.find(
        {"class_id": lab_id, "student_id": {"$in": member_ids}},
        {"report_html": 0}
    ).to_list(length=500)
    subs_by_user = {}
    for s in submissions:
        subs_by_user.setdefault(s["student_id"], []).append({
            "submission_id": s["submission_id"],
            "assignment_id": s["assignment_id"],
            "status": s.get("status"),
            "trust_score": s.get("trust_score"),
            "stylometry_verdict": (s.get("stylometry_v3") or {}).get("verdict"),
            "stylometry_probability": (s.get("stylometry_v3") or {}).get("probability"),
            "ai_probability": effective_ai_probability(s.get("ai_detection")),
            "submitted_at": s.get("submitted_at"),
            "word_count": s.get("word_count"),
            "is_shared": bool(s.get("is_shared")),
            "report_authors": [
                {
                    "name": a.get("name"),
                    "verdict": (a.get("stylometry_v3") or {}).get("verdict"),
                    "final_pct": (a.get("contribution") or {}).get("final_pct"),
                }
                for a in (s.get("report_authors") or [])
            ] if s.get("is_shared") else [],
        })
    # Topic titles for context
    topic_ids = list({s["assignment_id"] for s in submissions})
    topics = await assignments_collection.find(
        {"assignment_id": {"$in": topic_ids}}, {"assignment_id": 1, "title": 1}
    ).to_list(length=500)
    titles = {t["assignment_id"]: t.get("title") for t in topics}
    for subs in subs_by_user.values():
        for s in subs:
            s["topic_title"] = titles.get(s["assignment_id"])

    return {
        "lab": await _lab_response(lab, len(members)),
        "is_pi": is_pi,
        "members": [{
            "user_id": m["user_id"],
            "name": m.get("user_name", "Unknown"),
            "email": m.get("user_email"),
            "joined_at": m.get("joined_at"),
            "stylometry_enrolled": bool(m.get("stylometry_enrolled")),
            # PI sees everyone's submissions; members only their own
            "submissions": subs_by_user.get(m["user_id"], []) if (is_pi or m["user_id"] == user["user_id"]) else [],
        } for m in members],
    }


# ============================================================================
# TOPICS
# ============================================================================

@router.post("/topics")
async def create_topic(request: TopicCreate, authorization: Optional[str] = Header(None)):
    """Create a research topic = auto-published synthetic assignment + draft submission."""
    user = await verify_researcher(authorization)

    # Resolve lab — explicit, else first lab the researcher belongs to
    lab = None
    if request.lab_id:
        lab = await classes_collection.find_one({"class_id": request.lab_id, "kind": "lab"})
        if not lab:
            raise HTTPException(status_code=404, detail="Lab not found")
        member = await class_members_collection.find_one({
            "class_id": lab["class_id"], "user_id": user["user_id"]
        })
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this lab")
    else:
        memberships = await class_members_collection.find(
            {"user_id": user["user_id"]}
        ).to_list(length=100)
        for m in memberships:
            cand = await classes_collection.find_one({
                "class_id": m["class_id"], "kind": "lab", "archived": False
            })
            if cand:
                lab = cand
                break
        if not lab:
            raise HTTPException(status_code=400, detail="No lab found — create or join a lab first")

    # Synthetic assignment (kind=research_topic): published, far-future deadline,
    # researcher-appropriate tool settings (face off, stylometry+integrity on)
    # Research reports are STYLOMETRY-ONLY: no trust score, no AI detection,
    # no plagiarism, no face check. Authorship is judged purely by the writer's
    # enrolled stylometry profile.
    from ..models import AssignmentSettings
    settings = AssignmentSettings(
        face_verification_enabled=False,
        stylometry_enabled=True,
        analyze_integrity_enabled=False,
        gptzero_enabled=False,
        check_plagiarism=False,
    ).model_dump()

    assignment_doc = {
        "assignment_id": str(uuid.uuid4()),
        "kind": "research_topic",
        "class_id": lab["class_id"],
        "teacher_id": user["user_id"],  # topic creator/owner
        "title": request.title.strip(),
        "instructions": (request.description or "").strip(),
        "due_date": datetime.now(timezone.utc) + timedelta(days=365 * TOPIC_FAR_FUTURE_YEARS),
        "points": 100,
        "settings": settings,
        "rubric": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "published": True,
        # never picked up by the batch-similarity deadline scheduler
        "batch_similarity_completed": True,
    }
    await assignments_collection.insert_one(assignment_doc)

    membership = await class_members_collection.find_one({
        "class_id": lab["class_id"], "user_id": user["user_id"]
    })

    # Draft submission so the editor has full context immediately.
    # Collaborative reports start with the creator as the sole (primary) author.
    submission_doc = {
        "submission_id": str(uuid.uuid4()),
        "assignment_id": assignment_doc["assignment_id"],
        "class_id": lab["class_id"],
        "student_id": user["user_id"],
        "content": "",
        "content_html": "",
        "word_count": 0,
        "status": "draft",
        "trust_score": 100,
        "content_mix": {"typed": 1.0, "internal": 0, "external": 0},
        "integrity_flags": [],
        "face_verification_log": [],
        "plagiarism_score": 0,
        "plagiarism_matches": [],
        # Multi-author collaboration fields (single-author reports keep is_shared=False)
        "is_shared": bool(request.collaborative),
        "primary_author_id": user["user_id"],
        "report_authors": [{
            "user_id": user["user_id"],
            "name": user["name"],
            "email": user.get("email"),
            "joined_at": datetime.now(timezone.utc),
            "stylometry_v3": None,
            "contribution": None,
        }],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await submissions_collection.insert_one(submission_doc)

    return {
        "success": True,
        "topic_id": assignment_doc["assignment_id"],
        "lab_id": lab["class_id"],
        "submission_id": submission_doc["submission_id"],
        "title": assignment_doc["title"],
        "collaborative": bool(request.collaborative),
        "stylometry_enrolled": bool(membership and membership.get("stylometry_enrolled")),
    }


@router.get("/topics")
async def list_topics(authorization: Optional[str] = Header(None)):
    """Researcher's topics (created OR co-authored) with status + deliverables."""
    user = await verify_researcher(authorization)
    uid = user["user_id"]

    # Topics the user created + topics where they're a co-author on a shared report
    coauthored = await submissions_collection.find(
        {"report_authors.user_id": uid}, {"assignment_id": 1}
    ).to_list(length=200)
    coauthored_ids = [s["assignment_id"] for s in coauthored]

    topics = await assignments_collection.find({
        "kind": "research_topic",
        "$or": [{"teacher_id": uid}, {"assignment_id": {"$in": coauthored_ids}}],
    }).sort("created_at", -1).to_list(length=200)

    topic_ids = [t["assignment_id"] for t in topics]
    submissions = await submissions_collection.find(
        {"assignment_id": {"$in": topic_ids}},
        {"report_html": 0}
    ).to_list(length=400)
    # index by assignment_id (one shared submission per topic)
    subs = {s["assignment_id"]: s for s in submissions}

    lab_ids = list({t["class_id"] for t in topics})
    labs = await classes_collection.find({"class_id": {"$in": lab_ids}}).to_list(length=100)
    lab_names = {l["class_id"]: l.get("name", "Lab") for l in labs}

    result = []
    for t in topics:
        s = subs.get(t["assignment_id"])
        result.append({
            "topic_id": t["assignment_id"],
            "title": t.get("title"),
            "lab_id": t["class_id"],
            "lab_name": lab_names.get(t["class_id"], "Lab"),
            "created_at": t.get("created_at"),
            "submission_id": s.get("submission_id") if s else None,
            "status": s.get("status", "draft") if s else "draft",
            "word_count": s.get("word_count", 0) if s else 0,
            "trust_score": s.get("trust_score") if s else None,
            "stylometry_verdict": ((s.get("stylometry_v3") or {}).get("verdict")) if s else None,
            "stylometry_probability": ((s.get("stylometry_v3") or {}).get("probability")) if s else None,
            "ai_probability": effective_ai_probability(s.get("ai_detection")) if s else None,
            "submitted_at": s.get("submitted_at") if s else None,
            "has_video": bool(s and s.get("video_ref")),
            "has_pdf": bool(s and s.get("pdf_ref")),
            "is_shared": bool(s and s.get("is_shared")),
            "author_count": len(s.get("report_authors") or []) if s else 0,
            "is_owner": t.get("teacher_id") == uid,
        })
    return {"topics": result}


# ============================================================================
# COLLABORATION — real-time co-authoring + per-author stylometry
# ============================================================================

class InviteAuthor(BaseModel):
    user_id: str


class AuthorSegment(BaseModel):
    user_id: str
    text: str = ""


class AuthorSegments(BaseModel):
    segments: list[AuthorSegment] = []


@router.get("/collab-access/{assignment_id}")
async def collab_access(assignment_id: str, authorization: Optional[str] = Header(None)):
    """
    Called by the Hocuspocus collab server to authorize a join.
    Allow if the caller is a report author (or the lab PI) of this topic AND
    is stylometry-enrolled in the lab (enrollment is required to co-author).
    Returns {allowed, user:{user_id, name, uid}} — uid is used as the
    authorship mark id, matching the stylometry student_id.
    """
    user = await _get_user(authorization)
    assignment = await assignments_collection.find_one({"assignment_id": assignment_id})
    if not assignment or assignment.get("kind") != "research_topic":
        raise HTTPException(status_code=404, detail="Research topic not found")

    lab_id = assignment["class_id"]
    submission = await submissions_collection.find_one({"assignment_id": assignment_id})

    is_author = bool(submission and user["user_id"] in _author_ids(submission))
    is_pi = await _is_lab_pi(user["user_id"], lab_id)
    if not (is_author or is_pi):
        raise HTTPException(status_code=403, detail="Not a co-author of this report")

    # PI may observe without being enrolled; co-authors must be enrolled.
    if is_author and not is_pi and not await _is_stylometry_enrolled(user["user_id"], lab_id):
        raise HTTPException(status_code=403, detail="Stylometry enrollment required to co-author")

    return {
        "allowed": True,
        "user": {
            "user_id": user["user_id"],
            "name": user.get("name", "Researcher"),
            "uid": user["user_id"],
        },
    }


@router.get("/submissions/{submission_id}/authors")
async def list_report_authors(submission_id: str, authorization: Optional[str] = Header(None)):
    """List a report's authors with enrollment + contribution + per-author verdict."""
    user = await _get_user(authorization)
    submission = await _verify_own_submission(user, submission_id)
    submission = await _heal_authors_from_content(submission)
    lab_id = submission.get("class_id")
    authors = []
    for a in submission.get("report_authors") or []:
        authors.append({
            **{k: a.get(k) for k in ("user_id", "name", "email", "stylometry_v3", "contribution")},
            "is_primary": a.get("user_id") == submission.get("primary_author_id"),
            "stylometry_enrolled": await _is_stylometry_enrolled(a.get("user_id"), lab_id),
        })
    # 'Who wrote what' — ordered authorship runs from the document marks.
    segments = _extract_author_segments_from_html(submission.get("content") or "")
    return {
        "submission_id": submission_id,
        "is_shared": bool(submission.get("is_shared")),
        "primary_author_id": submission.get("primary_author_id"),
        "authors": authors,
        "segments": segments,
    }


@router.post("/submissions/{submission_id}/invite-author")
async def invite_author(submission_id: str, request: InviteAuthor, authorization: Optional[str] = Header(None)):
    """Add a lab member as a co-author. Primary author or lab PI only.
    The invitee must be a lab member AND stylometry-enrolled."""
    user = await _get_user(authorization)
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    lab_id = submission.get("class_id")

    is_primary = submission.get("primary_author_id") == user["user_id"]
    if not (is_primary or await _is_lab_pi(user["user_id"], lab_id)):
        raise HTTPException(status_code=403, detail="Only the report creator or lab PI can invite")

    invitee_id = request.user_id
    if invitee_id in _author_ids(submission):
        raise HTTPException(status_code=400, detail="Already a co-author")

    member = await class_members_collection.find_one({"class_id": lab_id, "user_id": invitee_id})
    if not member:
        raise HTTPException(status_code=400, detail="Not a member of this lab")
    if not member.get("stylometry_enrolled"):
        raise HTTPException(status_code=400, detail=f"{member.get('user_name', 'This member')} must complete stylometry enrollment before co-authoring")

    invitee = await users_collection.find_one({"user_id": invitee_id})
    author_entry = {
        "user_id": invitee_id,
        "name": (invitee or {}).get("name") or member.get("user_name", "Researcher"),
        "email": (invitee or {}).get("email") or member.get("user_email"),
        "joined_at": datetime.now(timezone.utc),
        "stylometry_v3": None,
        "contribution": None,
    }
    await submissions_collection.update_one(
        {"submission_id": submission_id},
        {"$push": {"report_authors": author_entry}, "$set": {"is_shared": True}},
    )
    return {"success": True, "author": {k: author_entry[k] for k in ("user_id", "name", "email")}}


@router.delete("/submissions/{submission_id}/authors/{author_id}")
async def remove_author(submission_id: str, author_id: str, authorization: Optional[str] = Header(None)):
    """Remove a co-author (cannot remove the primary author). Primary or PI only."""
    user = await _get_user(authorization)
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.get("primary_author_id") == author_id:
        raise HTTPException(status_code=400, detail="Cannot remove the primary author")
    is_primary = submission.get("primary_author_id") == user["user_id"]
    if not (is_primary or await _is_lab_pi(user["user_id"], submission.get("class_id"))):
        raise HTTPException(status_code=403, detail="Only the report creator or lab PI can remove authors")
    await submissions_collection.update_one(
        {"submission_id": submission_id},
        {"$pull": {"report_authors": {"user_id": author_id}}},
    )
    remaining = await submissions_collection.find_one({"submission_id": submission_id})
    if len(remaining.get("report_authors") or []) <= 1:
        await submissions_collection.update_one(
            {"submission_id": submission_id}, {"$set": {"is_shared": False}}
        )
    return {"success": True}


@router.post("/submissions/{submission_id}/verify-authors")
async def verify_authors(submission_id: str, request: AuthorSegments, authorization: Optional[str] = Header(None)):
    """Run stylometry per author: each author's text vs THEIR OWN enrolled profile.
    Stores each verdict on report_authors[i].stylometry_v3."""
    user = await _get_user(authorization)
    submission = await _verify_own_submission(user, submission_id)
    submission = await _ensure_report_authors(submission, request.segments)
    lab_id = submission.get("class_id")
    author_ids = set(_author_ids(submission))

    from .chunk_analyze import _stylo_verify_chunk

    results = []
    for seg in request.segments:
        if seg.user_id not in author_ids:
            continue
        text = (seg.text or "").strip()
        enrolled = await _is_stylometry_enrolled(seg.user_id, lab_id)
        if not enrolled or len(text) < 50:
            verdict = {
                "verdict": "unavailable",
                "reason": "not enrolled" if not enrolled else "insufficient text",
            }
        else:
            r = await _stylo_verify_chunk(seg.user_id, lab_id, text, absorb=False)
            verdict = {
                "verdict": r.get("verdict", "review_required"),
                "cosine_score": r.get("cosine_score"),
                "probability": r.get("probability"),
                "profile_strength": r.get("profile_strength"),
                "status": r.get("status"),
            }
        await submissions_collection.update_one(
            {"submission_id": submission_id, "report_authors.user_id": seg.user_id},
            {"$set": {"report_authors.$.stylometry_v3": verdict}},
        )
        results.append({"user_id": seg.user_id, "stylometry_v3": verdict})
    return {"success": True, "results": results}


@router.post("/submissions/{submission_id}/compute-contributions")
async def compute_contributions(submission_id: str, request: AuthorSegments, authorization: Optional[str] = Header(None)):
    """Compute BOTH contribution metrics per author:
    - final-doc share: words in the final report attributed to each author
    - keystroke effort: each author's typed keystrokes from their session snapshots
    """
    user = await _get_user(authorization)
    submission = await _verify_own_submission(user, submission_id)
    submission = await _ensure_report_authors(submission, request.segments)
    assignment_id = submission.get("assignment_id")
    author_ids = set(_author_ids(submission))

    # Final-document word share
    seg_words = {s.user_id: len((s.text or "").split()) for s in request.segments if s.user_id in author_ids}
    total_words = sum(seg_words.values()) or 1

    # Keystroke effort from each author's session snapshots (latest typedCount)
    effort = {}
    if snapshots_collection is not None:
        for uid in author_ids:
            doc = await snapshots_collection.find_one(
                {"$or": [
                    {"submission_id": submission_id, "student_id": uid},
                    {"student_id": uid, "assignment_id": assignment_id},
                ]},
                sort=[("created_at", -1)],
            )
            keys = 0
            if doc:
                for snap in reversed(doc.get("snapshots") or []):
                    if snap.get("typedCount"):
                        keys = snap["typedCount"]
                        break
            effort[uid] = keys
    total_effort = sum(effort.values()) or 1

    out = []
    for uid in author_ids:
        contribution = {
            "final_words": seg_words.get(uid, 0),
            "final_pct": round(seg_words.get(uid, 0) / total_words * 100, 1),
            "keystrokes": effort.get(uid, 0),
            "effort_pct": round(effort.get(uid, 0) / total_effort * 100, 1),
        }
        await submissions_collection.update_one(
            {"submission_id": submission_id, "report_authors.user_id": uid},
            {"$set": {"report_authors.$.contribution": contribution}},
        )
        out.append({"user_id": uid, "contribution": contribution})
    return {"success": True, "contributions": out}


# ============================================================================
# DELIVERABLES — PDF + VIDEO
# ============================================================================

@router.post("/submissions/{submission_id}/generate-pdf")
async def generate_pdf(submission_id: str, authorization: Optional[str] = Header(None)):
    """Render the submitted document to a PDF (WeasyPrint) and store it."""
    user = await _get_user(authorization)
    submission = await _verify_own_submission(user, submission_id)

    if not media.pdf_available():
        raise HTTPException(status_code=503, detail="PDF engine not available on this server")

    content_html = submission.get("content_html") or ""
    if not content_html.strip():
        raise HTTPException(status_code=400, detail="Submission has no content to render")

    assignment = await assignments_collection.find_one(
        {"assignment_id": submission.get("assignment_id")}
    )
    title = (assignment or {}).get("title", "Research Document")

    page_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 25mm 20mm; }}
  body {{ font-family: Georgia, 'Times New Roman', serif; font-size: 12pt; line-height: 1.6; color: #1a1a1a; }}
  h1.doc-title {{ font-size: 18pt; margin-bottom: 4pt; }}
  .doc-meta {{ color: #666; font-size: 9pt; margin-bottom: 18pt; border-bottom: 1px solid #ddd; padding-bottom: 8pt; }}
  img {{ max-width: 100%; }}
  table {{ border-collapse: collapse; width: 100%; }}
  td, th {{ border: 1px solid #ccc; padding: 4pt 6pt; }}
</style></head>
<body>
  <h1 class="doc-title">{title}</h1>
  <div class="doc-meta">Written in Editorrah · integrity-verified session · generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</div>
  {content_html}
</body></html>"""

    try:
        pdf_bytes = await media.generate_pdf_from_html(page_html)
    except Exception as e:
        logger.error(f"PDF generation failed for {submission_id}: {e}")
        raise HTTPException(status_code=500, detail="PDF generation failed")

    ref = await media.store_blob(pdf_bytes, "application/pdf", "research-pdfs", user["user_id"])
    if not ref:
        raise HTTPException(status_code=500, detail="PDF storage failed")

    await submissions_collection.update_one(
        {"submission_id": submission_id},
        {"$set": {"pdf_ref": ref, "pdf_generated_at": datetime.now(timezone.utc)}}
    )
    return {"success": True, "size_bytes": len(pdf_bytes)}


@router.get("/submissions/{submission_id}/pdf")
async def get_pdf(submission_id: str, authorization: Optional[str] = Header(None)):
    user = await _get_user(authorization)
    submission = await _verify_own_submission(user, submission_id)
    ref = submission.get("pdf_ref")
    if not ref:
        raise HTTPException(status_code=404, detail="PDF not generated yet")
    blob = await media.fetch_blob(ref)
    if not blob:
        raise HTTPException(status_code=404, detail="PDF not found in storage")
    data, _ = blob
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="editorrah-{submission_id[:8]}.pdf"'},
    )


@router.post("/submissions/{submission_id}/video")
async def upload_video(
    submission_id: str,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Receive the client-recorded replay WebM, transcode to MP4, store."""
    user = await _get_user(authorization)
    await _verify_own_submission(user, submission_id)

    webm_bytes = await file.read()
    if not webm_bytes:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(webm_bytes) > MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail="Video too large (max 80MB)")

    if media.ffmpeg_available():
        try:
            mp4_bytes = await media.transcode_webm_to_mp4(webm_bytes)
            content_type = "video/mp4"
        except Exception as e:
            logger.error(f"Transcode failed for {submission_id}, storing WebM as-is: {e}")
            mp4_bytes, content_type = webm_bytes, "video/webm"
    else:
        logger.warning("ffmpeg not available — storing WebM without transcode")
        mp4_bytes, content_type = webm_bytes, "video/webm"

    ref = await media.store_blob(mp4_bytes, content_type, "research-videos", user["user_id"])
    if not ref:
        raise HTTPException(status_code=500, detail="Video storage failed")

    await submissions_collection.update_one(
        {"submission_id": submission_id},
        {"$set": {
            "video_ref": ref,
            "video_content_type": content_type,
            "video_generated_at": datetime.now(timezone.utc),
        }}
    )
    return {"success": True, "content_type": content_type, "size_bytes": len(mp4_bytes)}


async def _serve_video(submission: dict) -> Response:
    ref = submission.get("video_ref")
    if not ref:
        raise HTTPException(status_code=404, detail="Video not generated yet")
    blob = await media.fetch_blob(ref)
    if not blob:
        raise HTTPException(status_code=404, detail="Video not found in storage")
    data, stored_type = blob
    content_type = submission.get("video_content_type") or stored_type or "video/mp4"
    ext = "mp4" if "mp4" in content_type else "webm"
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="editorrah-session-{submission["submission_id"][:8]}.{ext}"',
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/submissions/{submission_id}/video")
async def get_video(submission_id: str, authorization: Optional[str] = Header(None)):
    user = await _get_user(authorization)
    submission = await _verify_own_submission(user, submission_id)
    return await _serve_video(submission)


@router.get("/status")
async def research_status():
    """Capability check for deliverable engines."""
    return {
        "ffmpeg": media.ffmpeg_available(),
        "pdf": media.pdf_available(),
    }


@router.get("/enrollment/{lab_id}")
async def my_enrollment_status(lab_id: str, authorization: Optional[str] = Header(None)):
    """Whether the caller has completed stylometry enrollment in a lab.
    Used by the editor to block writing until enrollment is done."""
    user = await _get_user(authorization)
    return {"enrolled": await _is_stylometry_enrolled(user["user_id"], lab_id)}


@router.get("/topics/{assignment_id}/collab-status")
async def topic_collab_status(assignment_id: str, authorization: Optional[str] = Header(None)):
    """Whether a TOPIC is collaborative — true if ANY submission for it is
    shared or has multiple report authors. The editor uses this to force collab
    mode for EVERY co-author (each has their own submission with an inconsistent
    is_shared flag, so a per-submission check splits co-authors across modes)."""
    await _get_user(authorization)
    collaborative = False
    async for s in submissions_collection.find({"assignment_id": assignment_id}):
        if s.get("is_shared") or len(s.get("report_authors") or []) > 1:
            collaborative = True
            break
    return {"collaborative": collaborative}


# ============================================================================
# SHARING (public links — password_reset_tokens pattern)
# ============================================================================

@router.post("/submissions/{submission_id}/share")
async def create_share_link(
    submission_id: str,
    request: ShareCreate = None,
    authorization: Optional[str] = Header(None),
):
    user = await _get_user(authorization)
    submission = await _verify_own_submission(user, submission_id)

    scope = (request.scope if request else None) or ["video", "playback", "report"]
    scope = [s for s in scope if s in ("video", "playback", "report")]

    share_token = secrets.token_urlsafe(32)
    await share_tokens_collection.insert_one({
        "token": share_token,
        "submission_id": submission_id,
        "created_by": user["user_id"],
        "scope": scope,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=SHARE_TOKEN_TTL_DAYS),
        "revoked": False,
        "access_count": 0,
    })

    frontend_url = os.getenv("FRONTEND_URL", "https://www.editorrah.com")
    return {
        "success": True,
        "share_token": share_token,
        "share_url": f"{frontend_url}/share/{share_token}",
        "expires_in_days": SHARE_TOKEN_TTL_DAYS,
        "scope": scope,
    }


@router.delete("/submissions/{submission_id}/share")
async def revoke_share_links(submission_id: str, authorization: Optional[str] = Header(None)):
    user = await _get_user(authorization)
    await _verify_own_submission(user, submission_id)
    result = await share_tokens_collection.update_many(
        {"submission_id": submission_id, "revoked": False},
        {"$set": {"revoked": True}}
    )
    return {"success": True, "revoked": result.modified_count}


# ============================================================================
# CO-AUTHOR INVITE LINKS — anyone with the link can join after sign-up + the
# lab's stylometry enrollment (same topic). Distinct from the public /share
# links above (kind="coauthor_invite").
# ============================================================================

@router.post("/submissions/{submission_id}/invite-link")
async def create_coauthor_invite_link(submission_id: str, authorization: Optional[str] = Header(None)):
    """Create (or reuse) a shareable co-author invite link. Primary author / PI only."""
    user = await _get_user(authorization)
    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    lab_id = submission.get("class_id")
    is_primary = submission.get("primary_author_id") == user["user_id"]
    if not (is_primary or await _is_lab_pi(user["user_id"], lab_id)):
        raise HTTPException(status_code=403, detail="Only the report creator or lab PI can create an invite link")

    existing = await share_tokens_collection.find_one(
        {"submission_id": submission_id, "kind": "coauthor_invite", "revoked": False}
    )
    if existing:
        token = existing["token"]
    else:
        token = secrets.token_urlsafe(24)
        await share_tokens_collection.insert_one({
            "token": token, "kind": "coauthor_invite", "submission_id": submission_id,
            "created_by": user["user_id"], "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=SHARE_TOKEN_TTL_DAYS),
            "revoked": False,
        })
    frontend_url = os.getenv("FRONTEND_URL", "https://www.editorrah.com")
    return {"success": True, "token": token, "invite_url": f"{frontend_url}/join/{token}"}


async def _validate_invite_token(token: str) -> dict:
    doc = await share_tokens_collection.find_one({"token": token, "kind": "coauthor_invite"})
    if not doc or doc.get("revoked"):
        raise HTTPException(status_code=404, detail="Invite link not found or revoked")
    exp = doc.get("expires_at")
    if exp:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp:
            raise HTTPException(status_code=410, detail="Invite link has expired")
    return doc


@router.get("/join-info/{token}")
async def coauthor_invite_info(token: str):
    """PUBLIC: describe an invite link so the join page can show context."""
    doc = await _validate_invite_token(token)
    submission = await submissions_collection.find_one({"submission_id": doc["submission_id"]})
    if not submission:
        raise HTTPException(status_code=404, detail="This report no longer exists")
    assignment = await assignments_collection.find_one({"assignment_id": submission.get("assignment_id")})
    lab = await classes_collection.find_one({"class_id": submission.get("class_id")})
    inviter = await users_collection.find_one({"user_id": doc.get("created_by")})
    return {
        "topic_title": (assignment or {}).get("title", "Research Report"),
        "lab_name": (lab or {}).get("name") or (lab or {}).get("class_name", "Research Lab"),
        "lab_id": submission.get("class_id"),
        "inviter_name": (inviter or {}).get("name", "A researcher"),
    }


@router.post("/join/{token}")
async def accept_coauthor_invite(token: str, authorization: Optional[str] = Header(None)):
    """Accept a co-author invite: join the lab, then either require stylometry
    enrollment or add the caller as a co-author and return the editor route."""
    user = await _get_user(authorization)
    doc = await _validate_invite_token(token)
    submission = await submissions_collection.find_one({"submission_id": doc["submission_id"]})
    if not submission:
        raise HTTPException(status_code=404, detail="This report no longer exists")
    lab_id = submission.get("class_id")
    assignment_id = submission.get("assignment_id")
    assignment = await assignments_collection.find_one({"assignment_id": assignment_id})
    topic_title = (assignment or {}).get("title", "Research Report")

    # 1. Ensure lab membership.
    member = await class_members_collection.find_one({"class_id": lab_id, "user_id": user["user_id"]})
    if not member:
        await class_members_collection.insert_one({
            "class_id": lab_id, "user_id": user["user_id"],
            "user_name": user.get("name"), "user_email": user.get("email"),
            "role": "member", "stylometry_enrolled": False,
            "joined_at": datetime.now(timezone.utc),
        })

    # 2. Stylometry enrollment is required to co-author.
    if not await _is_stylometry_enrolled(user["user_id"], lab_id):
        return {
            "needs_enrollment": True, "lab_id": lab_id,
            "assignment_id": assignment_id, "topic_title": topic_title,
        }

    # 3. Add as co-author (idempotent) and open the collaborative editor.
    if user["user_id"] not in _author_ids(submission):
        await submissions_collection.update_one(
            {"submission_id": submission["submission_id"]},
            {"$push": {"report_authors": {
                "user_id": user["user_id"], "name": user.get("name"),
                "email": user.get("email"), "joined_at": datetime.now(timezone.utc),
                "stylometry_v3": None, "contribution": None,
            }}, "$set": {"is_shared": True}},
        )
    return {
        "joined": True, "submission_id": submission["submission_id"],
        "assignment_id": assignment_id, "lab_id": lab_id, "topic_title": topic_title,
    }


async def _validate_share_token(share_token: str) -> dict:
    # Exclude co-author invite tokens — those are not public deliverable links.
    token_doc = await share_tokens_collection.find_one(
        {"token": share_token, "kind": {"$ne": "coauthor_invite"}}
    )
    if not token_doc or token_doc.get("revoked"):
        raise HTTPException(status_code=404, detail="Share link not found or revoked")
    expires_at = token_doc.get("expires_at")
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status_code=410, detail="Share link has expired")
    return token_doc


@share_router.get("/{share_token}")
async def get_shared_submission(share_token: str):
    """PUBLIC: share payload — meta, replay snapshots, report HTML (per scope)."""
    token_doc = await _validate_share_token(share_token)
    submission_id = token_doc["submission_id"]
    scope = token_doc.get("scope", ["video", "playback", "report"])

    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission no longer exists")

    assignment = await assignments_collection.find_one(
        {"assignment_id": submission.get("assignment_id")}
    )
    author = await users_collection.find_one({"user_id": submission.get("student_id")})

    # Reconstruct per-author stylometry + contributions from the document so the
    # public report mirrors the owner's results page (no trust score).
    submission = await _heal_authors_from_content(submission)
    authors = [{
        **{k: a.get(k) for k in ("user_id", "name", "stylometry_v3", "contribution")},
        "is_primary": a.get("user_id") == submission.get("primary_author_id"),
    } for a in (submission.get("report_authors") or [])]

    payload = {
        "meta": {
            "title": (assignment or {}).get("title", "Research Document"),
            "author_name": (author or {}).get("name", "Researcher"),
            "submitted_at": submission.get("submitted_at"),
            "word_count": submission.get("word_count", 0),
            "author_count": len(authors),
        },
        "scope": scope,
        "authors": authors,
        "segments": _extract_author_segments_from_html(submission.get("content") or ""),
        "pdf_available": bool(submission.get("pdf_ref")),
        "video_available": bool(submission.get("video_ref")) and "video" in scope,
        "video_content_type": submission.get("video_content_type"),
    }

    if "playback" in scope and snapshots_collection is not None:
        doc = await snapshots_collection.find_one(
            {"submission_id": submission_id}, {"_id": 0}
        )
        if doc:
            payload["snapshots"] = doc.get("snapshots", [])
            payload["total_duration_ms"] = doc.get("total_duration_ms", 0)

        # Discrete edit-event stream (char-by-char replay with author
        # attribution) — served alongside snapshots when it exists.
        try:
            from .session_playback import _fetch_merged_events
            events, event_authors = await _fetch_merged_events(submission)
            if events:
                payload["playback_events"] = events
                payload["playback_authors"] = event_authors
        except Exception:
            pass  # snapshots remain the fallback

    if "report" in scope:
        payload["report_html"] = submission.get("report_html")

    try:
        await share_tokens_collection.update_one(
            {"_id": token_doc["_id"]}, {"$inc": {"access_count": 1}}
        )
    except Exception:
        pass  # non-critical

    return payload


@share_router.get("/{share_token}/video")
async def get_shared_video(share_token: str):
    """PUBLIC: stream the replay video for a valid share token."""
    token_doc = await _validate_share_token(share_token)
    if "video" not in token_doc.get("scope", []):
        raise HTTPException(status_code=403, detail="Video not shared on this link")
    submission = await submissions_collection.find_one(
        {"submission_id": token_doc["submission_id"]}
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission no longer exists")
    return await _serve_video(submission)


@share_router.get("/{share_token}/pdf")
async def get_shared_pdf(share_token: str):
    """PUBLIC: download the document PDF for a valid share token."""
    token_doc = await _validate_share_token(share_token)
    submission = await submissions_collection.find_one(
        {"submission_id": token_doc["submission_id"]}
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission no longer exists")
    ref = submission.get("pdf_ref")
    if not ref:
        raise HTTPException(status_code=404, detail="No PDF available for this report")
    blob = await media.fetch_blob(ref)
    if not blob:
        raise HTTPException(status_code=404, detail="PDF not found in storage")
    data, _ = blob
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="editorrah-{submission["submission_id"][:8]}.pdf"'},
    )
