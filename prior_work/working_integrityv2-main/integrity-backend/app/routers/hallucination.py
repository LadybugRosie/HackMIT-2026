"""
Hallucination Check Router — standalone surface (file upload + text box).

Reuses the same OpenFactCheck engine that powers the in-editor
"Hallucination & Source Check" panel (auth.py /factcheck/verify), but adds:
  - document upload (PDF / DOCX / TXT / MD) with server-side text extraction
  - run history per user (hallucination_checks collection)

Endpoints:
  POST /api/hallucination/check       — JSON {text, evidence_mode}
  POST /api/hallucination/check-file  — multipart file upload (+ evidence_mode)
  GET  /api/hallucination/history     — caller's recent checks (summaries)
"""

import asyncio
import io
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hallucination", tags=["hallucination"])

# MongoDB collections — set by main.py on startup
checks_collection = None
users_collection = None

# Defaults to prod; set OPENFACTCHECK_URL to point at a local engine for testing.
OPENFACTCHECK_URL = os.getenv(
    "OPENFACTCHECK_URL", "https://openfactcheck-production.up.railway.app/v1/verify"
)
# Shared secret the engine requires (x-api-key). Must match one of the engine's API_KEYS.
OPENFACTCHECK_API_KEY = os.getenv("OPENFACTCHECK_API_KEY", "")
MAX_FILE_BYTES = 100 * 1024 * 1024  # 100MB — matches RequestSizeMiddleware hallucination cap
MAX_TEXT_CHARS = 100_000           # cap text sent to the fact-check engine (general)
# Published papers are long and their reference list sits at the very end — a
# small cap chops the references off, breaking citation mapping. Send the whole
# paper in published-paper mode so the engine can parse the reference list.
# Keep <= the engine's MAX_TEXT_CHARS or it returns 0 claims. Prod engine caps
# ~100K, so cap here too (truncate-with-warning) until the engine cap is raised.
PUBLISHED_PAPER_MAX_CHARS = 100_000
ALLOWED_EVIDENCE_MODES = ("REGISTRY_ONLY", "OFFLINE_ONLY", "HYBRID")


def set_collections(checks, users):
    global checks_collection, users_collection
    checks_collection = checks
    users_collection = users


def _extract_token(authorization: Optional[str]) -> str:
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
    return user


ALLOWED_MODES = ("general", "published_paper")


class HallucinationCheckRequest(BaseModel):
    text: str
    evidence_mode: str = "REGISTRY_ONLY"
    mode: str = "general"  # "general" | "published_paper" (IEEE/journal audit)


def _empty_result(warning: str, error: bool = False) -> dict:
    return {
        "summary": {"supported": 0, "unsupported": 0, "contradicted": 0, "unknown": 0},
        "claims": [],
        "warnings": [warning],
        "reference_report": {"dois": [], "urls": [], "summary": {}},
        # Explicit failure flag: the frontend must show an error state, never
        # a false-clean "no issues found" when the engine was unreachable.
        "error": error,
    }


async def _call_openfactcheck(text: str, evidence_mode: str, mode: str = "general") -> dict:
    """Same engine + response shape as the in-editor fact-check proxy."""
    if evidence_mode not in ALLOWED_EVIDENCE_MODES:
        evidence_mode = "REGISTRY_ONLY"
    if mode not in ALLOWED_MODES:
        mode = "general"
    # Normalize Unicode dashes (en/em/minus/non-breaking hyphen) so DOIs like
    # 10.1016/S0140-6736(20)31142-9 copied from PDFs parse correctly downstream.
    text = text.translate(str.maketrans({
        "–": "-", "—": "-", "−": "-", "‑": "-",
    }))
    cap = PUBLISHED_PAPER_MAX_CHARS if mode == "published_paper" else MAX_TEXT_CHARS
    truncated = False
    if len(text) > cap:
        text = text[:cap]
        truncated = True
    try:
        from ..utils.http_client import get_client
        client = get_client()
        # Long docs produce many claims, each LLM-verified. This runs inside an
        # async background job (see _run_job), so a long wait is fine — give a
        # full paper room to finish.
        response = await client.post(
            OPENFACTCHECK_URL,
            json={"text": text, "evidence_mode": evidence_mode, "mode": mode},
            timeout=600.0,
            headers={"x-api-key": OPENFACTCHECK_API_KEY} if OPENFACTCHECK_API_KEY else None,
        )
        if response.status_code == 200:
            result = response.json()
            if truncated:
                result.setdefault("warnings", []).append(
                    f"Document truncated to {cap:,} characters for analysis"
                )
            return result
        if response.status_code in (401, 403):
            hint = ("backend is missing OPENFACTCHECK_API_KEY"
                    if not OPENFACTCHECK_API_KEY
                    else "OPENFACTCHECK_API_KEY does not match the engine's API_KEYS")
            logger.error(f"OpenFactCheck auth failed ({response.status_code}) — {hint}")
            return _empty_result(
                f"Fact-check engine rejected the request ({hint}). No claims were analyzed.",
                error=True,
            )
        logger.error(f"OpenFactCheck returned {response.status_code}: {response.text[:200]}")
        return _empty_result(f"Fact check API error: {response.status_code}. No claims were analyzed.", error=True)
    except Exception as e:
        logger.error(f"OpenFactCheck call failed: {e}")
        return _empty_result(f"Fact check service error: {str(e)}. No claims were analyzed.", error=True)


# ============================================================================
# TEXT EXTRACTION
# ============================================================================

def _extract_pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts)


def _extract_docx_text(data: bytes) -> str:
    import docx
    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)


def extract_text_from_upload(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _extract_pdf_text(data)
    if name.endswith(".docx"):
        return _extract_docx_text(data)
    if name.endswith((".txt", ".md", ".markdown", ".text")):
        return data.decode("utf-8", errors="replace")
    raise HTTPException(
        status_code=415,
        detail="Unsupported file type — upload a PDF, DOCX, TXT or MD file",
    )


async def _record_check(user: dict, source: str, text: str, result: dict, filename: str = None):
    if checks_collection is None:
        return
    try:
        claims = result.get("claims") or []
        # Recompute the summary from the actual claims so file uploads always
        # store the real supported/unsupported/contradicted/unknown counts —
        # never a stale or empty summary (e.g. from a partial/error result).
        summary = {"supported": 0, "unsupported": 0, "contradicted": 0, "unknown": 0}
        for c in claims:
            v = c.get("verdict")
            if v in summary:
                summary[v] += 1
        # Don't pollute history with failed runs (engine error → 0 claims + warning).
        if not claims:
            warns = result.get("warnings") or []
            is_error = any("error" in str(w).lower() or "too short" in str(w).lower() for w in warns)
            if is_error:
                return
        await checks_collection.insert_one({
            "check_id": str(uuid.uuid4()),
            "user_id": user["user_id"],
            "source": source,                 # "text" | "file"
            "filename": filename,
            "word_count": result.get("extracted_word_count") or len(text.split()),
            "summary": summary,
            "claim_count": len(claims),
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.warning(f"Failed to record hallucination check (non-critical): {e}")


# ============================================================================
# ASYNC JOBS
# A full-document fact check takes 1-3 minutes (each claim is LLM-verified).
# Holding one HTTP request open that long gets reset by the edge proxy
# (ERR_HTTP2_PROTOCOL_ERROR). Instead: POST returns a job_id immediately, a
# background task runs the check, and the client polls GET /job/{id}.
# Jobs are stored in MongoDB so they survive across requests/replicas.
# ============================================================================

def _jobs_col():
    """Lazily derive the jobs collection from the existing DB handle (no main.py change)."""
    if checks_collection is None:
        return None
    return checks_collection.database["hallucination_jobs"]


async def _run_job(job_id: str, text: str, evidence_mode: str, mode: str, user: dict, source: str, filename: str = None):
    """Background worker: run the fact check, store the result on the job doc."""
    col = _jobs_col()
    try:
        result = await _call_openfactcheck(text, evidence_mode, mode)
        result["extracted_word_count"] = len(text.split())
        if filename:
            result["filename"] = filename
        await _record_check(user, source, text, result, filename=filename)
        if col is not None:
            await col.update_one({"job_id": job_id}, {"$set": {
                "status": "done", "result": result, "finished_at": datetime.now(timezone.utc),
            }})
    except Exception as e:
        logger.error(f"Hallucination job {job_id} failed: {e}")
        if col is not None:
            await col.update_one({"job_id": job_id}, {"$set": {
                "status": "error", "error": str(e), "finished_at": datetime.now(timezone.utc),
            }})


async def _enqueue(text: str, evidence_mode: str, mode: str, user: dict, source: str, filename: str = None) -> str:
    """Create a job, kick off the background worker, return the job_id."""
    col = _jobs_col()
    job_id = str(uuid.uuid4())
    if col is not None:
        # opportunistic cleanup of old jobs (cheap, keeps the collection small)
        try:
            await col.delete_many({"created_at": {"$lt": datetime.now(timezone.utc) - timedelta(days=1)}})
        except Exception:
            pass
        await col.insert_one({
            "job_id": job_id, "user_id": user["user_id"], "status": "processing",
            "source": source, "filename": filename, "created_at": datetime.now(timezone.utc),
        })
    asyncio.create_task(_run_job(job_id, text, evidence_mode, mode, user, source, filename))
    return job_id


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/check")
async def check_text(request: HallucinationCheckRequest, authorization: Optional[str] = Header(None)):
    """Start an async fact check on pasted text. Returns {job_id} to poll."""
    user = await _get_user(authorization)
    text = (request.text or "").strip()
    if len(text) < 50:
        return _empty_result("Text too short for fact checking (minimum 50 characters)")
    job_id = await _enqueue(text, request.evidence_mode, request.mode, user, "text")
    return {"job_id": job_id, "status": "processing"}


@router.post("/check-file")
async def check_file(
    file: UploadFile = File(...),
    evidence_mode: str = Form("REGISTRY_ONLY"),
    mode: str = Form("general"),
    authorization: Optional[str] = Header(None),
):
    """Start an async fact check on an uploaded document (PDF/DOCX/TXT/MD). Returns {job_id} to poll."""
    user = await _get_user(authorization)

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    try:
        text = extract_text_from_upload(file.filename, data).strip()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Text extraction failed for {file.filename}: {e}")
        raise HTTPException(status_code=422, detail="Could not extract text from this file")

    if len(text) < 50:
        return _empty_result(
            "Could not extract enough text from this file (minimum 50 characters). "
            "Scanned/image-only PDFs are not supported."
        )

    job_id = await _enqueue(text, evidence_mode, mode, user, "file", file.filename)
    return {"job_id": job_id, "status": "processing"}


@router.get("/job/{job_id}")
async def get_job(job_id: str, authorization: Optional[str] = Header(None)):
    """Poll a fact-check job. Returns {status: processing|done|error} (+ the result when done)."""
    user = await _get_user(authorization)
    col = _jobs_col()
    if col is None:
        raise HTTPException(status_code=503, detail="Job store unavailable")
    job = await col.find_one({"job_id": job_id, "user_id": user["user_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    status = job.get("status")
    if status == "processing":
        return {"status": "processing"}
    if status == "error":
        return {"status": "error", "error": job.get("error", "Verification failed")}
    return {"status": "done", **(job.get("result") or {})}


@router.get("/history")
async def check_history(authorization: Optional[str] = Header(None)):
    """Caller's recent hallucination checks (summaries only)."""
    user = await _get_user(authorization)
    if checks_collection is None:
        return {"checks": []}
    checks = await checks_collection.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(length=50)
    return {"checks": checks}
