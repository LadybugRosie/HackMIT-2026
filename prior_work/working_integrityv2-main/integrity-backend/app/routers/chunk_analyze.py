"""
Chunk-Level AI + Stylometry Analysis

Runs GPTZero AI detection and/or forensicstylo /course/verify on individual
text chunks (external pastes or blind windows) in parallel.  Returns per-chunk
verdicts (AI probability + stylometry) as an independent qualitative signal.
"""
from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import logging
import os
import httpx

router = APIRouter(prefix="/api/chunk-analyze", tags=["chunk-analysis"])
logger = logging.getLogger(__name__)

STYLOMETRY_V3_BASE = os.getenv("STYLOMETRY_V3_BASE", "https://forensicstylo.up.railway.app")

# Rate-limit concurrent GPTZero calls
_gptzero_semaphore = asyncio.Semaphore(5)

# MongoDB collection references (set by main.py)
users_collection = None
sessions_collection = None
class_members_collection = None


def set_collections(users, sessions, members):
    global users_collection, sessions_collection, class_members_collection
    users_collection = users
    sessions_collection = sessions
    class_members_collection = members


# ---------------------------------------------------------------------------
# Auth helpers (same pattern as stylometry_v3.py)
# ---------------------------------------------------------------------------
def _extract_token(token: Optional[str] = None, authorization: Optional[str] = Header(None)) -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    if authorization:
        return authorization
    if token:
        return token
    raise HTTPException(status_code=401, detail="Authentication required")


async def _get_user(token: str):
    from .auth import get_current_user
    user = await get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class ChunkItem(BaseModel):
    text: str
    source: str = "window"  # "paste" or "window"
    word_count: int = 0


class ChunkAnalyzeRequest(BaseModel):
    class_id: Optional[str] = None
    chunks: List[ChunkItem]
    ai_enabled: bool = True
    stylo_enabled: bool = True


# ---------------------------------------------------------------------------
# Per-chunk analysis coroutines
# ---------------------------------------------------------------------------
async def _gptzero_chunk(text: str) -> dict:
    """Run GPTZero on a single chunk with semaphore rate-limiting."""
    async with _gptzero_semaphore:
        from .auth import gptzero_predict
        return await gptzero_predict(text)


async def _stylo_verify_chunk(
    student_id: str, class_id: str, text: str, absorb: bool = False
) -> dict:
    """Run forensicstylo /course/verify on a single chunk."""
    # Strip HTML if present
    if "<" in text and ">" in text:
        from ..services.auto_grading import strip_html_tags
        text = strip_html_tags(text)

    try:
        from ..utils.http_client import get_client
        client = get_client()
        body: Dict[str, Any] = {
            "student_id": student_id,
            "class_id": class_id,
            "submission_text": text,
        }
        if not absorb:
            body["absorb"] = False

        response = await client.post(
            f"{STYLOMETRY_V3_BASE}/course/verify",
            json=body,
            timeout=120,
        )
        if response.status_code in (400, 404, 422):
            try:
                err = response.json()
            except Exception:
                err = {"detail": response.text}
            return {"status": "error", "detail": err.get("detail", "Verification failed")}

        response.raise_for_status()
        result = response.json()
        return {"status": "success", **result}
    except httpx.HTTPError as e:
        logger.error(f"Chunk stylo verify failed: {e}")
        return {"status": "error", "detail": str(e)}
    except Exception as e:
        logger.error(f"Chunk stylo verify unexpected error: {e}")
        return {"status": "error", "detail": str(e)}


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------
@router.post("")
async def analyze_chunks(
    request: ChunkAnalyzeRequest,
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
):
    """
    Analyse text chunks in parallel for AI detection + stylometry verification.

    Called by print.vue after whole-doc analysis.  Each chunk is an external
    paste (CA on) or a blind window (CA off) sent as plaintext.
    """
    resolved_token = _extract_token(token, authorization)
    user = await _get_user(resolved_token)
    student_id = user["user_id"]

    # Validation
    if not request.chunks:
        return {"success": True, "chunks": [], "any_flagged": False, "summary": "No chunks"}
    if len(request.chunks) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 chunks per request")

    # Check stylometry enrollment once (avoid per-chunk 400s)
    stylo_available = False
    if request.stylo_enabled and request.class_id:
        if class_members_collection is not None:
            membership = await class_members_collection.find_one({
                "class_id": request.class_id,
                "user_id": student_id,
            })
            stylo_available = bool(membership and membership.get("stylometry_enrolled"))

    # -----------------------------------------------------------------------
    # Build parallel tasks: [ai_task_0, stylo_task_0, ai_task_1, stylo_task_1, ...]
    # -----------------------------------------------------------------------
    tasks = []
    valid_indices = []  # track which chunks actually get tasks

    for i, chunk in enumerate(request.chunks):
        # Cap chunk text at 50k chars to prevent abuse
        if len(chunk.text) > 50000:
            chunk.text = chunk.text[:50000]
        wc = chunk.word_count or len(chunk.text.split())
        if wc < 50:
            continue  # too short to analyse
        valid_indices.append(i)

        # AI detection task
        if request.ai_enabled and wc >= 100:
            tasks.append(_gptzero_chunk(chunk.text))
        else:
            tasks.append(_make_skipped_future())

        # Stylometry task (absorb=False on first pass)
        if stylo_available:
            tasks.append(_stylo_verify_chunk(student_id, request.class_id, chunk.text, absorb=False))
        else:
            tasks.append(_make_skipped_future())

    # Run all in parallel
    if not tasks:
        return {"success": True, "chunks": [], "any_flagged": False, "summary": "No analysable chunks"}

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # -----------------------------------------------------------------------
    # Assemble per-chunk results
    # -----------------------------------------------------------------------
    chunk_results = []
    flagged_count = 0
    flagged_texts = []

    for idx_pos, chunk_idx in enumerate(valid_indices):
        chunk = request.chunks[chunk_idx]
        wc = chunk.word_count or len(chunk.text.split())
        ai_offset = idx_pos * 2
        stylo_offset = idx_pos * 2 + 1

        # Parse AI result
        ai_raw = raw_results[ai_offset] if ai_offset < len(raw_results) else None
        if isinstance(ai_raw, Exception):
            ai_raw = {"status": "error", "detail": str(ai_raw)}

        ai_prob = ai_raw.get("ai_probability", 0) if isinstance(ai_raw, dict) else 0
        ai_class = ai_raw.get("predicted_class", "unknown") if isinstance(ai_raw, dict) else "unknown"
        ai_status = ai_raw.get("status", "error") if isinstance(ai_raw, dict) else "error"

        # Parse stylo result
        stylo_raw = raw_results[stylo_offset] if stylo_offset < len(raw_results) else None
        if isinstance(stylo_raw, Exception):
            stylo_raw = {"status": "error", "detail": str(stylo_raw)}

        stylo_verdict = stylo_raw.get("verdict") if isinstance(stylo_raw, dict) else None
        stylo_cosine = stylo_raw.get("cosine_score") if isinstance(stylo_raw, dict) else None
        stylo_status = stylo_raw.get("status", "error") if isinstance(stylo_raw, dict) else "error"

        # Determine flags
        flag_reasons = []
        ai_flagged = ai_status == "success" and ai_prob > 0.5
        stylo_flagged = stylo_status == "success" and stylo_verdict == "flagged"

        if ai_flagged:
            flag_reasons.append("ai_detected")
        if stylo_flagged:
            flag_reasons.append("style_mismatch")

        is_flagged = bool(flag_reasons)
        if is_flagged:
            flagged_count += 1
            flagged_texts.append(chunk.text)

        chunk_results.append({
            "chunk_index": chunk_idx,
            "word_count": wc,
            "source": chunk.source,
            "text_preview": chunk.text[:80] + ("..." if len(chunk.text) > 80 else ""),
            "ai_probability": round(ai_prob, 4) if ai_prob is not None else 0,
            "ai_class": ai_class,
            "ai_status": ai_status,
            "stylo_verdict": stylo_verdict,
            "stylo_cosine": round(stylo_cosine, 4) if stylo_cosine is not None else None,
            "stylo_status": stylo_status,
            "flagged": is_flagged,
            "flag_reasons": flag_reasons,
        })

    # -----------------------------------------------------------------------
    # Flywheel: absorb verified chunks into profile (post-processing)
    # -----------------------------------------------------------------------
    if stylo_available:
        absorb_tasks = []
        for cr in chunk_results:
            if (cr["stylo_status"] == "success"
                    and cr["stylo_verdict"] == "verified"
                    and not cr["flagged"]):
                chunk_text = request.chunks[cr["chunk_index"]].text
                absorb_tasks.append(
                    _stylo_verify_chunk(student_id, request.class_id, chunk_text, absorb=True)
                )
        if absorb_tasks:
            # Fire-and-forget — don't block response on absorption
            async def _absorb_all():
                await asyncio.gather(*absorb_tasks, return_exceptions=True)
            asyncio.create_task(_absorb_all())

    # -----------------------------------------------------------------------
    # Build summary
    # -----------------------------------------------------------------------
    total_chunks = len(chunk_results)
    any_flagged = flagged_count > 0

    if flagged_count == 0:
        summary = f"All {total_chunks} chunks verified clean"
    else:
        reasons = set()
        for cr in chunk_results:
            reasons.update(cr["flag_reasons"])
        reason_str = " + ".join(sorted(reasons)).replace("ai_detected", "AI").replace("style_mismatch", "style mismatch")
        summary = f"{flagged_count} of {total_chunks} chunks flagged ({reason_str})"

    return {
        "success": True,
        "chunks": chunk_results,
        "any_flagged": any_flagged,
        "flagged_count": flagged_count,
        "flagged_chunks_text": flagged_texts,
        "summary": summary,
    }


async def _make_skipped_future():
    """Return a skipped result for tasks that don't need to run."""
    return {"status": "skipped"}
