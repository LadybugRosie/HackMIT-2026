"""
Face Biometric Verification Router
Handles face baseline upload, verification, and continuous monitoring using AWS Rekognition
"""
from fastapi import APIRouter, HTTPException, Form, UploadFile, File, Header, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import base64
import io
import os
import logging

# Import AWS Rekognition service
from ..services import aws_rekognition

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/face", tags=["Face Verification"])

# MongoDB collection references (set by main.py)
users_collection = None
sessions_collection = None
face_check_log_collection = None  # Server-side face verification log
assignments_collection = None
classes_collection = None
class_members_collection = None  # FIX #8: Need this for correct membership query

def set_users_collection(collection):
    global users_collection
    users_collection = collection

def set_sessions_collection(collection):
    global sessions_collection
    sessions_collection = collection

def set_face_check_log_collection(collection):
    global face_check_log_collection
    face_check_log_collection = collection

def set_assignments_collection(collection):
    global assignments_collection
    assignments_collection = collection

def set_classes_collection(collection):
    global classes_collection
    classes_collection = collection

def set_class_members_collection(collection):
    """FIX #8: Need class_members to correctly check student enrollment"""
    global class_members_collection
    class_members_collection = collection

# Import get_current_user from auth router
from .auth import get_current_user


def _extract_token(token: Optional[str] = None, authorization: Optional[str] = Header(None)) -> str:
    """Extract token from Authorization header or query param."""
    if authorization and authorization.startswith('Bearer '):
        return authorization[7:]
    if authorization:
        return authorization
    if token:
        return token
    raise HTTPException(status_code=401, detail="Authentication required")


# ============================================================================
# MODELS
# ============================================================================

class FaceSettingsRequest(BaseModel):
    face_biometric_enabled: bool


class FaceVerifyRequest(BaseModel):
    image_base64: str  # Base64 encoded image from webcam


class FaceSessionVerifyRequest(BaseModel):
    image_base64: str
    session_id: str


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def decode_base64_image(base64_string: str) -> str:
    """
    Validate and return base64 image string
    AWS Rekognition works directly with base64, so we just pass it through
    """
    # Remove data URL prefix if present
    if ',' in base64_string:
        return base64_string.split(',')[1]
    return base64_string


# ============================================================================
# ROUTES
# ============================================================================

@router.get("/status")
async def get_face_status():
    """Check if face verification is available"""
    return {
        "available": aws_rekognition.AWS_AVAILABLE,
        "aws_rekognition": aws_rekognition.AWS_AVAILABLE,
        "region": os.getenv("AWS_REGION", "not-configured")
    }


@router.post("/upload-baseline")
async def upload_face_baseline(token: str = Form(...), image: UploadFile = File(...)):
    """Upload baseline face photo for verification"""
    global users_collection, sessions_collection
    
    user = await get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    if not aws_rekognition.AWS_AVAILABLE:
        raise HTTPException(status_code=500, detail="AWS Rekognition not available on server")
    
    # Validate file type
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Read image
    contents = await image.read()
    
    # Limit size (5MB for AWS Rekognition)
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be less than 5MB")
    
    # Convert to base64 for AWS Rekognition
    base64_image = base64.b64encode(contents).decode('utf-8')
    
    # Detect face to verify a face is present
    detection_result = aws_rekognition.detect_faces(base64_image)
    
    if not detection_result.get("success"):
        error_msg = detection_result.get('error', 'Unknown error')
        raise HTTPException(
            status_code=400, 
            detail=f"Face detection failed: {error_msg}"
        )
    
    # Store image as base64 data URL
    data_url = f"data:{image.content_type};base64,{base64_image}"
    
    # Index face in AWS Rekognition collection
    index_result = aws_rekognition.index_face(base64_image, user["email"])
    
    # Update user in MongoDB
    update_data = {
        "face_baseline_image": data_url,
        "face_baseline_uploaded_at": datetime.now(timezone.utc),
        "face_biometric_enabled": True,  # Auto-enable when baseline uploaded
        "updated_at": datetime.now(timezone.utc)
    }
    
    # Store AWS face_id if indexing was successful
    if index_result.get("success"):
        update_data["aws_face_id"] = index_result.get("face_id")
        update_data["aws_image_id"] = index_result.get("image_id")
    
    await users_collection.update_one(
        {"email": user["email"]},
        {"$set": update_data}
    )
    
    # Update session
    await sessions_collection.update_one(
        {"token": token},
        {"$set": {
            "user.face_biometric_enabled": True,
            "user.face_baseline_uploaded": True
        }}
    )
    
    logger.info(f"Face baseline uploaded for user: {user['email']}")
    
    return {
        "success": True,
        "message": "Face baseline uploaded successfully. Face verification is now enabled.",
        "face_detected": True,
        "confidence": detection_result.get("confidence"),
        "indexed": index_result.get("success", False)
    }


@router.post("/upload-baseline-base64")
async def upload_face_baseline_base64(request: FaceVerifyRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """Upload baseline face photo as base64 (from webcam)"""
    resolved_token = _extract_token(token, authorization)
    global users_collection, sessions_collection
    
    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    if not aws_rekognition.AWS_AVAILABLE:
        raise HTTPException(status_code=500, detail="AWS Rekognition not available on server")
    
    try:
        # Decode and validate base64 image
        image_base64 = decode_base64_image(request.image_base64)
        
        # Detect face using AWS Rekognition
        detection_result = aws_rekognition.detect_faces(image_base64)
        
        if not detection_result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=f"Face detection failed: {detection_result.get('error', 'Unknown error')}"
            )
        
        # Store image in S3 (or fall back to data URL)
        from ..services import image_storage
        raw_data_url = request.image_base64 if request.image_base64.startswith('data:') else f"data:image/jpeg;base64,{image_base64}"
        user_id = user.get("user_id", user["email"])
        s3_key = await image_storage.upload_image(raw_data_url, folder="face-baselines", user_id=user_id)
        face_image_value = s3_key if s3_key else raw_data_url

        # Delete old S3 face image if exists
        old_user = await users_collection.find_one({"email": user["email"]})
        if old_user and old_user.get("face_baseline_image") and not old_user["face_baseline_image"].startswith("data:"):
            await image_storage.delete_image(old_user["face_baseline_image"])

        # Index face in AWS Rekognition collection
        index_result = aws_rekognition.index_face(image_base64, user["email"])
        
        # Update user
        update_data = {
            "face_baseline_image": face_image_value,
            "face_baseline_uploaded_at": datetime.now(timezone.utc),
            "face_biometric_enabled": True,
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Store AWS face_id if indexing was successful
        if index_result.get("success"):
            update_data["aws_face_id"] = index_result.get("face_id")
            update_data["aws_image_id"] = index_result.get("image_id")
        
        await users_collection.update_one(
            {"email": user["email"]},
            {"$set": update_data}
        )
        
        # Update session
        await sessions_collection.update_one(
            {"token": resolved_token},
            {"$set": {
                "user.face_biometric_enabled": True,
                "user.face_baseline_uploaded": True
            }}
        )
        
        logger.info(f"Face baseline (webcam) uploaded for user: {user['email']}")
        
        return {
            "success": True,
            "message": "Face baseline captured successfully",
            "face_detected": True,
            "confidence": detection_result.get("confidence"),
            "indexed": index_result.get("success", False)
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/settings")
async def update_face_settings(request: FaceSettingsRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """Enable or disable face biometric verification"""
    resolved_token = _extract_token(token, authorization)
    global users_collection, sessions_collection
    
    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    # Check if baseline exists when enabling
    if request.face_biometric_enabled:
        user_doc = await users_collection.find_one({"email": user["email"]})
        if not user_doc.get("face_baseline_image"):
            raise HTTPException(
                status_code=400,
                detail="Please upload a baseline face photo before enabling face verification"
            )
    
    # Update settings
    await users_collection.update_one(
        {"email": user["email"]},
        {"$set": {
            "face_biometric_enabled": request.face_biometric_enabled,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    # Update session
    await sessions_collection.update_one(
        {"token": resolved_token},
        {"$set": {"user.face_biometric_enabled": request.face_biometric_enabled}}
    )
    
    status = "enabled" if request.face_biometric_enabled else "disabled"
    logger.info(f"Face biometric {status} for user: {user['email']}")
    
    return {
        "success": True,
        "message": f"Face biometric verification {status}",
        "face_biometric_enabled": request.face_biometric_enabled
    }


@router.get("/settings")
async def get_face_settings(token: str = None, authorization: Optional[str] = Header(None)):
    """Get user's face biometric settings"""
    resolved_token = _extract_token(token, authorization)
    global users_collection
    
    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    user_doc = await users_collection.find_one({"email": user["email"]})
    
    return {
        "face_biometric_enabled": user_doc.get("face_biometric_enabled", False),
        "face_baseline_uploaded": bool(user_doc.get("face_baseline_image")),
        "face_baseline_uploaded_at": user_doc.get("face_baseline_uploaded_at"),
        "available": aws_rekognition.AWS_AVAILABLE,
        "aws_indexed": bool(user_doc.get("aws_face_id"))
    }


@router.post("/verify-access")
async def verify_face_for_access(request: FaceVerifyRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """
    Verify face before granting editor access.
    Called when user tries to open the editor.
    """
    resolved_token = _extract_token(token, authorization)
    global users_collection
    
    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    if not aws_rekognition.AWS_AVAILABLE:
        # If AWS Rekognition not available, log the bypass server-side
        if face_check_log_collection is not None:
            await face_check_log_collection.insert_one({
                "user_id": user.get("user_id"),
                "user_email": user["email"],
                "check_type": "access",
                "verified": True,
                "bypass": True,
                "reason": "AWS Rekognition not available",
                "timestamp": datetime.now(timezone.utc)
            })
        return {
            "verified": True,
            "message": "AWS Rekognition not available on server",
            "bypass": True
        }
    
    # Get user's face settings
    user_doc = await users_collection.find_one({"email": user["email"]})
    
    # Check if face biometric is enabled
    if not user_doc.get("face_biometric_enabled", False):
        return {
            "verified": True,
            "message": "Face biometric not enabled",
            "bypass": True
        }
    
    # Check if baseline exists
    baseline_image = user_doc.get("face_baseline_image")
    if not baseline_image:
        raise HTTPException(
            status_code=400,
            detail="No baseline face photo found. Please upload one in your profile."
        )
    
    try:
        # Decode current image from webcam
        current_image_base64 = decode_base64_image(request.image_base64)
        
        # Decode baseline image
        baseline_image_base64 = decode_base64_image(baseline_image)
        
        # Compare faces using AWS Rekognition
        result = aws_rekognition.compare_faces(
            baseline_image_base64,
            current_image_base64,
            similarity_threshold=90.0  # 90% similarity threshold
        )
        
        if result.get("no_face"):
            return {
                "verified": False,
                "message": "No face detected. Please position your face clearly in front of the camera.",
                "retry": True
            }
        
        if not result.get("success"):
            return {
                "verified": False,
                "message": f"Verification failed: {result.get('error', 'Unknown error')}",
                "retry": True
            }
        
        # Log verification attempt
        await users_collection.update_one(
            {"email": user["email"]},
            {"$set": {
                "last_face_verification": datetime.now(timezone.utc),
                "last_face_verification_result": result["verified"]
            }}
        )
        
        if result["verified"]:
            logger.info(f"✅ Face verification PASSED for user: {user['email']} (Similarity: {result.get('similarity', 0):.1f}%)")
            
            # SERVER-SIDE face check log (Fix for loophole #3)
            if face_check_log_collection is not None:
                await face_check_log_collection.insert_one({
                    "user_id": user.get("user_id"),
                    "user_email": user["email"],
                    "check_type": "access",
                    "verified": True,
                    "similarity": result.get("similarity"),
                    "timestamp": datetime.now(timezone.utc)
                })
            
            return {
                "verified": True,
                "message": "Face verified successfully! Access granted.",
                "similarity": result.get("similarity"),
                "confidence": result.get("confidence")
            }
        else:
            logger.warning(f"❌ Face verification FAILED for user: {user['email']}")
            
            # Log failures too
            if face_check_log_collection is not None:
                await face_check_log_collection.insert_one({
                    "user_id": user.get("user_id"),
                    "user_email": user["email"],
                    "check_type": "access",
                    "verified": False,
                    "similarity": result.get("similarity", 0),
                    "timestamp": datetime.now(timezone.utc)
                })
            
            return {
                "verified": False,
                "message": "Face does not match baseline. Access denied.",
                "similarity": result.get("similarity", 0)
            }
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify-session")
async def verify_face_during_session(request: FaceSessionVerifyRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """
    Verify face during active editing session (periodic check).
    Called periodically while user is working in the editor.
    """
    resolved_token = _extract_token(token, authorization)
    global users_collection
    
    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    if not aws_rekognition.AWS_AVAILABLE:
        # Log the bypass server-side
        if face_check_log_collection is not None:
            await face_check_log_collection.insert_one({
                "user_id": user.get("user_id"),
                "user_email": user["email"],
                "session_id": request.session_id,
                "check_type": "session",
                "verified": True,
                "bypass": True,
                "reason": "AWS Rekognition not available",
                "timestamp": datetime.now(timezone.utc)
            })
        return {
            "verified": True,
            "continue_session": True,
            "bypass": True
        }
    
    # Get user's face settings
    user_doc = await users_collection.find_one({"email": user["email"]})
    
    if not user_doc.get("face_biometric_enabled", False):
        return {
            "verified": True,
            "continue_session": True,
            "bypass": True
        }
    
    baseline_image = user_doc.get("face_baseline_image")
    if not baseline_image:
        return {
            "verified": True,
            "continue_session": True,
            "bypass": True,
            "message": "No baseline configured"
        }
    
    try:
        current_image_base64 = decode_base64_image(request.image_base64)
        
        # Use direct compare_faces against the student's own baseline first.
        # This avoids false "different person" detections from the collection search
        # when lighting changes cause a match to a different enrolled face.
        baseline_image_base64 = decode_base64_image(baseline_image)
        result = aws_rekognition.compare_faces(
            baseline_image_base64,
            current_image_base64,
            similarity_threshold=80.0
        )
        
        if result.get("no_face"):
            logger.warning(f"No face detected during session check for user: {user['email']}")
            return {
                "verified": False,
                "continue_session": True,
                "warning": True,
                "message": "No face detected. Please return to your seat."
            }
        
        if not result.get("success"):
            return {
                "verified": False,
                "continue_session": True,
                "warning": True,
                "message": f"Verification error: {result.get('error', 'Unknown')}"
            }
        
        liveness_data = result.get("liveness_data", {})
        
        if result["verified"]:
            log_entry = {
                "user_id": user.get("user_id"),
                "user_email": user["email"],
                "session_id": request.session_id,
                "check_type": "session",
                "verified": True,
                "similarity": result.get("similarity"),
                "timestamp": datetime.now(timezone.utc),
                "pose_yaw": liveness_data.get("pose_yaw"),
                "pose_pitch": liveness_data.get("pose_pitch"),
                "eyes_open": liveness_data.get("eyes_open"),
                "eyes_open_confidence": liveness_data.get("eyes_open_confidence"),
                "quality_sharpness": liveness_data.get("quality_sharpness"),
            }
            
            photo_attack_suspected = False
            photo_attack_reason = None
            
            if face_check_log_collection is not None:
                await face_check_log_collection.insert_one(log_entry)
                
                try:
                    recent_checks = await face_check_log_collection.find(
                        {"session_id": request.session_id, "verified": True, "pose_yaw": {"$exists": True}},
                    ).sort("timestamp", -1).limit(5).to_list(5)
                    
                    if len(recent_checks) >= 3:
                        eyes_always_open = all(
                            c.get("eyes_open") is True and (c.get("eyes_open_confidence") or 0) > 99.0
                            for c in recent_checks
                        )
                        if eyes_always_open:
                            photo_attack_suspected = True
                            photo_attack_reason = "eyes_never_blink"
                        
                        yaw_values = [c.get("pose_yaw", 0) for c in recent_checks if c.get("pose_yaw") is not None]
                        if len(yaw_values) >= 3:
                            import statistics
                            yaw_stddev = statistics.pstdev(yaw_values)
                            if yaw_stddev < 0.5:
                                photo_attack_suspected = True
                                photo_attack_reason = f"static_face_pose (yaw_stddev={yaw_stddev:.2f})"
                        
                        sharpness_values = [c.get("quality_sharpness", 100) for c in recent_checks if c.get("quality_sharpness") is not None]
                        if sharpness_values and all(s < 25 for s in sharpness_values):
                            photo_attack_suspected = True
                            photo_attack_reason = "consistently_low_sharpness"
                    
                    if photo_attack_suspected:
                        logger.warning(f"PHOTO ATTACK SUSPECTED for {user['email']}: {photo_attack_reason}")
                        await face_check_log_collection.insert_one({
                            "user_id": user.get("user_id"),
                            "user_email": user["email"],
                            "session_id": request.session_id,
                            "check_type": "photo_attack_flag",
                            "reason": photo_attack_reason,
                            "timestamp": datetime.now(timezone.utc)
                        })
                except Exception as trend_err:
                    logger.warning(f"Liveness trend analysis failed (non-fatal): {trend_err}")
            
            response_data = {
                "verified": True,
                "continue_session": True,
                "similarity": result.get("similarity"),
                "confidence": result.get("confidence")
            }
            
            if photo_attack_suspected:
                response_data["photo_attack_warning"] = True
                response_data["warning_reason"] = photo_attack_reason
            
            return response_data
        
        else:
            # Face not recognized — return a warning instead of instant
            # termination.  Poor lighting, camera angle, or a stale baseline
            # can all cause false negatives.  The client uses a 3-strike
            # system, so repeated failures will still terminate the session.
            logger.warning(f"Face not recognized for user: {user['email']}")
            
            if face_check_log_collection is not None:
                await face_check_log_collection.insert_one({
                    "user_id": user.get("user_id"),
                    "user_email": user["email"],
                    "session_id": request.session_id,
                    "check_type": "session",
                    "verified": False,
                    "similarity": result.get("similarity", 0),
                    "timestamp": datetime.now(timezone.utc)
                })
            
            return {
                "verified": False,
                "continue_session": True,
                "warning": True,
                "message": "Face not recognized. Please ensure good lighting and face the camera."
            }
            
    except ValueError as e:
        return {
            "verified": False,
            "continue_session": True,
            "warning": True,
            "message": str(e)
        }


@router.delete("/baseline")
async def delete_face_baseline(token: str = None, authorization: Optional[str] = Header(None)):
    """Delete face baseline and disable face verification"""
    resolved_token = _extract_token(token, authorization)
    global users_collection, sessions_collection
    
    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    # =========================================================================
    # RESTRICTION: Block deletion if student has active assignments requiring
    # face verification (Fix for loophole #4)
    # Teachers can always delete baselines.
    # =========================================================================
    # FIX #8: Use class_members_collection (not classes_collection with wrong field)
    user_role = user.get("role", "student")
    if user_role != "teacher" and assignments_collection is not None and class_members_collection is not None:
        # Find all classes this student is enrolled in via class_members
        memberships = await class_members_collection.find(
            {"user_id": user.get("user_id"), "role": "student"}
        ).to_list(100)
        class_ids = [m["class_id"] for m in memberships]
        
        if class_ids:
            # Check for active assignments with face verification enabled
            now = datetime.now(timezone.utc)
            active_face_assignments = await assignments_collection.count_documents({
                "class_id": {"$in": class_ids},
                "published": True,
                "due_date": {"$gte": now},
                "settings.face_verification_enabled": True
            })
            
            if active_face_assignments > 0:
                raise HTTPException(
                    status_code=403,
                    detail=f"Cannot delete face baseline: you have {active_face_assignments} active assignment(s) "
                           f"that require face verification. Please wait until they are past due."
                )
    
    # Get user's AWS face_id before deletion
    user_doc = await users_collection.find_one({"email": user["email"]})
    aws_face_id = user_doc.get("aws_face_id")
    
    # Delete face from AWS Rekognition collection if it exists
    if aws_face_id and aws_rekognition.AWS_AVAILABLE:
        delete_result = aws_rekognition.delete_face_from_collection(aws_face_id)
        if delete_result.get("success"):
            logger.info(f"✅ Deleted face from AWS collection: {aws_face_id}")
    
    # Remove face data from MongoDB
    await users_collection.update_one(
        {"email": user["email"]},
        {
            "$unset": {
                "face_baseline_image": "",
                "face_baseline_embedding": "",
                "face_baseline_uploaded_at": "",
                "aws_face_id": "",
                "aws_image_id": ""
            },
            "$set": {
                "face_biometric_enabled": False,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    # Update session
    await sessions_collection.update_one(
        {"token": resolved_token},
        {"$set": {
            "user.face_biometric_enabled": False,
            "user.face_baseline_uploaded": False
        }}
    )
    
    logger.info(f"Face baseline deleted for user: {user['email']}")
    
    return {
        "success": True,
        "message": "Face baseline deleted and verification disabled"
    }
