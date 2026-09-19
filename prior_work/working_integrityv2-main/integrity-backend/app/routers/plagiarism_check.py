"""
Plagiarism Check Router — Endpoints for v2 plagiarism detection engine
======================================================================

Endpoints:
  POST /api/plagiarism/check               — Check any text for plagiarism
  POST /api/plagiarism/check-submission/{id} — Run full check on a submission (teacher)
  GET  /api/plagiarism/report/{check_id}    — Get HTML report for a completed check
  POST /api/plagiarism/batch/{assignment_id} — Batch-check all submissions (teacher)
  GET  /api/plagiarism/status               — Engine status / capabilities
"""

from fastapi import APIRouter, HTTPException, Query, Header, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


router = APIRouter(prefix="/api/plagiarism", tags=["Plagiarism Detection v2"])

# MongoDB collection references (set by main.py)
submissions_collection = None
assignments_collection = None
classes_collection = None
class_members_collection = None
users_collection = None


def set_collections(submissions, assignments, classes, members, users):
    global submissions_collection, assignments_collection, classes_collection
    global class_members_collection, users_collection
    submissions_collection = submissions
    assignments_collection = assignments
    classes_collection = classes
    class_members_collection = members
    users_collection = users


# ---------------------------------------------------------------------------
# Auth helpers (mirrors pattern from other routers)
# ---------------------------------------------------------------------------

async def _get_user(token: str):
    from .auth import get_current_user
    return await get_current_user(token)


def _extract_token(token: Optional[str] = None, authorization: Optional[str] = Header(None)) -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    if authorization:
        return authorization
    if token:
        return token
    raise HTTPException(status_code=401, detail="Authentication required")


async def _refresh_role(user: dict) -> dict:
    if users_collection is not None and user.get("user_id"):
        db_user = await users_collection.find_one({"user_id": user["user_id"]})
        if db_user:
            user["role"] = db_user.get("role", user.get("role", "student"))
    return user


async def _require_teacher(token: str) -> dict:
    user = await _get_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await _refresh_role(user)
    if user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can perform this action")
    return user


async def _require_auth(token: str) -> dict:
    user = await _get_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class PlagiarismCheckRequest(BaseModel):
    content: str = Field(..., min_length=50, max_length=500000)
    title: Optional[str] = Field(None, max_length=500)
    check_internal: bool = True
    check_scholarly: bool = True
    check_web: bool = True


class SubmissionCheckRequest(BaseModel):
    check_internal: bool = True
    check_scholarly: bool = True
    check_web: bool = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/check")
async def check_text(
    request: PlagiarismCheckRequest,
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
):
    """
    Run plagiarism detection on arbitrary text.
    Checks against internal corpus + 240M+ scholarly works via OpenAlex,
    Semantic Scholar, and Crossref + web sources (news, Wikipedia, blogs).
    """
    resolved_token = _extract_token(token, authorization)
    user = await _require_auth(resolved_token)

    from ..services.plagiarism_v2 import check_plagiarism_v2

    result = await check_plagiarism_v2(
        content=request.content,
        title=request.title or "",
        check_internal=request.check_internal,
        check_scholarly=request.check_scholarly,
        check_web=request.check_web,
    )

    return result


@router.post("/check-submission/{submission_id}")
async def check_submission(
    submission_id: str,
    request: SubmissionCheckRequest = SubmissionCheckRequest(),
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
):
    """
    Run full plagiarism v2 pipeline on a specific submission.
    Teacher only. Updates the submission record with results.
    """
    resolved_token = _extract_token(token, authorization)
    user = await _require_teacher(resolved_token)

    if submissions_collection is None:
        raise HTTPException(status_code=503, detail="Database not available")

    submission = await submissions_collection.find_one({"submission_id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Verify teacher owns this class
    class_doc = await classes_collection.find_one({"class_id": submission["class_id"]})
    if not class_doc or class_doc["teacher_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized for this class")

    content = submission.get("content") or submission.get("content_html") or ""
    # Always strip HTML — content field often contains HTML markup
    import re
    content = re.sub(r"<script[^>]*>.*?</script>", " ", content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"<style[^>]*>.*?</style>", " ", content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"<[^>]+>", " ", content)
    content = re.sub(r"&[#\w]+;", " ", content)
    content = re.sub(r"\s+", " ", content).strip()
    if not content or len(content) < 50:
        raise HTTPException(status_code=400, detail="Submission content too short for plagiarism check")

    from ..services.plagiarism_v2 import check_plagiarism_v2

    result = await check_plagiarism_v2(
        content=content,
        submission_id=submission_id,
        assignment_id=submission.get("assignment_id", ""),
        class_id=submission.get("class_id", ""),
        student_id=submission.get("student_id", ""),
        check_internal=request.check_internal,
        check_scholarly=request.check_scholarly,
        check_web=request.check_web,
    )

    # Resolve student names for internal matches
    student_ids = {m.get("matched_student_id", "") for m in result.get("internal_matches", []) if m.get("matched_student_id")}
    student_names = {}
    if student_ids and users_collection is not None:
        async for u in users_collection.find(
            {"user_id": {"$in": list(student_ids)}},
            {"user_id": 1, "name": 1, "email": 1}
        ):
            student_names[u["user_id"]] = u.get("name") or u.get("email", "").split("@")[0]

    # Update submission with results
    all_matches = []
    for m in result.get("internal_matches", []):
        sid = m.get("matched_student_id", "")
        all_matches.append({
            "matched_submission_id": m.get("matched_submission_id", ""),
            "matched_student_id": sid,
            "matched_student_name": student_names.get(sid, ""),
            "similarity_score": m["similarity_score"],
            "matching_segments": m.get("details", {}).get("matching_passages", [])[:5],
            "type": m.get("source_type", "internal"),
            "source_type": m.get("source_type", "internal"),
        })
    for m in result.get("scholarly_matches", []):
        all_matches.append({
            "source_type": "scholarly",
            "type": "scholarly",
            "title": m.get("title", ""),
            "authors": m.get("authors", []),
            "doi": m.get("doi", ""),
            "url": m.get("url", ""),
            "journal": m.get("journal", ""),
            "year": m.get("year"),
            "citation": m.get("citation", ""),
            "similarity_score": m["similarity_score"],
            "match_type": m.get("match_type", ""),
            "matching_segments": m.get("details", {}).get("matching_passages", [])[:3],
        })
    for m in result.get("web_matches", []):
        all_matches.append({
            "source_type": "web",
            "type": "web",
            "title": m.get("title", ""),
            "url": m.get("url", ""),
            "search_engine": m.get("search_engine", ""),
            "similarity_score": m["similarity_score"],
            "match_type": m.get("match_type", ""),
            "matching_segments": m.get("details", {}).get("matching_passages", [])[:5],
        })

    all_matches.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)

    await submissions_collection.update_one(
        {"submission_id": submission_id},
        {"$set": {
            "plagiarism_score": result.get("overall_score", 0),
            "plagiarism_matches": all_matches[:15],
            "plagiarism_v2_check_id": result.get("check_id"),
            "plagiarism_v2_scholarly_count": result.get("scholarly_matches_count", 0),
            "plagiarism_v2_internal_count": result.get("internal_matches_count", 0),
            "plagiarism_v2_web_count": result.get("web_matches_count", 0),
            "plagiarism_v2_checked_at": datetime.now(timezone.utc),
        }},
    )

    # No composite recompute: plagiarism is an independent signal, and
    # plagiarism_v2_checked_at (set above) is what clears similarity_pending.
    return result


@router.get("/report/{check_id}")
async def get_report(
    check_id: str,
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
):
    """
    Get the HTML plagiarism report for a completed check.
    """
    resolved_token = _extract_token(token, authorization)
    await _require_auth(resolved_token)

    from ..services.plagiarism_v2 import _plagiarism_checks_col, generate_report_html

    if _plagiarism_checks_col is None:
        raise HTTPException(status_code=503, detail="Database not available")

    check = await _plagiarism_checks_col.find_one({"check_id": check_id})
    if not check:
        raise HTTPException(status_code=404, detail="Plagiarism check not found")

    html = generate_report_html(check)
    return HTMLResponse(content=html, headers={
        "Content-Type": "text/html; charset=utf-8",
        "X-Content-Type-Options": "nosniff",
    })


@router.post("/batch/{assignment_id}")
async def batch_check(
    assignment_id: str,
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
):
    """
    Run plagiarism v2 pipeline on ALL submissions for an assignment.
    Teacher only. This can take several minutes for large classes.
    """
    resolved_token = _extract_token(token, authorization)
    user = await _require_teacher(resolved_token)

    if assignments_collection is None:
        raise HTTPException(status_code=503, detail="Database not available")

    assignment = await assignments_collection.find_one({"assignment_id": assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    class_doc = await classes_collection.find_one({"class_id": assignment["class_id"]})
    if not class_doc or class_doc["teacher_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized for this class")

    from ..services.plagiarism_v2 import batch_check_v2

    result = await batch_check_v2(assignment_id)
    return result


@router.get("/status")
async def engine_status(
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
):
    """
    Return the plagiarism engine's current capabilities and status.
    Useful for the frontend to know what features are available.
    """
    resolved_token = _extract_token(token, authorization)
    await _require_auth(resolved_token)

    from ..services.plagiarism_v2 import HAS_DATASKETCH, HAS_SKLEARN, HAS_NLTK

    return {
        "engine": "plagiarism_v2",
        "version": "2.0.0",
        "capabilities": {
            "internal_corpus_check": True,
            "scholarly_api_check": True,
            "minhash_lsh": HAS_DATASKETCH,
            "sklearn_tfidf": HAS_SKLEARN,
            "nltk_sentence_split": HAS_NLTK,
        },
        "scholarly_apis": {
            "openalex": {"coverage": "240M+ works", "status": "active", "cost": "free"},
            "semantic_scholar": {"coverage": "200M+ papers", "status": "active", "cost": "free"},
            "crossref": {"coverage": "150M+ records", "status": "active", "cost": "free"},
        },
        "detection_methods": [
            "winnowing_fingerprinting",
            "minhash_lsh",
            "tfidf_cosine_similarity",
            "word_ngram_jaccard",
            "sentence_level_similarity",
            "passage_alignment",
        ],
        "enrichment": [
            "doi", "title", "authors", "journal", "publisher", "year",
            "citation_count", "open_access_url", "license", "issn",
            "subjects", "auto_citation_apa",
        ],
    }
