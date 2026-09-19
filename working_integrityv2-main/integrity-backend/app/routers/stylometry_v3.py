"""
Stylometry V3 Router — Per-Course Enrollment & Verification

Uses the external forensicstylo API's /course/* endpoints.
Each student must enroll per-course with 3+ writing samples.
Verified submissions are auto-absorbed by the API (data flywheel).
"""
from fastapi import APIRouter, HTTPException, Query, Header
from typing import Optional, List
from datetime import datetime, timezone
import os
import logging
import httpx

from ..models import StylometryV3EnrollRequest, StylometryV3VerifyRequest

router = APIRouter(prefix="/api/stylometry/v3", tags=["Stylometry V3"])
logger = logging.getLogger(__name__)

# Prod default is the deployed engine; override with env STYLOMETRY_V3_BASE=http://127.0.0.1:8081 for local dev.
STYLOMETRY_V3_BASE = os.getenv("STYLOMETRY_V3_BASE", "https://forensicstylo.up.railway.app")

# MongoDB collection references (set by main.py)
users_collection = None
sessions_collection = None
class_members_collection = None
classes_collection = None
assignments_collection = None
submissions_collection = None


def set_collections(users, sessions, members, classes, assignments=None, submissions=None):
    global users_collection, sessions_collection, class_members_collection
    global classes_collection, assignments_collection, submissions_collection
    users_collection = users
    sessions_collection = sessions
    class_members_collection = members
    classes_collection = classes
    assignments_collection = assignments
    submissions_collection = submissions


def _extract_token(token: Optional[str] = None, authorization: Optional[str] = Header(None)) -> str:
    if authorization and authorization.startswith('Bearer '):
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


# ============================================================================
# AI DETECTION HELPER (reuse from auth router)
# ============================================================================
async def _check_ai_on_samples(samples: List[str]) -> dict:
    """Run AI detection on enrollment samples. Returns {flagged: bool, details: [...]}"""
    try:
        from .auth import gptzero_predict, is_ai_written
    except ImportError:
        return {"flagged": False, "details": []}

    details = []
    for i, sample in enumerate(samples):
        result = await gptzero_predict(sample)
        flagged = is_ai_written(result)
        details.append({
            "sample_index": i,
            "ai_flagged": flagged,
            "ai_probability": result.get("ai_probability", 0),
            "predicted_class": result.get("predicted_class"),
        })
    all_flagged = all(d["ai_flagged"] for d in details)
    return {"flagged": all_flagged, "details": details}


# ============================================================================
# ENDPOINT 1: Enroll student in a course (per-course, 3+ samples)
# ============================================================================
@router.post("/enroll")
async def enroll_in_course(
    request: StylometryV3EnrollRequest,
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
):
    """
    Enroll a student's writing style for a specific course.
    Requires 3+ writing samples (400+ words each).
    Rejects if all samples are AI-generated.
    """
    resolved_token = _extract_token(token, authorization)
    user = await _get_user(resolved_token)

    if len(request.samples) < 3:
        raise HTTPException(status_code=400, detail="At least 3 writing samples required")

    for i, sample in enumerate(request.samples):
        wc = len(sample.split())
        if wc < 400:
            raise HTTPException(
                status_code=400,
                detail=f"Sample {i+1} must have at least 400 words (current: {wc})"
            )

    # Verify student is a member of the class
    membership = await class_members_collection.find_one({
        "class_id": request.class_id,
        "user_id": user["user_id"],
    })
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this class")

    # Strip HTML from samples to ensure forensicstylo receives plain text
    from ..services.auto_grading import strip_html_tags
    clean_samples = []
    for s in request.samples:
        clean_samples.append(strip_html_tags(s) if '<' in s and '>' in s else s)

    # AI detection gate
    ai_check = await _check_ai_on_samples(clean_samples)
    if ai_check["flagged"]:
        raise HTTPException(
            status_code=400,
            detail="All writing samples appear to be AI-generated. Please write in your own words."
        )

    student_id = user["user_id"]
    student_name = user.get("name", "")

    # Call external V3 course/enroll
    try:
        from ..utils.http_client import get_client
        client = get_client()
        response = await client.post(
            f"{STYLOMETRY_V3_BASE}/course/enroll",
            json={
                "student_id": student_id,
                "name": student_name,
                "class_id": request.class_id,
                "writing_samples": clean_samples,
            },
            timeout=120,
        )
        response.raise_for_status()
        enroll_result = response.json()
    except httpx.HTTPError as e:
        logger.error(f"Stylometry V3 enroll failed: {e}")
        raise HTTPException(status_code=502, detail=f"Stylometry service error: {str(e)}")

    # Update class_members with per-course enrollment status
    await class_members_collection.update_one(
        {"class_id": request.class_id, "user_id": student_id},
        {"$set": {
            "stylometry_enrolled": True,
            "stylometry_profile_strength": enroll_result.get("profile_strength", "fair"),
            "stylometry_samples_count": enroll_result.get("total_course_samples", len(request.samples)),
            "stylometry_enrolled_at": datetime.now(timezone.utc),
        }},
    )

    # Update global user profile with V3 enrollment data
    # Counts total courses enrolled across all classes
    total_courses = await class_members_collection.count_documents({
        "user_id": student_id,
        "stylometry_enrolled": True,
    })
    if users_collection is not None:
        await users_collection.update_one(
            {"user_id": student_id},
            {"$set": {
                "stylometry_enrolled": True,
                "stylometry_version": "v3",
                "stylometry_courses_enrolled": total_courses,
                "stylometry_last_enrolled_class": request.class_id,
                "stylometry_last_updated": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }},
        )
    # Update session so frontend reflects enrollment immediately
    if sessions_collection is not None:
        await sessions_collection.update_many(
            {"user.user_id": student_id},
            {"$set": {
                "user.stylometry_enrolled": True,
                "user.stylometry_courses_enrolled": total_courses,
            }},
        )

    # Mark the enrollment assignment as submitted (if it exists)
    class_doc = await classes_collection.find_one({"class_id": request.class_id})
    enrollment_assignment_id = class_doc.get("stylometry_enrollment_assignment_id") if class_doc else None
    if enrollment_assignment_id and submissions_collection is not None:
        existing_sub = await submissions_collection.find_one({
            "assignment_id": enrollment_assignment_id,
            "student_id": student_id,
        })
        if not existing_sub:
            import uuid
            await submissions_collection.insert_one({
                "submission_id": str(uuid.uuid4()),
                "assignment_id": enrollment_assignment_id,
                "class_id": request.class_id,
                "student_id": student_id,
                "content": "\n\n---\n\n".join(request.samples),
                "word_count": sum(len(s.split()) for s in request.samples),
                "status": "submitted",
                "submitted_at": datetime.now(timezone.utc),
                "trust_score": 100,
                "content_mix": {"typed": 1.0, "internal": 0, "external": 0},
                "integrity_flags": [],
                "face_verification_log": [],
                "plagiarism_score": 0,
                "plagiarism_matches": [],
                "ai_probability": 0,
                "stylometry_enrollment": True,
                "ai_check_details": ai_check["details"],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })

    return {
        "success": True,
        "student_id": student_id,
        "class_id": request.class_id,
        "status": enroll_result.get("status", "enrolled"),
        "profile_strength": enroll_result.get("profile_strength"),
        "samples_enrolled": enroll_result.get("samples_enrolled"),
        "total_course_samples": enroll_result.get("total_course_samples"),
        "recommendation": enroll_result.get("recommendation"),
        "ai_check": ai_check["details"],
    }


# ============================================================================
# ENDPOINT 2: Verify a submission against per-course profile
# ============================================================================
@router.post("/verify")
async def verify_submission(
    request: StylometryV3VerifyRequest,
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
):
    """
    Verify a student's submission against their per-course writing profile.
    Called on every assignment submission.
    """
    resolved_token = _extract_token(token, authorization)
    user = await _get_user(resolved_token)

    student_id = user["user_id"]

    # Check per-course enrollment
    membership = await class_members_collection.find_one({
        "class_id": request.class_id,
        "user_id": student_id,
    })
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this class")
    if not membership.get("stylometry_enrolled"):
        raise HTTPException(
            status_code=400,
            detail="Stylometry enrollment required for this course. Complete the Writing Profile Assessment first."
        )

    # Safety: strip HTML tags to ensure forensicstylo receives plain text.
    # The frontend sends getText(), but direct API callers might send HTML.
    _plain_text = request.submission_text
    if '<' in _plain_text and '>' in _plain_text:
        from ..services.auto_grading import strip_html_tags
        _plain_text = strip_html_tags(_plain_text)

    try:
        from ..utils.http_client import get_client
        client = get_client()
        response = await client.post(
            f"{STYLOMETRY_V3_BASE}/course/verify",
            json={
                "student_id": student_id,
                "class_id": request.class_id,
                "submission_text": _plain_text,
            },
            timeout=120,
        )
        if response.status_code in (400, 404, 422):
            # Pass through forensicstylo's error detail (e.g. "Student not found", validation errors)
            try:
                error_data = response.json()
            except Exception:
                error_data = {"detail": response.text}
            raise HTTPException(status_code=response.status_code, detail=error_data.get("detail", "Verification failed"))
        response.raise_for_status()
        verify_result = response.json()
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        logger.error(f"Stylometry V3 verify failed: {e}")
        raise HTTPException(status_code=502, detail=f"Stylometry service error: {str(e)}")

    # Update profile strength on class_members (flywheel updates)
    if verify_result.get("profile_absorbed"):
        await class_members_collection.update_one(
            {"class_id": request.class_id, "user_id": student_id},
            {"$set": {
                "stylometry_profile_strength": verify_result.get("profile_strength"),
                "stylometry_samples_count": verify_result.get("n_profile_essays", 0),
            }},
        )

    # Update global user doc with latest verification result
    if users_collection is not None:
        await users_collection.update_one(
            {"user_id": student_id},
            {"$set": {
                "stylometry_last_verdict": verify_result.get("verdict"),
                "stylometry_last_score": verify_result.get("probability"),
                "stylometry_last_cosine": verify_result.get("cosine_score"),
                "stylometry_last_class": request.class_id,
                "stylometry_last_verified_at": datetime.now(timezone.utc),
            }},
        )

    return {
        "success": True,
        **verify_result,
    }


# ============================================================================
# ENDPOINT 3: Get student's per-course profile status
# ============================================================================
@router.get("/profile/{student_id}")
async def get_course_profile(
    student_id: str,
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Get a student's stylometry enrollment status: global summary + per-course details."""
    resolved_token = _extract_token(token, authorization)
    await _get_user(resolved_token)

    # Fetch per-course data from the external V3 API
    external_data = {"courses": [], "total_courses": 0}
    try:
        from ..utils.http_client import get_client
        client = get_client()
        response = await client.get(
            f"{STYLOMETRY_V3_BASE}/course/profile/{student_id}",
            timeout=30,
        )
        if response.status_code == 200:
            external_data = response.json()
    except Exception as e:
        logger.warning(f"External V3 profile fetch failed: {e}")

    # Fetch global user data from our DB
    global_data = {}
    if users_collection is not None:
        user_doc = await users_collection.find_one(
            {"user_id": student_id},
            {
                "stylometry_enrolled": 1, "stylometry_version": 1,
                "stylometry_courses_enrolled": 1, "stylometry_last_verdict": 1,
                "stylometry_last_score": 1, "stylometry_last_cosine": 1,
                "stylometry_last_class": 1, "stylometry_last_verified_at": 1,
                "stylometry_last_updated": 1, "_id": 0,
            },
        )
        if user_doc:
            global_data = {k: v for k, v in user_doc.items() if v is not None}

    # Fetch local per-course enrollment data from class_members
    local_courses = []
    if class_members_collection is not None:
        memberships = await class_members_collection.find(
            {"user_id": student_id, "stylometry_enrolled": True},
            {"class_id": 1, "stylometry_profile_strength": 1, "stylometry_samples_count": 1,
             "stylometry_enrolled_at": 1, "_id": 0},
        ).to_list(length=50)
        local_courses = memberships

    return {
        "student_id": student_id,
        "global": global_data,
        "courses": external_data.get("courses", []),
        "local_courses": local_courses,
        "total_courses": external_data.get("total_courses", len(local_courses)),
        "recommendation": external_data.get("recommendation", ""),
    }


# ============================================================================
# ENDPOINT 4: Check enrollment status for a specific course (lightweight)
# ============================================================================
@router.get("/course-status/{class_id}")
async def get_course_enrollment_status(
    class_id: str,
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Check if current student is enrolled for a specific course."""
    resolved_token = _extract_token(token, authorization)
    user = await _get_user(resolved_token)

    membership = await class_members_collection.find_one({
        "class_id": class_id,
        "user_id": user["user_id"],
    })
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this class")

    # Also get the enrollment assignment ID
    class_doc = await classes_collection.find_one({"class_id": class_id})
    enrollment_assignment_id = class_doc.get("stylometry_enrollment_assignment_id") if class_doc else None

    return {
        "class_id": class_id,
        "enrolled": membership.get("stylometry_enrolled", False),
        "profile_strength": membership.get("stylometry_profile_strength"),
        "samples_count": membership.get("stylometry_samples_count", 0),
        "enrolled_at": membership.get("stylometry_enrolled_at"),
        "enrollment_assignment_id": enrollment_assignment_id,
    }


# ============================================================================
# ENDPOINT 5: Generate writing prompts for a course (OpenAI)
# ============================================================================
@router.post("/generate-prompts")
async def generate_enrollment_prompts(
    class_id: str = Query(...),
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Generate 3 writing prompts for stylometry enrollment using OpenAI."""
    resolved_token = _extract_token(token, authorization)
    user = await _get_user(resolved_token)

    class_doc = await classes_collection.find_one({"class_id": class_id})
    if not class_doc:
        raise HTTPException(status_code=404, detail="Class not found")

    course_name = class_doc.get("name", "")
    course_subject = class_doc.get("subject", "")
    course_description = class_doc.get("description", "")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # Fallback: generic prompts
        return {
            "prompts": [
                f"Write about a topic in {course_subject} that interests you and explain why it matters. Share your personal perspective and analysis.",
                f"Describe a concept or idea from {course_subject} that you find challenging. How do you approach understanding it?",
                f"Reflect on something you've learned about {course_subject} recently. How has it changed your thinking?",
            ],
            "source": "fallback",
        }

    prompt = f"""Generate exactly 3 writing prompts for a university-level course.

Course Name: {course_name}
Subject: {course_subject}
Description: {course_description or 'N/A'}

Requirements:
- Each prompt should elicit 400-500 words of analytical/reflective writing
- Prompts must be open-ended opinion/analysis questions with no single correct answer
- Every student's response should be unique to their perspective
- Prompts should relate to the course subject
- Output ONLY a JSON array of 3 strings, nothing else

Example output format:
["Prompt 1 text here...", "Prompt 2 text here...", "Prompt 3 text here..."]"""

    try:
        from ..utils.http_client import get_client
        client = get_client()
        import json
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 1000,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        content = json.loads(result["choices"][0]["message"]["content"])
        prompts = content if isinstance(content, list) else content.get("prompts", [])
        if len(prompts) < 3:
            raise ValueError("Less than 3 prompts generated")
        return {"prompts": prompts[:3], "source": "openai"}
    except Exception as e:
        logger.warning(f"OpenAI prompt generation failed, using fallback: {e}")
        return {
            "prompts": [
                f"Write about a topic in {course_subject} that interests you and explain why it matters. Share your personal perspective and analysis.",
                f"Describe a concept or idea from {course_subject} that you find challenging. How do you approach understanding it?",
                f"Reflect on something you've learned about {course_subject} recently. How has it changed your thinking?",
            ],
            "source": "fallback",
        }
