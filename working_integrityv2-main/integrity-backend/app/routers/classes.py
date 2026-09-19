"""
Classes Router - Class Management for Teachers and Students
"""
from fastapi import APIRouter, HTTPException, Query, Header
from typing import Optional, List
from datetime import datetime, timezone
import secrets
import string

from ..models import (
    ClassCreate, ClassUpdate, ClassJoin, ClassSettings, ClassResponse
)

router = APIRouter(prefix="/api/classes", tags=["Classes"])

# MongoDB collection references (set by main.py)
classes_collection = None
class_members_collection = None
users_collection = None
assignments_collection = None
submissions_collection = None

def set_collections(classes, members, users, assignments, submissions=None):
    """Set MongoDB collection references"""
    global classes_collection, class_members_collection, users_collection, assignments_collection, submissions_collection
    classes_collection = classes
    class_members_collection = members
    users_collection = users
    assignments_collection = assignments
    submissions_collection = submissions


def generate_class_code(length: int = 6) -> str:
    """Generate a unique class join code"""
    chars = string.ascii_uppercase + string.digits
    # Remove ambiguous characters
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '').replace('L', '')
    return ''.join(secrets.choice(chars) for _ in range(length))


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


async def verify_class_teacher(token: str, class_id: str):
    """Verify user is the teacher of this class"""
    user = await verify_teacher(token)
    
    class_doc = await classes_collection.find_one({"class_id": class_id})
    if not class_doc:
        raise HTTPException(status_code=404, detail="Class not found")
    
    if class_doc["teacher_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="You are not the teacher of this class")
    
    return user, class_doc


# ============================================================================
# STYLOMETRY ENROLLMENT ASSIGNMENT AUTO-CREATION
# ============================================================================

async def _generate_enrollment_prompts(course_name: str, subject: str, description: str) -> list:
    """Generate 3 writing prompts via OpenAI, with a generic fallback."""
    import os, json
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return [
            f"Write about a topic in {subject} that interests you and explain why it matters.",
            f"Describe a concept or idea from {subject} that you find challenging and how you approach it.",
            f"Reflect on something you've learned about {subject} recently and how it changed your thinking.",
        ]
    try:
        from ..utils.http_client import get_client
        client = get_client()
        prompt = (
            f"Generate exactly 3 SIMPLE, EASY writing prompts for a university course.\n"
            f"Course: {course_name}\nSubject: {subject}\nDescription: {description or 'N/A'}\n\n"
            f"Requirements:\n"
            f"- Prompts should be EASY and approachable — no technical jargon or complex analysis.\n"
            f"- Ask about personal opinions, experiences, or reflections related to the subject.\n"
            f"- Each prompt should elicit 400-500 words of natural writing.\n"
            f"- Open-ended questions with no single correct answer.\n"
            f"- Examples: 'What interests you most about [subject]?', 'Describe a time when...'\n"
            f"Return ONLY a JSON object like {{\"prompts\": [\"...\",\"...\",\"...\"]}}."
        )
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 800,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = json.loads(resp.json()["choices"][0]["message"]["content"])
        prompts = data if isinstance(data, list) else data.get("prompts", [])
        if len(prompts) >= 3:
            return prompts[:3]
    except Exception:
        pass
    return [
        f"Write about a topic in {subject} that interests you and explain why it matters.",
        f"Describe a concept or idea from {subject} that you find challenging and how you approach it.",
        f"Reflect on something you've learned about {subject} recently and how it changed your thinking.",
    ]


async def _create_stylometry_enrollment_assignment(class_doc: dict, teacher: dict) -> str:
    """Create the auto-generated stylometry enrollment assignment for a class.
    Returns the assignment_id or None on failure."""
    import uuid as _uuid
    from datetime import timedelta

    prompts = await _generate_enrollment_prompts(
        class_doc["name"],
        class_doc["subject"],
        class_doc.get("description", ""),
    )
    instructions = (
        "WRITING PROFILE ASSESSMENT — EXAM CONDITIONS\n\n"
        "This assessment builds your unique writing fingerprint for authorship verification. "
        "It is widely encouraged to complete this under exam conditions.\n\n"
        "RULES:\n"
        "• Write in your own words — no AI tools, no copy-pasting.\n"
        "• Treat this as a supervised exam.\n"
        "• Respond to each of the 3 prompts below with at least 400 words each.\n"
        "• Your typing patterns are being monitored.\n\n"
        f"PROMPT 1:\n{prompts[0]}\n\n"
        f"PROMPT 2:\n{prompts[1]}\n\n"
        f"PROMPT 3:\n{prompts[2]}\n\n"
        "NOTE TO INSTRUCTOR: You may review and edit these prompts. "
        "It is recommended to have students complete this assessment in a supervised exam environment."
    )

    assignment_id = str(_uuid.uuid4())
    assignment_doc = {
        "assignment_id": assignment_id,
        "class_id": class_doc["class_id"],
        "teacher_id": teacher["user_id"],
        "title": "Writing Profile Assessment",
        "instructions": instructions,
        "due_date": datetime.now(timezone.utc) + timedelta(days=365),
        "points": 0,
        "settings": {
            "face_verification_enabled": False,
            "face_check_interval": 600000,
            "face_max_warnings": 3,
            "strict_mode": True,
            "minimum_trust_score": 0,
            "allow_late": True,
            "late_penalty_percent": 0,
            "max_attempts": 1,
            "check_plagiarism": False,
            "plagiarism_threshold": 40,
            "auto_grade_enabled": False,
            "education_level": "university",
        },
        "rubric": None,
        "type": "stylometry_enrollment",
        "stylometry_prompts": prompts,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "published": True,
        "published_at": datetime.now(timezone.utc),
    }

    if assignments_collection is not None:
        await assignments_collection.insert_one(assignment_doc)
        return assignment_id
    return None


# ============================================================================
# CLASS CRUD OPERATIONS
# ============================================================================

@router.post("", response_model=ClassResponse)
async def create_class(request: ClassCreate, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Create a new class (teachers only)"""
    user = await verify_teacher(_extract_token(token, authorization))
    
    # Generate unique class code
    class_code = generate_class_code()
    while await classes_collection.find_one({"class_code": class_code}):
        class_code = generate_class_code()
    
    # Create class document
    import uuid
    class_doc = {
        "class_id": str(uuid.uuid4()),
        "name": request.name.strip(),
        "section": request.section.strip() if request.section else None,
        "subject": request.subject.strip(),
        "description": request.description.strip() if request.description else None,
        "color": request.color or "#1a73e8",
        "class_code": class_code,
        "teacher_id": user["user_id"],
        "teacher_name": user["name"],
        "settings": ClassSettings().model_dump(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "archived": False
    }
    
    await classes_collection.insert_one(class_doc)
    
    # Add teacher as class member
    member_doc = {
        "class_id": class_doc["class_id"],
        "user_id": user["user_id"],
        "role": "teacher",
        "joined_at": datetime.now(timezone.utc)
    }
    await class_members_collection.insert_one(member_doc)
    
    # Auto-create stylometry enrollment assignment for this class
    import logging as _log
    try:
        enrollment_assignment_id = await _create_stylometry_enrollment_assignment(
            class_doc, user
        )
        if enrollment_assignment_id:
            await classes_collection.update_one(
                {"class_id": class_doc["class_id"]},
                {"$set": {"stylometry_enrollment_assignment_id": enrollment_assignment_id}}
            )
    except Exception as e:
        _log.getLogger(__name__).error(f"Failed to create enrollment assignment: {e}")
    
    return ClassResponse(
        class_id=class_doc["class_id"],
        name=class_doc["name"],
        section=class_doc["section"],
        subject=class_doc["subject"],
        description=class_doc["description"],
        color=class_doc["color"],
        class_code=class_doc["class_code"],
        teacher_id=class_doc["teacher_id"],
        teacher_name=class_doc["teacher_name"],
        student_count=0,
        assignment_count=0,
        created_at=class_doc["created_at"],
        archived=False
    )


@router.get("", response_model=List[ClassResponse])
async def list_classes(
    token: str = Query(None),
    archived: bool = Query(False),
    authorization: Optional[str] = Header(None)
):
    """List all classes for the current user"""
    user = await get_user_from_token(_extract_token(token, authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get all class memberships for this user
    memberships = await class_members_collection.find(
        {"user_id": user["user_id"]}
    ).to_list(length=100)
    
    class_ids = [m["class_id"] for m in memberships]
    
    if not class_ids:
        return []
    
    # Get all classes
    classes = await classes_collection.find({
        "class_id": {"$in": class_ids},
        "archived": archived
    }).to_list(length=100)
    
    # Bulk counts in 2 aggregation queries instead of 2N sequential queries
    student_counts = {}
    async for doc in class_members_collection.aggregate([
        {"$match": {"class_id": {"$in": class_ids}, "role": "student"}},
        {"$group": {"_id": "$class_id", "count": {"$sum": 1}}}
    ]):
        student_counts[doc["_id"]] = doc["count"]

    assignment_counts = {}
    if assignments_collection is not None:
        async for doc in assignments_collection.aggregate([
            {"$match": {"class_id": {"$in": class_ids}}},
            {"$group": {"_id": "$class_id", "count": {"$sum": 1}}}
        ]):
            assignment_counts[doc["_id"]] = doc["count"]

    result = []
    for cls in classes:
        student_count = student_counts.get(cls["class_id"], 0)
        assignment_count = assignment_counts.get(cls["class_id"], 0)

        result.append(ClassResponse(
            class_id=cls["class_id"],
            name=cls["name"],
            section=cls.get("section"),
            subject=cls["subject"],
            description=cls.get("description"),
            color=cls.get("color", "#1a73e8"),
            class_code=cls["class_code"],
            teacher_id=cls["teacher_id"],
            teacher_name=cls.get("teacher_name", "Unknown"),
            student_count=student_count,
            assignment_count=assignment_count,
            created_at=cls["created_at"],
            archived=cls.get("archived", False)
        ))
    
    # Sort by created_at descending
    result.sort(key=lambda x: x.created_at, reverse=True)
    
    return result


@router.get("/dashboard-stats")
async def get_dashboard_stats(token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Get aggregated dashboard statistics for a teacher"""
    user = await verify_teacher(_extract_token(token, authorization))
    
    # Get all classes owned by this teacher
    teacher_classes = await classes_collection.find({
        "teacher_id": user["user_id"],
        "archived": False
    }).to_list(length=200)
    
    class_ids = [cls["class_id"] for cls in teacher_classes]
    
    if not class_ids:
        return {
            "total_students": 0,
            "pending_submissions": 0,
            "average_trust_score": 0,
            "active_classes": 0,
            "flagged_submissions": []
        }
    
    # Total students across all classes
    total_students = await class_members_collection.count_documents({
        "class_id": {"$in": class_ids},
        "role": "student"
    })
    
    # Get all assignments for this teacher's classes
    teacher_assignments = []
    if assignments_collection is not None:
        teacher_assignments = await assignments_collection.find({
            "class_id": {"$in": class_ids}
        }).to_list(length=500)
    
    assignment_ids = [a["assignment_id"] for a in teacher_assignments]
    
    pending_submissions = 0
    average_trust_score = 0
    flagged_submissions = []
    
    if submissions_collection is not None and assignment_ids:
        # Count pending (submitted but not graded) submissions
        pending_submissions = await submissions_collection.count_documents({
            "assignment_id": {"$in": assignment_ids},
            "status": "submitted"
        })
        
        # Calculate average trust score across all submitted/graded submissions
        pipeline = [
            {"$match": {
                "assignment_id": {"$in": assignment_ids},
                "status": {"$in": ["submitted", "graded", "returned"]}
            }},
            {"$group": {
                "_id": None,
                "avg_trust": {"$avg": "$trust_score"},
                "count": {"$sum": 1}
            }}
        ]
        trust_result = await submissions_collection.aggregate(pipeline).to_list(length=1)
        if trust_result and trust_result[0].get("avg_trust") is not None:
            average_trust_score = round(trust_result[0]["avg_trust"])
        
        # Get flagged submissions (low trust or integrity flags)
        flagged_cursor = submissions_collection.find({
            "assignment_id": {"$in": assignment_ids},
            "status": {"$in": ["submitted", "graded"]},
            "$or": [
                {"trust_score": {"$lt": 60}},
                {"integrity_flags": {"$not": {"$size": 0}}}
            ]
        }).sort("submitted_at", -1).limit(10)
        
        flagged_docs = await flagged_cursor.to_list(length=10)
        
        # Build assignment lookup
        assignment_lookup = {a["assignment_id"]: a for a in teacher_assignments}
        
        for doc in flagged_docs:
            assignment = assignment_lookup.get(doc.get("assignment_id"), {})
            trust = doc.get("trust_score", 0)
            flags = doc.get("integrity_flags", [])
            
            alert_type = "trust" if trust < 60 else "flag"
            if any("plagiarism" in str(f).lower() for f in flags):
                alert_type = "plagiarism"
            
            flagged_submissions.append({
                "id": doc.get("submission_id", ""),
                "submissionId": doc.get("submission_id", ""),
                "assignmentId": doc.get("assignment_id", ""),
                "type": alert_type,
                "title": f"Low trust score ({trust}%)" if trust < 60 else "Integrity flag",
                "description": f"{assignment.get('title', 'Unknown')} - {doc.get('student_name', 'Student')}",
            })
    
    return {
        "total_students": total_students,
        "pending_submissions": pending_submissions,
        "average_trust_score": average_trust_score,
        "active_classes": len(teacher_classes),
        "flagged_submissions": flagged_submissions
    }


@router.get("/{class_id}", response_model=ClassResponse)
async def get_class(class_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Get class details"""
    user = await get_user_from_token(_extract_token(token, authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Check if user is a member of this class
    membership = await class_members_collection.find_one({
        "class_id": class_id,
        "user_id": user["user_id"]
    })
    
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this class")
    
    class_doc = await classes_collection.find_one({"class_id": class_id})
    if not class_doc:
        raise HTTPException(status_code=404, detail="Class not found")
    
    # Count students
    student_count = await class_members_collection.count_documents({
        "class_id": class_id,
        "role": "student"
    })
    
    # Count assignments
    assignment_count = 0
    if assignments_collection is not None:
        assignment_count = await assignments_collection.count_documents({
            "class_id": class_id
        })
    
    return ClassResponse(
        class_id=class_doc["class_id"],
        name=class_doc["name"],
        section=class_doc.get("section"),
        subject=class_doc["subject"],
        description=class_doc.get("description"),
        color=class_doc.get("color", "#1a73e8"),
        class_code=class_doc["class_code"],
        teacher_id=class_doc["teacher_id"],
        teacher_name=class_doc.get("teacher_name", "Unknown"),
        student_count=student_count,
        assignment_count=assignment_count,
        created_at=class_doc["created_at"],
        archived=class_doc.get("archived", False)
    )


@router.put("/{class_id}", response_model=ClassResponse)
async def update_class(class_id: str, request: ClassUpdate, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Update class details (teacher only)"""
    user, class_doc = await verify_class_teacher(_extract_token(token, authorization), class_id)
    
    # Build update document
    update_doc = {"updated_at": datetime.now(timezone.utc)}
    
    if request.name is not None:
        update_doc["name"] = request.name.strip()
    if request.section is not None:
        update_doc["section"] = request.section.strip() if request.section else None
    if request.subject is not None:
        update_doc["subject"] = request.subject.strip()
    if request.description is not None:
        update_doc["description"] = request.description.strip() if request.description else None
    if request.color is not None:
        update_doc["color"] = request.color
    
    await classes_collection.update_one(
        {"class_id": class_id},
        {"$set": update_doc}
    )
    
    # Get updated class
    updated_class = await classes_collection.find_one({"class_id": class_id})
    
    student_count = await class_members_collection.count_documents({
        "class_id": class_id,
        "role": "student"
    })
    
    assignment_count = 0
    if assignments_collection is not None:
        assignment_count = await assignments_collection.count_documents({
            "class_id": class_id
        })
    
    return ClassResponse(
        class_id=updated_class["class_id"],
        name=updated_class["name"],
        section=updated_class.get("section"),
        subject=updated_class["subject"],
        description=updated_class.get("description"),
        color=updated_class.get("color", "#1a73e8"),
        class_code=updated_class["class_code"],
        teacher_id=updated_class["teacher_id"],
        teacher_name=updated_class.get("teacher_name", "Unknown"),
        student_count=student_count,
        assignment_count=assignment_count,
        created_at=updated_class["created_at"],
        archived=updated_class.get("archived", False)
    )


@router.put("/{class_id}/archive")
async def archive_class(class_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Archive a class (teacher only)"""
    user, class_doc = await verify_class_teacher(_extract_token(token, authorization), class_id)
    
    await classes_collection.update_one(
        {"class_id": class_id},
        {"$set": {"archived": True, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"success": True, "message": "Class archived"}


@router.put("/{class_id}/unarchive")
async def unarchive_class(class_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Unarchive a class (teacher only)"""
    user, class_doc = await verify_class_teacher(_extract_token(token, authorization), class_id)
    
    await classes_collection.update_one(
        {"class_id": class_id},
        {"$set": {"archived": False, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"success": True, "message": "Class unarchived"}


# ============================================================================
# CLASS MEMBERSHIP
# ============================================================================

@router.post("/join")
async def join_class(request: ClassJoin, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Join a class using class code (students only)"""
    user = await get_user_from_token(_extract_token(token, authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Only students can join classes")
    
    # Find class by code
    class_doc = await classes_collection.find_one({
        "class_code": request.class_code.upper(),
        "archived": False
    })
    
    if not class_doc:
        raise HTTPException(status_code=404, detail="Invalid class code")
    
    # Check if already a member
    existing = await class_members_collection.find_one({
        "class_id": class_doc["class_id"],
        "user_id": user["user_id"]
    })
    
    if existing:
        raise HTTPException(status_code=400, detail="You are already enrolled in this class")
    
    # Add as member
    member_doc = {
        "class_id": class_doc["class_id"],
        "user_id": user["user_id"],
        "user_name": user["name"],
        "user_email": user["email"],
        "role": "student",
        "joined_at": datetime.now(timezone.utc)
    }
    await class_members_collection.insert_one(member_doc)
    
    return {
        "success": True,
        "message": f"Successfully joined {class_doc['name']}",
        "class": {
            "class_id": class_doc["class_id"],
            "name": class_doc["name"],
            "subject": class_doc["subject"],
            "teacher_name": class_doc.get("teacher_name", "Unknown")
        }
    }


@router.get("/{class_id}/members")
async def get_class_members(
    class_id: str,
    token: str = Query(None),
    role: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Get class roster (teacher only for full details, students see limited info)"""
    user = await get_user_from_token(_extract_token(token, authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Check membership
    membership = await class_members_collection.find_one({
        "class_id": class_id,
        "user_id": user["user_id"]
    })
    
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this class")
    
    # Build query
    query = {"class_id": class_id}
    if role:
        query["role"] = role
    
    members = await class_members_collection.find(query).to_list(length=500)

    # Batch-fetch all user details in one query instead of N+1
    member_user_ids = [m["user_id"] for m in members]
    user_docs = await users_collection.find(
        {"user_id": {"$in": member_user_ids}}
    ).to_list(length=len(member_user_ids))
    user_lookup = {u["user_id"]: u for u in user_docs}

    result = []
    for member in members:
        user_doc = user_lookup.get(member["user_id"])
        if user_doc:
            member_data = {
                "user_id": member["user_id"],
                "name": user_doc["name"],
                "role": member["role"],
                "joined_at": member["joined_at"]
            }

            # Only show email to teachers
            if user.get("role") == "teacher":
                member_data["email"] = user_doc["email"]
                member_data["profile_image"] = user_doc.get("profile_image")

            result.append(member_data)
    
    # Sort: teachers first, then students alphabetically
    result.sort(key=lambda x: (0 if x["role"] == "teacher" else 1, x["name"].lower()))
    
    return {"members": result, "total": len(result)}


@router.delete("/{class_id}/members/{user_id}")
async def remove_class_member(
    class_id: str,
    user_id: str,
    token: str = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Remove a student from class (teacher only)"""
    teacher, class_doc = await verify_class_teacher(_extract_token(token, authorization), class_id)
    
    # Can't remove yourself
    if user_id == teacher["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot remove yourself from the class")
    
    # Find member
    member = await class_members_collection.find_one({
        "class_id": class_id,
        "user_id": user_id
    })
    
    if not member:
        raise HTTPException(status_code=404, detail="Student not found in this class")
    
    if member["role"] == "teacher":
        raise HTTPException(status_code=400, detail="Cannot remove a teacher")
    
    await class_members_collection.delete_one({
        "class_id": class_id,
        "user_id": user_id
    })
    
    return {"success": True, "message": "Student removed from class"}


@router.post("/{class_id}/leave")
async def leave_class(class_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Leave a class (students only)"""
    user = await get_user_from_token(_extract_token(token, authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    membership = await class_members_collection.find_one({
        "class_id": class_id,
        "user_id": user["user_id"]
    })
    
    if not membership:
        raise HTTPException(status_code=404, detail="You are not a member of this class")
    
    if membership["role"] == "teacher":
        raise HTTPException(status_code=400, detail="Teachers cannot leave their own class")
    
    await class_members_collection.delete_one({
        "class_id": class_id,
        "user_id": user["user_id"]
    })
    
    return {"success": True, "message": "Left class successfully"}


# ============================================================================
# CLASS CODE MANAGEMENT
# ============================================================================

@router.post("/{class_id}/regenerate-code")
async def regenerate_class_code(class_id: str, token: str = Query(None), authorization: Optional[str] = Header(None)):
    """Regenerate class join code (teacher only)"""
    user, class_doc = await verify_class_teacher(_extract_token(token, authorization), class_id)
    
    # Generate new unique code
    new_code = generate_class_code()
    while await classes_collection.find_one({"class_code": new_code}):
        new_code = generate_class_code()
    
    await classes_collection.update_one(
        {"class_id": class_id},
        {"$set": {"class_code": new_code, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"success": True, "class_code": new_code}
