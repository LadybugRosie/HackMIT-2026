"""
Assignments Router - Assignment Management for Teachers
"""
from fastapi import APIRouter, HTTPException, Query, Header
from typing import Optional, List
from datetime import datetime, timezone
import uuid

from ..models import (
    AssignmentCreate, AssignmentUpdate, AssignmentSettings,
    AssignmentResponse, RubricCriteria
)
from ..services.integrity_visibility import legacy_mode, effective_ai_probability

router = APIRouter(prefix="/api/assignments", tags=["Assignments"])

# MongoDB collection references (set by main.py)
assignments_collection = None
classes_collection = None
class_members_collection = None
submissions_collection = None
users_collection = None

def set_collections(assignments, classes, members, submissions, users):
    """Set MongoDB collection references"""
    global assignments_collection, classes_collection, class_members_collection
    global submissions_collection, users_collection
    assignments_collection = assignments
    classes_collection = classes
    class_members_collection = members
    submissions_collection = submissions
    users_collection = users


def _extract_token(token: Optional[str] = None, authorization: Optional[str] = Header(None)) -> str:
    """Extract token from Authorization header or query param."""
    if authorization and authorization.startswith('Bearer '):
        return authorization[7:]
    if authorization:
        return authorization
    if token:
        return token
    raise HTTPException(status_code=401, detail="Authentication required")


async def get_user_from_token(token: str):
    """Get user from session token"""
    from .auth import get_current_user
    return await get_current_user(token)


async def verify_teacher(token: str):
    """Verify user is a teacher (FIX #22: re-reads role from DB)"""
    user = await get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # FIX #22: Refresh role from DB to prevent stale permissions
    if users_collection is not None and user.get("user_id"):
        db_user = await users_collection.find_one({"user_id": user["user_id"]})
        if db_user:
            user["role"] = db_user.get("role", user.get("role", "student"))
    if user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can perform this action")
    return user


async def verify_class_teacher(user: dict, class_id: str):
    """Verify user is the teacher of this class"""
    class_doc = await classes_collection.find_one({"class_id": class_id})
    if not class_doc:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if class_doc["teacher_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="You are not the teacher of this class")
    
    return class_doc


async def verify_class_member(user: dict, class_id: str):
    """Verify user is a member of this class"""
    membership = await class_members_collection.find_one({
        "class_id": class_id,
        "user_id": user["user_id"]
    })
    
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this class")
    
    return membership


# ============================================================================
# ASSIGNMENT CRUD
# ============================================================================

@router.post("", response_model=AssignmentResponse)
async def create_assignment(request: AssignmentCreate, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Create a new assignment (teacher only)"""
    user = await verify_teacher(_extract_token(token, authorization))
    class_doc = await verify_class_teacher(user, request.class_id)
    
    # Validate rubric if provided (warn but don't block)
    rubric_warning = None
    if request.rubric:
        total_rubric_points = sum(c.points for c in request.rubric)
        if total_rubric_points != request.points:
            rubric_warning = f"Note: Rubric points ({total_rubric_points}) differ from assignment points ({request.points})"
    
    # Create assignment document
    assignment_doc = {
        "assignment_id": str(uuid.uuid4()),
        "class_id": request.class_id,
        "teacher_id": user["user_id"],
        "title": request.title.strip(),
        "instructions": request.instructions.strip(),
        "due_date": request.due_date,
        "points": request.points,
        "settings": request.settings.model_dump(),
        "rubric": [r.model_dump() for r in request.rubric] if request.rubric else None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "published": False
    }
    
    await assignments_collection.insert_one(assignment_doc)
    
    return AssignmentResponse(
        assignment_id=assignment_doc["assignment_id"],
        class_id=assignment_doc["class_id"],
        class_name=class_doc["name"],
        teacher_id=assignment_doc["teacher_id"],
        title=assignment_doc["title"],
        instructions=assignment_doc["instructions"],
        due_date=assignment_doc["due_date"],
        points=assignment_doc["points"],
        settings=AssignmentSettings(**assignment_doc["settings"]),
        rubric=[RubricCriteria(**r) for r in assignment_doc["rubric"]] if assignment_doc["rubric"] else None,
        created_at=assignment_doc["created_at"],
        published=assignment_doc["published"],
        submission_count=0,
        graded_count=0
    )


@router.get("", response_model=List[AssignmentResponse])
async def list_assignments(
    token: str = Query(None),
    class_id: Optional[str] = Query(None),
    published_only: bool = Query(False),
    authorization: Optional[str] = Header(None)
):
    """List assignments for a class or all classes the user is in"""
    user = await get_user_from_token(_extract_token(token, authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Build query
    query = {}
    
    if class_id:
        # Verify membership
        await verify_class_member(user, class_id)
        query["class_id"] = class_id
    else:
        # Get all classes the user is in
        memberships = await class_members_collection.find(
            {"user_id": user["user_id"]}
        ).to_list(length=100)
        class_ids = [m["class_id"] for m in memberships]
        
        if not class_ids:
            return []
        
        query["class_id"] = {"$in": class_ids}
    
    # Students/researchers only see published assignments
    if user.get("role") in ("student", "researcher") or published_only:
        query["published"] = True

    assignments = await assignments_collection.find(query).sort("due_date", 1).to_list(length=200)

    result = []
    is_student = user.get("role") in ("student", "researcher") or not user.get("role")

    # Batch-fetch class names in one query instead of N+1
    assignment_class_ids = list({a["class_id"] for a in assignments})
    class_docs = await classes_collection.find(
        {"class_id": {"$in": assignment_class_ids}}
    ).to_list(length=len(assignment_class_ids))
    class_lookup = {c["class_id"]: c["name"] for c in class_docs}

    # Batch-fetch submission & graded counts via aggregation instead of 2N count queries
    assignment_ids = [a["assignment_id"] for a in assignments]
    submission_counts = {}
    graded_counts = {}
    if submissions_collection is not None and assignment_ids:
        async for doc in submissions_collection.aggregate([
            {"$match": {
                "assignment_id": {"$in": assignment_ids},
                "status": {"$in": ["submitted", "graded", "returned"]}
            }},
            {"$group": {
                "_id": "$assignment_id",
                "total": {"$sum": 1},
                "graded": {"$sum": {"$cond": [
                    {"$in": ["$status", ["graded", "returned"]]}, 1, 0
                ]}}
            }}
        ]):
            submission_counts[doc["_id"]] = doc["total"]
            graded_counts[doc["_id"]] = doc["graded"]

    # For students: batch-fetch their submissions in one query
    student_submissions = {}
    if is_student and submissions_collection is not None and assignment_ids:
        student_subs = await submissions_collection.find({
            "assignment_id": {"$in": assignment_ids},
            "student_id": user["user_id"]
        }).to_list(length=len(assignment_ids))
        student_submissions = {s["assignment_id"]: s for s in student_subs}

    for assignment in assignments:
        class_name = class_lookup.get(assignment["class_id"], "Unknown")
        submission_count = submission_counts.get(assignment["assignment_id"], 0)
        graded_count = graded_counts.get(assignment["assignment_id"], 0)

        response_data = {
            "assignment_id": assignment["assignment_id"],
            "class_id": assignment["class_id"],
            "class_name": class_name,
            "teacher_id": assignment["teacher_id"],
            "title": assignment["title"],
            "instructions": assignment["instructions"],
            "due_date": assignment["due_date"],
            "points": assignment["points"],
            "settings": assignment["settings"],
            "rubric": assignment.get("rubric"),
            "created_at": assignment["created_at"],
            "published": assignment["published"],
            "submission_count": submission_count,
            "graded_count": graded_count,
            "type": assignment.get("type", "regular"),
            "stylometry_prompts": assignment.get("stylometry_prompts"),
        }

        # For students: enrich with their own submission data
        if is_student:
            my_sub = student_submissions.get(assignment["assignment_id"])
            if my_sub:
                response_data["status"] = my_sub.get("status", "draft")
                response_data["submitted"] = my_sub.get("status") in ("submitted", "graded", "returned")
                response_data["grade"] = my_sub.get("grade")
                response_data["graded_at"] = my_sub.get("graded_at")
                # Students see no integrity unless the legacy production switch is on.
                if legacy_mode():
                    response_data["trust_score"] = my_sub.get("trust_score")
                response_data["submission_id"] = my_sub.get("submission_id")
            else:
                response_data["status"] = None
                response_data["submitted"] = False
                response_data["grade"] = None
                response_data["graded_at"] = None
        
        result.append(response_data)
    
    return result


@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(assignment_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Get assignment details"""
    user = await get_user_from_token(_extract_token(token, authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    assignment = await assignments_collection.find_one({"assignment_id": assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Verify membership
    await verify_class_member(user, assignment["class_id"])
    
    # Students/researchers can only see published assignments
    if user.get("role") in ("student", "researcher") and not assignment["published"]:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Get class name
    class_doc = await classes_collection.find_one({"class_id": assignment["class_id"]})
    class_name = class_doc["name"] if class_doc else "Unknown"
    
    # Count submissions
    submission_count = 0
    graded_count = 0
    if submissions_collection is not None:
        submission_count = await submissions_collection.count_documents({
            "assignment_id": assignment_id,
            "status": {"$in": ["submitted", "graded", "returned"]}
        })
        graded_count = await submissions_collection.count_documents({
            "assignment_id": assignment_id,
            "status": {"$in": ["graded", "returned"]}
        })
    
    return AssignmentResponse(
        assignment_id=assignment["assignment_id"],
        class_id=assignment["class_id"],
        class_name=class_name,
        teacher_id=assignment["teacher_id"],
        title=assignment["title"],
        instructions=assignment["instructions"],
        due_date=assignment["due_date"],
        points=assignment["points"],
        settings=AssignmentSettings(**assignment["settings"]),
        rubric=[RubricCriteria(**r) for r in assignment["rubric"]] if assignment.get("rubric") else None,
        created_at=assignment["created_at"],
        published=assignment["published"],
        submission_count=submission_count,
        graded_count=graded_count
    )


@router.put("/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    assignment_id: str,
    request: AssignmentUpdate,
    token: str = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Update an assignment (teacher only)"""
    user = await verify_teacher(_extract_token(token, authorization))
    
    assignment = await assignments_collection.find_one({"assignment_id": assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    class_doc = await verify_class_teacher(user, assignment["class_id"])
    
    # Build update document
    update_doc = {"updated_at": datetime.now(timezone.utc)}
    
    if request.title is not None:
        update_doc["title"] = request.title.strip()
    if request.instructions is not None:
        update_doc["instructions"] = request.instructions.strip()
    if request.due_date is not None:
        update_doc["due_date"] = request.due_date
    if request.points is not None:
        update_doc["points"] = request.points
    if request.settings is not None:
        update_doc["settings"] = request.settings.model_dump()
    if request.rubric is not None:
        update_doc["rubric"] = [r.model_dump() for r in request.rubric]
    
    await assignments_collection.update_one(
        {"assignment_id": assignment_id},
        {"$set": update_doc}
    )
    
    # Get updated assignment
    updated = await assignments_collection.find_one({"assignment_id": assignment_id})
    
    submission_count = 0
    graded_count = 0
    if submissions_collection is not None:
        submission_count = await submissions_collection.count_documents({
            "assignment_id": assignment_id,
            "status": {"$in": ["submitted", "graded", "returned"]}
        })
        graded_count = await submissions_collection.count_documents({
            "assignment_id": assignment_id,
            "status": {"$in": ["graded", "returned"]}
        })
    
    return AssignmentResponse(
        assignment_id=updated["assignment_id"],
        class_id=updated["class_id"],
        class_name=class_doc["name"],
        teacher_id=updated["teacher_id"],
        title=updated["title"],
        instructions=updated["instructions"],
        due_date=updated["due_date"],
        points=updated["points"],
        settings=AssignmentSettings(**updated["settings"]),
        rubric=[RubricCriteria(**r) for r in updated["rubric"]] if updated.get("rubric") else None,
        created_at=updated["created_at"],
        published=updated["published"],
        submission_count=submission_count,
        graded_count=graded_count
    )


@router.delete("/{assignment_id}")
async def delete_assignment(assignment_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Delete an assignment (teacher only)"""
    user = await verify_teacher(_extract_token(token, authorization))
    
    assignment = await assignments_collection.find_one({"assignment_id": assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    if assignment.get("type") == "stylometry_enrollment":
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the Writing Profile Assessment. It is required for stylometry verification."
        )
    
    await verify_class_teacher(user, assignment["class_id"])
    
    # Check if there are submissions
    if submissions_collection is not None:
        submission_count = await submissions_collection.count_documents({
            "assignment_id": assignment_id
        })
        if submission_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete assignment with {submission_count} submissions. Archive it instead."
            )
    
    await assignments_collection.delete_one({"assignment_id": assignment_id})
    
    return {"success": True, "message": "Assignment deleted"}


# ============================================================================
# ASSIGNMENT PUBLISHING
# ============================================================================

@router.post("/{assignment_id}/publish")
async def publish_assignment(assignment_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Publish an assignment to students (teacher only)"""
    user = await verify_teacher(_extract_token(token, authorization))
    
    assignment = await assignments_collection.find_one({"assignment_id": assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    await verify_class_teacher(user, assignment["class_id"])
    
    await assignments_collection.update_one(
        {"assignment_id": assignment_id},
        {"$set": {"published": True, "published_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"success": True, "message": "Assignment published"}


@router.post("/{assignment_id}/unpublish")
async def unpublish_assignment(assignment_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Unpublish an assignment (teacher only)"""
    user = await verify_teacher(_extract_token(token, authorization))
    
    assignment = await assignments_collection.find_one({"assignment_id": assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    await verify_class_teacher(user, assignment["class_id"])
    
    # Check if there are submissions
    if submissions_collection is not None:
        submission_count = await submissions_collection.count_documents({
            "assignment_id": assignment_id,
            "status": {"$ne": "draft"}
        })
        if submission_count > 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot unpublish assignment with existing submissions"
            )
    
    await assignments_collection.update_one(
        {"assignment_id": assignment_id},
        {"$set": {"published": False, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"success": True, "message": "Assignment unpublished"}


# ============================================================================
# AI RUBRIC PARSING
# ============================================================================

@router.post("/parse-rubric-ai")
async def parse_rubric_with_ai(token: str = Query(None), total_points: int = Query(100), authorization: Optional[str] = Header(None)):
    """Parse rubric from file content using AI (teacher only)"""
    from fastapi import Request
    import json
    
    user = await verify_teacher(_extract_token(token, authorization))
    
    # Read raw body as the file content text
    # This endpoint receives JSON body with file_content field
    return {"error": "Use the /parse-rubric-ai-content endpoint"}


from pydantic import BaseModel as PydanticBaseModel

class RubricParseRequest(PydanticBaseModel):
    file_content: str
    file_name: Optional[str] = "file.txt"
    total_points: int = 100


@router.post("/parse-rubric-ai-content")
async def parse_rubric_ai_content(request: RubricParseRequest, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Parse rubric from text/file content using AI (teacher only)"""
    user = await verify_teacher(_extract_token(token, authorization))
    
    import os, json, httpx
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    content = request.file_content[:10000]  # Limit input
    
    prompt = f"""You are an expert at extracting grading rubrics from documents. 
Parse the following content and extract a structured grading rubric.

The rubric should total approximately {request.total_points} points.

Content to parse:
---
{content}
---

Extract the rubric criteria and return as JSON with this exact structure:
{{
    "rubric": [
        {{
            "name": "Criterion Name",
            "description": "What this criterion evaluates",
            "points": <max points for this criterion>,
            "levels": [
                {{ "name": "Excellent", "points": <points>, "description": "Description of excellent work" }},
                {{ "name": "Good", "points": <points>, "description": "Description of good work" }},
                {{ "name": "Satisfactory", "points": <points>, "description": "Description of satisfactory work" }},
                {{ "name": "Needs Improvement", "points": <points>, "description": "Description of poor work" }}
            ]
        }}
    ]
}}

Rules:
- If the text contains clear rubric criteria, extract them faithfully
- If the text is a general description/prompt, generate an appropriate rubric for grading it
- Always include 3-6 criteria covering all important aspects
- Each criterion should have 3-5 scoring levels from highest to lowest
- The total of all criteria max points should equal approximately {request.total_points}
- Level points should decrease from the max down to a minimum"""

    try:
        from ..utils.http_client import get_client
        client = get_client()
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
                "response_format": {"type": "json_object"}
            }
        )
        response.raise_for_status()
        result = response.json()
        ai_response = json.loads(result["choices"][0]["message"]["content"])

        rubric = ai_response.get("rubric", [])

        import uuid as _uuid
        for criterion in rubric:
            criterion["criteria_id"] = str(_uuid.uuid4())

        return {
            "success": True,
            "rubric": rubric,
            "criteria_count": len(rubric),
            "total_points": sum(c.get("points", 0) for c in rubric)
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=500, detail=f"AI parsing failed: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rubric parsing failed: {str(e)}")


# ============================================================================
# STUDENT-SPECIFIC ENDPOINTS
# ============================================================================

@router.get("/{assignment_id}/my-submission")
async def get_my_submission(assignment_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Get current user's submission for this assignment (students)"""
    user = await get_user_from_token(_extract_token(token, authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    assignment = await assignments_collection.find_one({"assignment_id": assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    await verify_class_member(user, assignment["class_id"])
    
    if submissions_collection is None:
        return {"submission": None}
    
    submission = await submissions_collection.find_one({
        "assignment_id": assignment_id,
        "student_id": user["user_id"]
    })
    
    if not submission:
        return {"submission": None}
    
    sub_payload = {
        "submission_id": submission["submission_id"],
        "status": submission["status"],
        "content": submission.get("content", ""),
        "content_html": submission.get("content_html", ""),
        "submitted_at": submission.get("submitted_at"),
        "grade": submission.get("grade"),
        "feedback": submission.get("feedback"),
        "graded_at": submission.get("graded_at"),
        "grade_breakdown": submission.get("grade_breakdown"),
        "updated_at": submission.get("updated_at")
    }
    # Students see no integrity (no trust/report) unless legacy switch is on.
    if legacy_mode():
        sub_payload["trust_score"] = submission.get("trust_score")
        sub_payload["has_report"] = submission.get("status") in ("submitted", "graded", "returned")
    return {"submission": sub_payload}


@router.get("/{assignment_id}/submissions")
async def list_assignment_submissions(
    assignment_id: str,
    token: str = Query(None),
    status: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    """List all submissions for an assignment (teacher only)"""
    user = await verify_teacher(_extract_token(token, authorization))
    
    assignment = await assignments_collection.find_one({"assignment_id": assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    await verify_class_teacher(user, assignment["class_id"])
    
    if submissions_collection is None:
        return {"submissions": [], "total": 0}
    
    # Build query
    query = {"assignment_id": assignment_id}
    if status:
        query["status"] = status
    
    submissions = await submissions_collection.find(query).to_list(length=500)

    # Batch-fetch all student info in one query instead of N+1
    student_ids = list({sub["student_id"] for sub in submissions})
    student_docs = await users_collection.find(
        {"user_id": {"$in": student_ids}}
    ).to_list(length=len(student_ids))
    student_lookup = {s["user_id"]: s["name"] for s in student_docs}

    result = []
    for sub in submissions:
        student_name = student_lookup.get(sub["student_id"], "Unknown")

        row = {
            "submission_id": sub["submission_id"],
            "student_id": sub["student_id"],
            "student_name": student_name,
            "status": sub["status"],
            "trust_score": sub.get("trust_score", 0),
            "plagiarism_score": sub.get("plagiarism_score", 0),
            # AI probability lives under ai_detection; None means "not run".
            "ai_probability": effective_ai_probability(sub.get("ai_detection")),
            "stylometry_verdict": (sub.get("stylometry_v3") or sub.get("stylometry") or {}).get("verdict"),
            "stylometry_cosine": (sub.get("stylometry_v3") or {}).get("cosine_score"),
            "similarity_pending": sub.get("plagiarism_v2_checked_at") is None,
            "word_count": sub.get("word_count", 0),
            "submitted_at": sub.get("submitted_at"),
            "grade": sub.get("grade"),
            "graded_at": sub.get("graded_at"),
            "flags": sub.get("integrity_flags", [])
        }
        result.append(row)
    
    # Sort by status (submitted first), then by name
    status_order = {"submitted": 0, "draft": 1, "graded": 2, "returned": 3}
    result.sort(key=lambda x: (status_order.get(x["status"], 99), x["student_name"].lower()))
    
    return {"submissions": result, "total": len(result)}
