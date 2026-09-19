"""
Authentication Router - Signup, Login, Profile Management
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request, Header
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, Literal, List
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import base64
import os
import uuid
import httpx
import re
import bcrypt
import resend
import logging
from ..middleware.audit import AuditLogger, AuditEventType

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)

# MongoDB collection references (set by main.py)
users_collection = None
sessions_collection = None  # PERSISTENT SESSIONS IN MONGODB!
login_attempts_collection = None  # FIX #9: account lockout tracking

# FIX #9: Lockout configuration
MAX_FAILED_ATTEMPTS = 5       # Lock after 5 failures
LOCKOUT_DURATION_MINUTES = 15  # Lock for 15 minutes

def set_users_collection(collection):
    global users_collection
    users_collection = collection

def set_sessions_collection(collection):
    global sessions_collection
    sessions_collection = collection

def set_login_attempts_collection(collection):
    """FIX #9: Set collection for tracking failed login attempts"""
    global login_attempts_collection
    login_attempts_collection = collection

# Password reset tokens collection
password_reset_tokens_collection = None

def set_password_reset_tokens_collection(collection):
    global password_reset_tokens_collection
    password_reset_tokens_collection = collection

# ============================================================================
# MODELS
# ============================================================================

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    university: str
    invitation_code: Optional[str] = None  # Required for teachers only
    class_code: Optional[str] = None  # Optional: students auto-join a class / researchers auto-join a lab
    role: Literal["teacher", "student", "researcher"] = "student"  # User role
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if len(v) > 128:
            raise ValueError('Password too long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('name')
    def validate_name(cls, v):
        v = v.strip()
        if len(v) < 1 or len(v) > 100:
            raise ValueError('Name must be 1-100 characters')
        # Only allow letters, spaces, hyphens, apostrophes
        if not re.match(r"^[a-zA-Z\s\-'\.]+$", v):
            raise ValueError('Name contains invalid characters')
        return v
    
    @validator('university')
    def validate_university(cls, v):
        v = v.strip()
        if len(v) < 1 or len(v) > 200:
            raise ValueError('University must be 1-200 characters')
        return v
    
    @validator('invitation_code')
    def validate_invitation_code(cls, v, values):
        if v is None or v.strip() == '':
            return v
        v = v.strip()
        if len(v) != 12:
            raise ValueError('Invitation code must be exactly 12 digits')
        if not v.isdigit():
            raise ValueError('Invitation code must contain only digits')
        return v
    
    @validator('class_code')
    def validate_class_code(cls, v):
        if v is None or v.strip() == '':
            return v
        v = v.strip().upper()
        if len(v) < 4 or len(v) > 10:
            raise ValueError('Class code must be 4-10 characters')
        return v
    
    @validator('role')
    def validate_role(cls, v):
        if v not in ["teacher", "student", "researcher"]:
            raise ValueError('Role must be "teacher", "student" or "researcher"')
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) > 128:
            raise ValueError('Password too long')
        return v

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    university: Optional[str] = None

class StylometryEnrollRequest(BaseModel):
    baseline_text: str

class StylometryEnrollAllRequest(BaseModel):
    samples: list  # List of 3 text samples

class UserResponse(BaseModel):
    email: str
    name: str
    university: str
    profile_image: Optional[str] = None
    created_at: str

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def hash_password(password: str) -> str:
    """Hash password using bcrypt (secure, with per-password salt)"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash.
    Supports both new bcrypt hashes and legacy SHA-256 hashes for migration."""
    # bcrypt hashes start with $2b$ or $2a$
    if stored_hash.startswith('$2b$') or stored_hash.startswith('$2a$'):
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    else:
        # Legacy SHA-256 hash - verify against old method
        # FIX #6: Require the env var (no hardcoded fallback)
        salt = os.getenv("INTEGRITY_SIGNING_KEY")
        if not salt:
            if os.getenv("ENVIRONMENT") == "production":
                return False  # Can't verify without the salt
            salt = "dev_salt_do_not_use_in_production"
        legacy_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return legacy_hash == stored_hash


def _legacy_sha256_hash(password: str) -> str:
    """Legacy SHA-256 hash for migration comparison only. Do not use for new passwords."""
    salt = os.getenv("INTEGRITY_SIGNING_KEY")
    if not salt:
        salt = "dev_salt_do_not_use_in_production"
    return hashlib.sha256((password + salt).encode()).hexdigest()


# ============================================================================
# FIX #9: ACCOUNT LOCKOUT
# ============================================================================

async def _check_account_lockout(email: str) -> bool:
    """Check if account is locked out due to too many failed attempts.
    Returns True if locked out."""
    if login_attempts_collection is None:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOCKOUT_DURATION_MINUTES)
    count = await login_attempts_collection.count_documents({
        "email": email.lower(),
        "timestamp": {"$gte": cutoff}
    })
    return count >= MAX_FAILED_ATTEMPTS


async def _record_failed_attempt(email: str, reason: str):
    """Record a failed login attempt."""
    if login_attempts_collection is None:
        return
    await login_attempts_collection.insert_one({
        "email": email.lower(),
        "reason": reason,
        "timestamp": datetime.now(timezone.utc)
    })


async def _clear_failed_attempts(email: str):
    """Clear failed attempts after successful login."""
    if login_attempts_collection is None:
        return
    await login_attempts_collection.delete_many({"email": email.lower()})

def generate_session_token() -> str:
    """Generate a secure session token"""
    return secrets.token_urlsafe(32)

async def get_current_user(token: str):
    """Get user from session token - NOW USES MONGODB FOR PERSISTENCE!"""
    global sessions_collection
    
    if sessions_collection is None:
        print("❌ sessions_collection not initialized!")
        return None
    
    if not token:
        return None
    
    # Look up session in MongoDB
    session = await sessions_collection.find_one({"token": token})
    if not session:
        return None
    
    # FIX #21: Use timezone-aware datetime comparison
    expires = session['expires']
    now = datetime.now(timezone.utc)
    # Handle both naive and aware datetimes from MongoDB
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        await sessions_collection.delete_one({"token": token})
        return None
    
    return session['user']


def extract_token(token: Optional[str] = None, authorization: Optional[str] = Header(None)) -> str:
    """Extract auth token from either query param or Authorization header.
    Prefers Authorization header (Bearer token) over query param for security."""
    # Prefer Authorization header
    if authorization:
        if authorization.startswith('Bearer '):
            return authorization[7:]
        return authorization
    # Fallback to query param (backward compatibility)
    if token:
        return token
    raise HTTPException(status_code=401, detail="Authentication required")

# ============================================================================
# ROUTES
# ============================================================================

@router.post("/signup")
async def signup(request: SignupRequest):
    """Register a new user with role-based invitation codes"""
    global users_collection
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        if users_collection is None:
            raise HTTPException(status_code=500, detail="Database not connected")
        
        # FIX #12: Validate invitation code for teachers with audit logging
        if request.role == "teacher":
            if not request.invitation_code or request.invitation_code.strip() == '':
                raise HTTPException(status_code=400, detail="Invitation code is required for teacher accounts")
            valid_code = os.getenv("TEACHER_INVITATION_CODE")
            if not valid_code:
                valid_code = os.getenv("INVITATION_CODE")
            if not valid_code:
                logger.error("TEACHER_INVITATION_CODE environment variable not set!")
                raise HTTPException(status_code=500, detail="Server configuration error")
            if request.invitation_code != valid_code:
                # FIX #12: Log failed invitation code attempts for security monitoring
                logger.warning(f"Invalid teacher invitation code attempt for email: {request.email}")
                raise HTTPException(status_code=403, detail="Invalid invitation code for teacher role")
            # FIX #12: Log successful teacher signups
            logger.info(f"Valid teacher invitation code used by: {request.email}")
        # Students don't need invitation codes - they join classes via class_code
        
        # Check if user already exists
        existing = await users_collection.find_one({"email": request.email.lower()})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Validate password strength
        if len(request.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        
        # Generate email verification code (6-digit)
        email_verification_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])

        # Create user document with unique user_id and role
        user_doc = {
            "user_id": str(uuid.uuid4()),
            "email": request.email.lower(),
            "password_hash": hash_password(request.password),
            "name": request.name.strip(),
            "university": request.university.strip(),
            "role": request.role,  # Store user role
            "profile_image": None,
            "email_verified": False,
            "email_verification_code": email_verification_code,
            "email_verification_expires": datetime.now(timezone.utc) + timedelta(hours=24),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Insert into MongoDB
        result = await users_collection.insert_one(user_doc)
        logger.info(f"User created: {user_doc['email']}, role: {user_doc['role']}, id: {result.inserted_id}")
        
        # Generate session token and store in MongoDB for persistence
        token = generate_session_token()
        session_doc = {
            "token": token,
            "user": {
                "user_id": user_doc["user_id"],
                "email": user_doc["email"],
                "name": user_doc["name"],
                "university": user_doc["university"],
                "role": user_doc["role"],
                "profile_image": None,
                "email_verified": False,
                "stylometry_enrolled": False,
                "stylometry_baseline_samples": 0,
                "face_biometric_enabled": False,
                "face_baseline_uploaded": False
            },
            "expires": datetime.now(timezone.utc) + timedelta(days=7),
            "created_at": datetime.now(timezone.utc)
        }
        await sessions_collection.insert_one(session_doc)
        logger.info(f"Session created for user: {user_doc['email']} (verification code sent)")
        
        # Auto-join class if student provided a class_code,
        # or lab if researcher provided a lab code (labs are classes with kind="lab")
        joined_class = None
        if request.role in ("student", "researcher") and request.class_code:
            try:
                from .classes import classes_collection as cls_col, class_members_collection as mem_col
                if cls_col is not None and mem_col is not None:
                    join_query = {
                        "class_code": request.class_code.upper(),
                        "archived": False
                    }
                    # Researchers may only join labs; students may only join classes
                    if request.role == "researcher":
                        join_query["kind"] = "lab"
                    else:
                        join_query["kind"] = {"$ne": "lab"}
                    class_doc = await cls_col.find_one(join_query)
                    if class_doc:
                        # Check not already a member (shouldn't be, just created)
                        existing_member = await mem_col.find_one({
                            "class_id": class_doc["class_id"],
                            "user_id": user_doc["user_id"]
                        })
                        if not existing_member:
                            member_doc = {
                                "class_id": class_doc["class_id"],
                                "user_id": user_doc["user_id"],
                                "user_name": user_doc["name"],
                                "user_email": user_doc["email"],
                                "role": request.role,
                                "joined_at": datetime.now(timezone.utc)
                            }
                            await mem_col.insert_one(member_doc)
                            joined_class = {
                                "class_id": class_doc["class_id"],
                                "name": class_doc["name"]
                            }
                            logger.info(f"Auto-joined {request.role} {user_doc['email']} to {class_doc['name']}")
            except Exception as e:
                logger.warning(f"Auto-join class failed (non-critical): {str(e)}")

        # Researchers always get a Personal Lab if they didn't join one,
        # so every research topic has a parent lab (class) for stylometry keying.
        if request.role == "researcher" and joined_class is None:
            try:
                from .classes import (
                    classes_collection as cls_col,
                    class_members_collection as mem_col,
                    generate_class_code,
                )
                if cls_col is not None and mem_col is not None:
                    lab_code = generate_class_code()
                    while await cls_col.find_one({"class_code": lab_code}):
                        lab_code = generate_class_code()
                    lab_doc = {
                        "class_id": str(uuid.uuid4()),
                        "kind": "lab",
                        "name": f"{user_doc['name']}'s Lab",
                        "section": None,
                        "subject": "Research",
                        "description": "Personal research lab",
                        "color": "#7c3aed",
                        "class_code": lab_code,
                        "teacher_id": user_doc["user_id"],  # PI / owner
                        "teacher_name": user_doc["name"],
                        "settings": {},
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                        "archived": False
                    }
                    await cls_col.insert_one(lab_doc)
                    await mem_col.insert_one({
                        "class_id": lab_doc["class_id"],
                        "user_id": user_doc["user_id"],
                        "user_name": user_doc["name"],
                        "user_email": user_doc["email"],
                        "role": "researcher",
                        "joined_at": datetime.now(timezone.utc)
                    })
                    joined_class = {
                        "class_id": lab_doc["class_id"],
                        "name": lab_doc["name"]
                    }
                    logger.info(f"Created personal lab for researcher {user_doc['email']}")
            except Exception as e:
                logger.warning(f"Personal lab creation failed (non-critical): {str(e)}")
        
        return {
            "success": True,
            "message": "Account created successfully. Please verify your email.",
            "token": token,
            "joined_class": joined_class,
            "email_verification_required": True,
            "user": {
                "user_id": user_doc["user_id"],
                "email": user_doc["email"],
                "name": user_doc["name"],
                "university": user_doc["university"],
                "role": user_doc["role"],
                "profile_image": None,
                "email_verified": False,
                "stylometry_enrolled": False,
                "stylometry_baseline_samples": 0,
                "face_biometric_enabled": False,
                "face_baseline_uploaded": False
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {str(e)}", exc_info=True)
        # FIX #17: Don't leak internal error details to client
        raise HTTPException(status_code=500, detail="Signup failed. Please try again later.")


# ============================================================================
# EMAIL VERIFICATION
# ============================================================================

class VerifyEmailRequest(BaseModel):
    code: str

@router.post("/verify-email")
async def verify_email(request: VerifyEmailRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """Verify user's email address with a 6-digit code"""
    resolved_token = extract_token(token, authorization)
    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    global users_collection, sessions_collection
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    user_doc = await users_collection.find_one({"email": user["email"]})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    if user_doc.get("email_verified"):
        return {"success": True, "message": "Email already verified"}

    stored_code = user_doc.get("email_verification_code")
    expires = user_doc.get("email_verification_expires")

    if not stored_code:
        raise HTTPException(status_code=400, detail="No verification code found. Request a new one.")

    if expires and expires.replace(tzinfo=timezone.utc if expires.tzinfo is None else expires.tzinfo) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification code expired. Request a new one.")

    if not secrets.compare_digest(request.code.strip(), stored_code):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Mark email as verified
    await users_collection.update_one(
        {"email": user["email"]},
        {"$set": {"email_verified": True, "updated_at": datetime.now(timezone.utc)},
         "$unset": {"email_verification_code": "", "email_verification_expires": ""}}
    )

    # Update session
    await sessions_collection.update_many(
        {"user.email": user["email"]},
        {"$set": {"user.email_verified": True}}
    )

    return {"success": True, "message": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification(token: str = None, authorization: Optional[str] = Header(None)):
    """Resend email verification code"""
    resolved_token = extract_token(token, authorization)
    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    global users_collection
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    user_doc = await users_collection.find_one({"email": user["email"]})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    if user_doc.get("email_verified"):
        return {"success": True, "message": "Email already verified"}

    # Generate new code
    new_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    await users_collection.update_one(
        {"email": user["email"]},
        {"$set": {
            "email_verification_code": new_code,
            "email_verification_expires": datetime.now(timezone.utc) + timedelta(hours=24),
        }}
    )

    # TODO: Send actual email with the code when email service is integrated
    # For now, code is stored and returned in non-production environments
    import logging
    logging.getLogger(__name__).info(f"Verification code for {user['email']}: {new_code}")

    response = {"success": True, "message": "Verification code sent"}
    if os.getenv("ENVIRONMENT") != "production":
        response["code"] = new_code  # Only expose in dev for testing
    return response


@router.post("/login")
async def login(login_data: LoginRequest, request: Request):
    """Login user"""
    global users_collection
    
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    # FIX #9: Check account lockout BEFORE attempting login
    if await _check_account_lockout(login_data.email):
        await AuditLogger.log_auth_failure(login_data.email, "Account locked out", request)
        raise HTTPException(
            status_code=429,
            detail=f"Account temporarily locked due to too many failed attempts. Try again in {LOCKOUT_DURATION_MINUTES} minutes."
        )
    
    # Find user
    user = await users_collection.find_one({"email": login_data.email.lower()})
    if not user:
        # Log failed attempt and record for lockout
        await AuditLogger.log_auth_failure(login_data.email, "User not found", request)
        await _record_failed_attempt(login_data.email, "User not found")
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Check password (supports both bcrypt and legacy SHA-256)
    if not verify_password(login_data.password, user["password_hash"]):
        # Log failed attempt and record for lockout
        await AuditLogger.log_auth_failure(login_data.email, "Invalid password", request)
        await _record_failed_attempt(login_data.email, "Invalid password")
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Auto-migrate legacy SHA-256 hash to bcrypt on successful login
    if not user["password_hash"].startswith('$2b$') and not user["password_hash"].startswith('$2a$'):
        new_hash = hash_password(login_data.password)
        await users_collection.update_one(
            {"email": user["email"]},
            {"$set": {"password_hash": new_hash}}
        )
        import logging
        logging.getLogger(__name__).info(f"Migrated password hash to bcrypt for user: {user['email']}")
    
    # FIX #9: Clear failed attempts on successful login
    await _clear_failed_attempts(login_data.email)
    
    # Generate session token and store in MongoDB for persistence
    token = generate_session_token()
    session_doc = {
        "token": token,
        "user": {
            "user_id": user.get("user_id", str(user.get("_id", ""))),
            "email": user["email"],
            "name": user["name"],
            "university": user.get("university", ""),
            "role": user.get("role", "student"),
            "profile_image": user.get("profile_image"),
            "email_verified": user.get("email_verified", False),
            "stylometry_enrolled": user.get("stylometry_enrolled", False),
            "stylometry_baseline_samples": user.get("stylometry_baseline_samples", 0),
            "face_biometric_enabled": user.get("face_biometric_enabled", False),
            "face_baseline_uploaded": bool(user.get("face_baseline_image"))
        },
        "expires": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)
    }
    
    # Delete any existing sessions for this user (single session per user)
    await sessions_collection.delete_many({"user.email": user["email"]})
    await sessions_collection.insert_one(session_doc)
    
    # Log successful login
    await AuditLogger.log_auth_success(
        user_id=user.get("user_id", str(user.get("_id", ""))),
        user_email=user["email"],
        request=request
    )
    
    return {
        "success": True,
        "message": "Login successful",
        "token": token,
        "user": {
            "user_id": user.get("user_id", str(user.get("_id", ""))),
            "email": user["email"],
            "name": user["name"],
            "university": user.get("university", ""),
            "role": user.get("role", "student"),
            "profile_image": user.get("profile_image"),
            "email_verified": user.get("email_verified", False),
            "stylometry_enrolled": user.get("stylometry_enrolled", False),
            "stylometry_baseline_samples": user.get("stylometry_baseline_samples", 0),
            "face_biometric_enabled": user.get("face_biometric_enabled", False),
            "face_baseline_uploaded": bool(user.get("face_baseline_image"))
        }
    }

@router.get("/me")
async def get_profile(token: str = None, authorization: Optional[str] = Header(None)):
    """Get current user profile"""
    resolved_token = extract_token(token, authorization)
    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return {
        "success": True,
        "user": user
    }

@router.post("/logout")
async def logout(token: str = None, authorization: Optional[str] = Header(None)):
    """Logout user - delete session from MongoDB"""
    resolved_token = extract_token(token, authorization)
    global sessions_collection
    if sessions_collection is not None:
        await sessions_collection.delete_one({"token": resolved_token})
    return {"success": True, "message": "Logged out"}

@router.put("/profile")
async def update_profile(request: ProfileUpdateRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """Update user profile"""
    resolved_token = extract_token(token, authorization)
    global users_collection, sessions_collection
    
    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    # Build update document
    update_doc = {"updated_at": datetime.now(timezone.utc)}
    session_update = {}
    if request.name:
        update_doc["name"] = request.name.strip()
        session_update["user.name"] = request.name.strip()
    if request.university:
        update_doc["university"] = request.university.strip()
        session_update["user.university"] = request.university.strip()
    
    # Update in MongoDB
    await users_collection.update_one(
        {"email": user["email"]},
        {"$set": update_doc}
    )
    
    # Update session in MongoDB
    if session_update:
        await sessions_collection.update_one(
            {"token": resolved_token},
            {"$set": session_update}
        )
    
    # Get updated session
    session = await sessions_collection.find_one({"token": resolved_token})
    
    return {
        "success": True,
        "message": "Profile updated",
        "user": session["user"] if session else user
    }

@router.post("/upload-image")
async def upload_profile_image(token: str = Form(...), image: UploadFile = File(...)):
    """Upload profile image - stores in S3 when available, falls back to MongoDB"""
    global users_collection, sessions_collection
    from ..services import image_storage

    user = await get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    # Validate file type
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Read image bytes
    contents = await image.read()
    
    # Limit size (5MB)
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be less than 5MB")
    
    # Convert to data URL
    base64_image = base64.b64encode(contents).decode('utf-8')
    data_url = f"data:{image.content_type};base64,{base64_image}"

    # Try S3 first, fall back to storing data URL in MongoDB
    user_id = user.get("user_id", user["email"])
    s3_key = await image_storage.upload_image(data_url, folder="profiles", user_id=user_id)
    profile_value = s3_key if s3_key else data_url

    # If replacing an old S3 image, delete the old one
    old_user = await users_collection.find_one({"email": user["email"]})
    if old_user and old_user.get("profile_image") and not old_user["profile_image"].startswith("data:"):
        await image_storage.delete_image(old_user["profile_image"])

    # Update in MongoDB (stores S3 key or data URL)
    await users_collection.update_one(
        {"email": user["email"]},
        {"$set": {"profile_image": profile_value, "updated_at": datetime.now(timezone.utc)}}
    )

    # For session/response, resolve to a URL the frontend can use
    display_url = await image_storage.get_image_url(profile_value) if s3_key else data_url
    
    # Update session in MongoDB
    await sessions_collection.update_one(
        {"token": token},
        {"$set": {"user.profile_image": display_url}}
    )
    
    return {
        "success": True,
        "message": "Profile image uploaded",
        "profile_image": display_url
    }

@router.get("/verify")
async def verify_token(token: str = None, authorization: Optional[str] = Header(None)):
    """Verify if token is valid"""
    resolved_token = extract_token(token, authorization)
    user = await get_current_user(resolved_token)
    if not user:
        return {"valid": False}
    return {"valid": True, "user": user}

# ============================================================================
# FIX #13: PASSWORD CHANGE
# ============================================================================

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('New password must be at least 8 characters')
        if len(v) > 128:
            raise ValueError('Password too long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v

@router.post("/change-password")
async def change_password(request: PasswordChangeRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """Change user password (requires current password for re-authentication, Fix #14)"""
    resolved_token = extract_token(token, authorization)
    global users_collection, sessions_collection
    
    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    # FIX #14: Re-authenticate with current password
    user_doc = await users_collection.find_one({"email": user["email"]})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not verify_password(request.current_password, user_doc["password_hash"]):
        raise HTTPException(status_code=403, detail="Current password is incorrect")
    
    # Don't allow same password
    if request.current_password == request.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from current password")
    
    # Update password
    new_hash = hash_password(request.new_password)
    await users_collection.update_one(
        {"email": user["email"]},
        {"$set": {
            "password_hash": new_hash,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    # Invalidate all existing sessions (force re-login)
    await sessions_collection.delete_many({"user.email": user["email"]})
    
    # Create a new session for the current user
    new_token = generate_session_token()
    new_session = {
        "token": new_token,
        "user": {
            "user_id": user.get("user_id"),
            "email": user["email"],
            "name": user.get("name"),
            "university": user.get("university"),
            "role": user.get("role", "student"),
            "profile_image": user.get("profile_image"),
            "stylometry_enrolled": user.get("stylometry_enrolled", False),
            "stylometry_baseline_samples": user.get("stylometry_baseline_samples", 0),
            "face_biometric_enabled": user.get("face_biometric_enabled", False),
            "face_baseline_uploaded": user.get("face_baseline_uploaded", False)
        },
        "expires": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)
    }
    await sessions_collection.insert_one(new_session)
    
    return {
        "success": True,
        "message": "Password changed successfully. Please log in again on other devices.",
        "token": new_token
    }


# ============================================================================
# FORGOT PASSWORD / RESET PASSWORD
# ============================================================================

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if len(v) > 128:
            raise ValueError('Password too long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v


RESET_TOKEN_EXPIRY_MINUTES = 15
RESET_RATE_LIMIT_PER_HOUR = 3


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """
    Send a password reset email. Always returns success to avoid leaking
    whether an email exists in the system.
    """
    global users_collection, password_reset_tokens_collection

    email = request.email.lower().strip()

    # Always return success (don't leak email existence)
    success_response = {
        "success": True,
        "message": "If an account exists with that email, we've sent a password reset link."
    }

    if users_collection is None or password_reset_tokens_collection is None:
        return success_response

    # Check if user exists
    user = await users_collection.find_one({"email": email})
    if not user:
        return success_response

    # Rate limit: max 3 reset requests per email per hour
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_count = await password_reset_tokens_collection.count_documents({
        "email": email,
        "created_at": {"$gte": one_hour_ago}
    })
    if recent_count >= RESET_RATE_LIMIT_PER_HOUR:
        return success_response  # Silently rate-limit

    # Generate reset token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)

    await password_reset_tokens_collection.insert_one({
        "token": token,
        "email": email,
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires_at,
        "used": False
    })

    # Send email via Resend
    frontend_url = os.getenv("FRONTEND_URL", "https://www.editorrah.com")
    reset_link = f"{frontend_url}/reset-password?token={token}"
    user_name = user.get("name", "there")

    try:
        resend.api_key = os.getenv("RESEND_API_KEY")
        resend.Emails.send({
            "from": "Editorrah <onboarding@resend.dev>",
            "to": [email],
            "subject": "Reset your Editorrah password",
            "html": f"""
            <div style="font-family: 'Google Sans', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
                <div style="text-align: center; margin-bottom: 32px;">
                    <svg width="40" height="40" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                        <rect width="48" height="48" rx="8" fill="#1a73e8"/>
                        <circle cx="24" cy="21" r="5" fill="white"/>
                        <path d="M33,30c0-3.5-3.5-5-9-5s-9,1.5-9,5v2h18V30z" fill="white"/>
                    </svg>
                </div>
                <h2 style="color: #202124; font-weight: 400; text-align: center; margin-bottom: 8px;">
                    Reset your password
                </h2>
                <p style="color: #5f6368; text-align: center; font-size: 14px; margin-bottom: 32px;">
                    Hi {user_name}, we received a request to reset your Editorrah password.
                </p>
                <div style="text-align: center; margin-bottom: 32px;">
                    <a href="{reset_link}"
                       style="display: inline-block; padding: 12px 32px; background: #1a73e8; color: white;
                              text-decoration: none; border-radius: 4px; font-size: 14px; font-weight: 500;">
                        Reset Password
                    </a>
                </div>
                <p style="color: #5f6368; font-size: 12px; text-align: center;">
                    This link expires in {RESET_TOKEN_EXPIRY_MINUTES} minutes. If you didn't request this, you can safely ignore this email.
                </p>
                <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 32px 0 16px;">
                <p style="color: #9aa0a6; font-size: 11px; text-align: center;">
                    Editorrah &mdash; Academic Integrity Platform
                </p>
            </div>
            """
        })
        logger.info(f"Password reset email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
        # Still return success to avoid leaking info

    return success_response


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """Reset password using a valid, unexpired, one-time token."""
    global users_collection, sessions_collection, password_reset_tokens_collection

    if password_reset_tokens_collection is None or users_collection is None:
        raise HTTPException(status_code=500, detail="Service unavailable")

    # Find the token
    token_doc = await password_reset_tokens_collection.find_one({
        "token": request.token,
        "used": False
    })

    if not token_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link. Please request a new one.")

    # Check expiry (MongoDB returns naive datetimes, so compare without tz)
    expires_at = token_doc["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        await password_reset_tokens_collection.update_one(
            {"_id": token_doc["_id"]},
            {"$set": {"used": True}}
        )
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")

    email = token_doc["email"]

    # Mark token as used (one-time use)
    await password_reset_tokens_collection.update_one(
        {"_id": token_doc["_id"]},
        {"$set": {"used": True}}
    )

    # Update password
    new_hash = hash_password(request.new_password)
    result = await users_collection.update_one(
        {"email": email},
        {"$set": {
            "password_hash": new_hash,
            "updated_at": datetime.now(timezone.utc)
        }}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")

    # Invalidate all existing sessions (force re-login everywhere)
    if sessions_collection is not None:
        await sessions_collection.delete_many({"user.email": email})

    logger.info(f"Password reset completed for {email}")

    return {
        "success": True,
        "message": "Password has been reset successfully. Please sign in with your new password."
    }


STYLOMETRY_API_BASE = os.getenv("STYLOMETRY_V3_BASE", "https://forensicstylo.up.railway.app")


def _stylometry_class_id(university: str) -> str:
    """Derive a V2 class_id from the user's university for impostor pooling."""
    slug = re.sub(r"[^a-z0-9]+", "-", university.lower()).strip("-")
    return f"uni-{slug}" if slug else "uni-default"


async def _reset_v1_enrollment(email: str, token: str = None):
    """Reset a stale V1 enrollment so the user is prompted to re-enroll in V2."""
    global users_collection, sessions_collection
    if users_collection is not None:
        await users_collection.update_one(
            {"email": email},
            {"$set": {
                "stylometry_enrolled": False,
                "stylometry_baseline_samples": 0,
                "stylometry_baseline_words": 0,
                "stylometry_needs_v2_migration": True,
                "updated_at": datetime.now(timezone.utc),
            }},
        )
    if sessions_collection is not None and token:
        await sessions_collection.update_many(
            {"user.email": email},
            {"$set": {
                "user.stylometry_enrolled": False,
                "user.stylometry_baseline_samples": 0,
            }},
        )


@router.post("/stylometry/enroll")
async def enroll_stylometry(request: StylometryEnrollRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """Enroll user in stylometry system with baseline text (V3 per-course engine).
    Re-calling for the same student+course appends to the existing profile."""
    resolved_token = extract_token(token, authorization)
    global users_collection, sessions_collection

    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    word_count = len(request.baseline_text.split())
    if word_count < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Baseline text must be at least 50 words. Current: {word_count} words"
        )

    user_doc = await users_collection.find_one({"email": user["email"]})
    is_first_enrollment = not user_doc.get("stylometry_enrolled", False)
    student_id = user.get("user_id", user["email"])
    class_id = _stylometry_class_id(user.get("university", ""))

    try:
        from ..utils.http_client import get_client
        client = get_client()

        response = await client.post(
            f"{STYLOMETRY_API_BASE}/course/enroll",
            json={
                "student_id": student_id,
                "name": user.get("name", ""),
                "class_id": class_id,
                "writing_samples": [request.baseline_text],
            },
            timeout=120,
        )
        response.raise_for_status()
        stylometry_result = response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Stylometry service error: {str(e)}")

    update_data = {
        "stylometry_enrolled": True,
        "stylometry_student_id": student_id,
        "stylometry_class_id": class_id,
        "stylometry_baseline_samples": stylometry_result.get("total_course_samples", 1),
        "stylometry_baseline_words": stylometry_result.get("total_words", word_count),
        "stylometry_profile_strength": stylometry_result.get("profile_strength", "weak"),
        "stylometry_last_updated": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    await users_collection.update_one({"email": user["email"]}, {"$set": update_data})
    await sessions_collection.update_one(
        {"token": resolved_token},
        {"$set": {
            "user.stylometry_enrolled": True,
            "user.stylometry_baseline_samples": update_data["stylometry_baseline_samples"],
        }},
    )

    return {
        "success": True,
        "message": "Enrolled in stylometry system" if is_first_enrollment else "Baseline updated",
        "baseline_words": stylometry_result.get("total_words"),
        "n_samples": stylometry_result.get("total_course_samples"),
        "profile_strength": stylometry_result.get("profile_strength"),
    }


@router.post("/stylometry/append")
async def append_stylometry_baseline(request: StylometryEnrollRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """Append verified text to student's baseline (only if last stylometry verdict was verified).
    V3: re-calling /course/enroll appends to the existing course profile."""
    resolved_token = extract_token(token, authorization)
    global users_collection, sessions_collection

    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    user_doc = await users_collection.find_one({"email": user["email"]})
    if not user_doc.get("stylometry_enrolled", False):
        raise HTTPException(status_code=400, detail="User not enrolled in stylometry")

    word_count = len(request.baseline_text.split())
    if word_count < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Text must be at least 50 words. Current: {word_count} words"
        )

    last_verdict = user_doc.get("stylometry_last_verdict")
    if last_verdict != "verified":
        return {
            "success": False,
            "absorbed": False,
            "message": (
                f"Not absorbed: last stylometry verdict={last_verdict}. "
                f"Requires verdict=verified."
            ),
        }

    student_id = user_doc.get("stylometry_student_id", user.get("user_id", user["email"]))
    class_id = user_doc.get("stylometry_class_id", _stylometry_class_id(user.get("university", "")))

    try:
        from ..utils.http_client import get_client
        client = get_client()
        response = await client.post(
            f"{STYLOMETRY_API_BASE}/course/enroll",
            json={
                "student_id": student_id,
                "name": user.get("name", ""),
                "class_id": class_id,
                "writing_samples": [request.baseline_text],
            },
            timeout=120,
        )
        if response.status_code == 404:
            await _reset_v1_enrollment(user["email"], resolved_token)
            return {
                "success": False,
                "absorbed": False,
                "needs_reenrollment": True,
                "message": "Your stylometry profile needs to be re-created. Please re-enroll in your profile settings.",
            }
        response.raise_for_status()
        stylometry_result = response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Stylometry service error: {str(e)}")

    await users_collection.update_one(
        {"email": user["email"]},
        {"$set": {
            "stylometry_baseline_samples": stylometry_result.get("total_course_samples"),
            "stylometry_baseline_words": stylometry_result.get("total_words"),
            "stylometry_profile_strength": stylometry_result.get("profile_strength"),
            "stylometry_last_updated": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    await sessions_collection.update_one(
        {"token": resolved_token},
        {"$set": {"user.stylometry_baseline_samples": stylometry_result.get("total_course_samples")}},
    )

    return {
        "success": True,
        "absorbed": True,
        "message": "Baseline updated successfully",
        "n_samples": stylometry_result.get("total_course_samples"),
        "baseline_words": stylometry_result.get("total_words"),
        "profile_strength": stylometry_result.get("profile_strength"),
    }


@router.post("/stylometry/enroll-all")
async def enroll_stylometry_all(request: StylometryEnrollAllRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """Enroll user with all 3 baseline samples at once (V3 per-course engine).
    V3 /course/enroll accepts all samples in a single call."""
    resolved_token = extract_token(token, authorization)
    global users_collection, sessions_collection

    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    if len(request.samples) != 3:
        raise HTTPException(status_code=400, detail="Exactly 3 samples required")

    total_words = 0
    for i, sample in enumerate(request.samples):
        word_count = len(sample.split())
        if word_count < 50:
            raise HTTPException(
                status_code=400,
                detail=f"Sample {i+1} must have at least 50 words. Current: {word_count}"
            )
        total_words += word_count

    ai_flags = []
    for sample in request.samples:
        ai_result = await gptzero_predict(sample)
        ai_flags.append(is_ai_written(ai_result))
    if ai_flags and all(ai_flags):
        raise HTTPException(
            status_code=400,
            detail="All 3 baseline samples appear AI-generated. Please submit your own writing."
        )

    student_id = user.get("user_id", user["email"])
    class_id = _stylometry_class_id(user.get("university", ""))

    try:
        from ..utils.http_client import get_client
        client = get_client()

        response = await client.post(
            f"{STYLOMETRY_API_BASE}/course/enroll",
            json={
                "student_id": student_id,
                "name": user.get("name", ""),
                "class_id": class_id,
                "writing_samples": request.samples,
            },
            timeout=120,
        )
        response.raise_for_status()
        profile_data = response.json()

    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Stylometry service error: {str(e)}")

    n_samples = profile_data.get("total_course_samples", 3)
    total_baseline_words = profile_data.get("total_words", total_words)

    update_data = {
        "stylometry_enrolled": True,
        "stylometry_student_id": student_id,
        "stylometry_class_id": class_id,
        "stylometry_baseline_samples": n_samples,
        "stylometry_baseline_words": total_baseline_words,
        "stylometry_profile_strength": profile_data.get("profile_strength", "fair"),
        "stylometry_last_updated": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    await users_collection.update_one({"email": user["email"]}, {"$set": update_data})
    await sessions_collection.update_one(
        {"token": resolved_token},
        {"$set": {
            "user.stylometry_enrolled": True,
            "user.stylometry_baseline_samples": n_samples,
        }},
    )

    return {
        "success": True,
        "message": "Successfully enrolled with 3 baseline samples",
        "n_samples": n_samples,
        "total_words": total_baseline_words,
        "profile_strength": profile_data.get("profile_strength"),
    }


@router.get("/stylometry/status")
async def get_stylometry_status(token: str = None, authorization: Optional[str] = Header(None)):
    """Get user's stylometry enrollment status with V2 profile data"""
    resolved_token = extract_token(token, authorization)
    global users_collection

    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    user_doc = await users_collection.find_one({"email": user["email"]})
    enrolled = user_doc.get("stylometry_enrolled", False)

    result = {
        "enrolled": enrolled,
        "baseline_samples": user_doc.get("stylometry_baseline_samples", 0),
        "baseline_words": user_doc.get("stylometry_baseline_words", 0),
        "profile_strength": user_doc.get("stylometry_profile_strength"),
        "last_updated": user_doc.get("stylometry_last_updated"),
    }

    if enrolled:
        student_id = user_doc.get("stylometry_student_id", user.get("user_id", user["email"]))
        try:
            from ..utils.http_client import get_client
            client = get_client()
            resp = await client.get(
                f"{STYLOMETRY_API_BASE}/course/profile/{student_id}",
                timeout=30,
            )
            if resp.status_code == 200:
                profile = resp.json()
                courses = profile.get("courses", [])
                if courses:
                    best = max(courses, key=lambda c: c.get("n_samples", 0))
                    result["profile_strength"] = best.get("profile_strength")
                    result["baseline_samples"] = best.get("n_samples", result["baseline_samples"])
                    result["baseline_words"] = best.get("total_words", result["baseline_words"])
                result["total_courses"] = profile.get("total_courses", 0)
            elif resp.status_code == 404:
                await _reset_v1_enrollment(user["email"], resolved_token)
                result["enrolled"] = False
                result["needs_reenrollment"] = True
                result["message"] = "Your profile needs to be re-created. Please re-enroll."
        except Exception:
            pass

    return result


class StylometryVerifyRequest(BaseModel):
    text: str


@router.post("/stylometry/verify")
async def verify_stylometry(request: StylometryVerifyRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """Verify if document matches user's writing style using V3 per-course engine."""
    resolved_token = extract_token(token, authorization)
    global users_collection

    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    user_doc = await users_collection.find_one({"email": user["email"]})
    if not user_doc.get("stylometry_enrolled", False):
        return {
            "verified": None,
            "status": "not_enrolled",
            "message": "User not enrolled in stylometry",
        }

    word_count = len(request.text.split())
    if word_count < 50:
        return {
            "verified": None,
            "status": "insufficient_text",
            "message": "Document needs at least 50 words for verification",
        }

    student_id = user_doc.get("stylometry_student_id", user.get("user_id", user["email"]))
    class_id = user_doc.get("stylometry_class_id", _stylometry_class_id(user.get("university", "")))

    try:
        from ..utils.http_client import get_client
        client = get_client()
        response = await client.post(
            f"{STYLOMETRY_API_BASE}/course/verify",
            json={
                "student_id": student_id,
                "class_id": class_id,
                "submission_text": request.text,
            },
            timeout=120,
        )

        if response.status_code == 404:
            await _reset_v1_enrollment(user["email"], resolved_token)
            return {
                "verified": None,
                "status": "not_enrolled",
                "message": "Your stylometry profile needs to be re-created. Please re-enroll in your profile settings.",
                "needs_reenrollment": True,
            }

        if response.status_code == 200:
            result = response.json()
            probability = result.get("probability", 0)
            verdict = result.get("verdict", "inconclusive")

            if verdict == "verified":
                verified = True
                status = "verified"
            elif verdict == "flagged":
                verified = False
                status = "mismatch"
            elif verdict == "review_required":
                verified = None
                status = "uncertain"
            else:
                verified = None
                status = "uncertain"

            await users_collection.update_one(
                {"email": user["email"]},
                {"$set": {
                    "stylometry_last_verdict": verdict,
                    "stylometry_last_score": probability,
                }},
            )

            return {
                "verified": verified,
                "score": probability,
                "similarity": probability,
                "verdict": verdict,
                "status": status,
                "confidence": result.get("confidence"),
                "z_score": result.get("z_score"),
                "margin": result.get("margin"),
                "cosine_score": result.get("cosine_score"),
                "best_impostor_sim": result.get("best_impostor_sim"),
                "impostor_count": result.get("impostor_count"),
                "n_profile_essays": result.get("n_profile_essays"),
                "profile_strength": result.get("profile_strength"),
                "profile_absorbed": result.get("profile_absorbed"),
                "explanation": result.get("explanation"),
                "baseline_words": user_doc.get("stylometry_baseline_words", 0),
                "baseline_samples": user_doc.get("stylometry_baseline_samples", 0),
            }
        else:
            return {
                "verified": None,
                "status": "api_error",
                "message": f"Stylometry API error: {response.status_code}",
            }
    except Exception as e:
        return {
            "verified": None,
            "status": "error",
            "message": str(e),
        }


@router.get("/stylometry/audit-trail")
async def get_stylometry_audit_trail(token: str = None, authorization: Optional[str] = Header(None), limit: int = 50):
    """Retrieve forensic verification audit trail from V2 GI engine"""
    resolved_token = extract_token(token, authorization)
    global users_collection

    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    user_doc = await users_collection.find_one({"email": user["email"]})
    if not user_doc.get("stylometry_enrolled", False):
        raise HTTPException(status_code=400, detail="User not enrolled in stylometry")

    student_id = user_doc.get("stylometry_student_id", user.get("user_id", user["email"]))

    try:
        from ..utils.http_client import get_client
        client = get_client()
        response = await client.get(
            f"{STYLOMETRY_API_BASE}/students/{student_id}/audit-trail",
            params={"limit": limit},
            timeout=30,
        )
        if response.status_code == 404:
            await _reset_v1_enrollment(user["email"], resolved_token)
            return {"entries": [], "needs_reenrollment": True, "message": "Profile needs re-enrollment."}
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Stylometry service error: {str(e)}")

# ============================================================================
# FACT CHECK / HALLUCINATION DETECTION (Proxy to OpenFactCheck API)
# ============================================================================

class FactCheckRequest(BaseModel):
    text: str
    evidence_mode: str = "REGISTRY_ONLY"  # REGISTRY_ONLY, OFFLINE_ONLY, HYBRID
    mode: str = "general"  # "general" | "published_paper" (IEEE/journal audit)

@router.post("/factcheck/verify")
async def verify_factcheck(request: FactCheckRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """
    Proxy endpoint for fact-checking and hallucination detection.
    Verifies claims, DOIs, URLs, and detects contradictions.
    """
    resolved_token = extract_token(token, authorization)
    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    if not request.text or len(request.text.strip()) < 50:
        return {
            "summary": {"supported": 0, "unsupported": 0, "contradicted": 0, "unknown": 0},
            "claims": [],
            "warnings": ["Text too short for fact checking (minimum 50 characters)"],
            "reference_report": {"dois": [], "urls": [], "summary": {}}
        }
    
    # Call OpenFactCheck API (defaults to prod; set OPENFACTCHECK_URL for local).
    factcheck_api_url = os.getenv(
        "OPENFACTCHECK_URL", "https://openfactcheck-production.up.railway.app/v1/verify"
    )
    # The engine now requires x-api-key; send it (matches engine's API_KEYS).
    _ofc_key = os.getenv("OPENFACTCHECK_API_KEY", "")

    try:
        from ..utils.http_client import get_client
        client = get_client()
        response = await client.post(
            factcheck_api_url,
            json={
                "text": request.text,
                "evidence_mode": request.evidence_mode,
                "mode": request.mode
            },
            # Long documents produce many LLM-verified claims; the shared 60s
            # client default times out on anything past a short paragraph.
            timeout=240.0,
            headers={"x-api-key": _ofc_key} if _ofc_key else None,
        )
        if response.status_code == 200:
            return response.json()
        else:
            _hint = ""
            if response.status_code in (401, 403):
                _hint = (" — backend is missing OPENFACTCHECK_API_KEY"
                         if not _ofc_key else " — API key mismatch with the engine")
            return {
                "summary": {"supported": 0, "unsupported": 0, "contradicted": 0, "unknown": 0},
                "claims": [],
                "warnings": [f"Fact check API error: {response.status_code}{_hint}. No claims were analyzed."],
                "reference_report": {"dois": [], "urls": [], "summary": {}},
                "error": True,
            }
    except Exception as e:
        return {
            "summary": {"supported": 0, "unsupported": 0, "contradicted": 0, "unknown": 0},
            "claims": [],
            "warnings": [f"Fact check service error: {str(e)}. No claims were analyzed."],
            "reference_report": {"dois": [], "urls": [], "summary": {}},
            "error": True,
        }

# ============================================================================
# AI DETECTION
# ============================================================================

class AIDetectionRequest(BaseModel):
    text: str

async def gptzero_predict(text: str):
    """
    Detect if content is AI-generated using GPTZero.
    Only runs for documents > 100 words.
    """
    word_count = len(text.split())
    if word_count < 100:
        return {
            "ai_probability": 0,
            "status": "document_too_short",
            "message": f"Document needs at least 100 words for AI detection. Current: {word_count} words",
            "word_count": word_count
        }

    gptzero_api_key = os.getenv("GPTZERO_API_KEY")
    if not gptzero_api_key:
        return {
            "ai_probability": 0,
            "status": "api_key_missing",
            "message": "AI detection service not configured"
        }

    gptzero_url = "https://api.gptzero.me/v2/predict/text"

    try:
        from ..utils.http_client import get_client
        client = get_client()
        response = await client.post(
            gptzero_url,
            headers={
                "x-api-key": gptzero_api_key,
                "Content-Type": "application/json"
            },
            json={
                "document": text,
                "multilingual": False
            }
        )

        if response.status_code == 200:
            result = response.json()
            documents = result.get("documents", [])
            if documents and len(documents) > 0:
                doc = documents[0]
                class_probs = doc.get("class_probabilities", {})
                ai_prob = class_probs.get("ai", 0)
                human_prob = class_probs.get("human", 0)
                mixed_prob = class_probs.get("mixed", 0)

                predicted_class = doc.get("predicted_class", "unknown")
                confidence = doc.get("confidence_category", "unknown")
                avg_generated_prob = doc.get("average_generated_prob", 0)

                return {
                    "ai_probability": ai_prob,
                    "human_probability": human_prob,
                    "mixed_probability": mixed_prob,
                    "predicted_class": predicted_class,
                    "confidence": confidence,
                    "average_generated_prob": avg_generated_prob,
                    "status": "success",
                    "word_count": word_count
                }
            return {
                "ai_probability": 0,
                "status": "no_result",
                "message": "AI Detection API returned no documents"
            }
        return {
            "ai_probability": 0,
            "status": "api_error",
            "message": f"AI Detection API error: {response.status_code}"
        }
    except Exception as e:
        return {
            "ai_probability": 0,
            "status": "error",
            "message": str(e)
        }

def is_ai_written(result: dict) -> bool:
    if result.get("status") != "success":
        return False
    ai_prob = result.get("ai_probability", 0)
    predicted_class = result.get("predicted_class", "")
    return predicted_class == "ai" or ai_prob >= 0.8

@router.post("/ai-detection/verify")
async def verify_ai_content(request: AIDetectionRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """
    Detect if content is AI-generated using advanced AI analysis.
    Only runs for documents > 100 words.
    Returns AI probability for trust score calculation.
    """
    resolved_token = extract_token(token, authorization)
    user = await get_current_user(resolved_token)
    if not user:
        return {
            "ai_probability": 0,
            "status": "not_authenticated",
            "message": "Not authenticated"
        }
    return await gptzero_predict(request.text)


# ============================================================================
# AI ASSISTANT PROXY (keeps OpenAI key on the server, not in the frontend)
# ============================================================================

class AssistantRequest(BaseModel):
    prompt: str
    selected_text: str = ""
    max_tokens: int = 1000

@router.post("/assistant/chat")
async def assistant_chat(request: AssistantRequest, token: str = None, authorization: Optional[str] = Header(None)):
    """
    Proxy endpoint for the AI writing assistant.
    Keeps the OpenAI API key on the server instead of exposing it in frontend JS.
    """
    resolved_token = extract_token(token, authorization)
    user = await get_current_user(resolved_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI assistant not configured")

    # Limit max_tokens to prevent abuse
    max_tokens = min(request.max_tokens, 2000)

    user_content = f"{request.prompt}: {request.selected_text}" if request.selected_text else request.prompt

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
                    {"role": "user", "content": user_content}
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7
            }
        )
        response.raise_for_status()
        result = response.json()
        reply = result.get("choices", [{}])[0].get("message", {}).get("content", "No response.")
        return {"success": True, "content": reply}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {e.response.status_code}")
    except Exception:
        raise HTTPException(status_code=500, detail="AI assistant request failed")
