"""
Audit Logging Middleware
Tracks important actions for security and compliance
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorCollection
import logging

# Configure logger
logger = logging.getLogger("audit")
logger.setLevel(logging.INFO)

# Audit collection reference (set from main.py)
audit_collection: Optional[AsyncIOMotorCollection] = None


def set_audit_collection(collection: AsyncIOMotorCollection):
    """Set the MongoDB collection for audit logs"""
    global audit_collection
    audit_collection = collection


# ============================================================================
# AUDIT EVENT TYPES
# ============================================================================

class AuditEventType:
    # Authentication
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILED = "auth.login.failed"
    AUTH_LOGOUT = "auth.logout"
    AUTH_SIGNUP = "auth.signup"
    AUTH_PASSWORD_CHANGE = "auth.password.change"
    
    # User actions
    USER_PROFILE_UPDATE = "user.profile.update"
    USER_FACE_ENROLLED = "user.face.enrolled"
    
    # Class management
    CLASS_CREATED = "class.created"
    CLASS_UPDATED = "class.updated"
    CLASS_ARCHIVED = "class.archived"
    CLASS_MEMBER_ADDED = "class.member.added"
    CLASS_MEMBER_REMOVED = "class.member.removed"
    
    # Assignment management
    ASSIGNMENT_CREATED = "assignment.created"
    ASSIGNMENT_UPDATED = "assignment.updated"
    ASSIGNMENT_PUBLISHED = "assignment.published"
    ASSIGNMENT_DELETED = "assignment.deleted"
    
    # Submission actions
    SUBMISSION_CREATED = "submission.created"
    SUBMISSION_SUBMITTED = "submission.submitted"
    SUBMISSION_GRADED = "submission.graded"
    SUBMISSION_RETURNED = "submission.returned"
    SUBMISSION_AUTO_GRADED = "submission.auto_graded"
    
    # Integrity events
    INTEGRITY_FACE_VERIFIED = "integrity.face.verified"
    INTEGRITY_FACE_FAILED = "integrity.face.failed"
    INTEGRITY_PLAGIARISM_DETECTED = "integrity.plagiarism.detected"
    INTEGRITY_TRUST_LOW = "integrity.trust.low"
    
    # Security events
    SECURITY_RATE_LIMITED = "security.rate_limited"
    SECURITY_SUSPICIOUS_ACTIVITY = "security.suspicious"
    SECURITY_INVALID_TOKEN = "security.invalid_token"
    
    # Admin actions
    ADMIN_USER_MODIFIED = "admin.user.modified"
    ADMIN_SETTINGS_CHANGED = "admin.settings.changed"


# ============================================================================
# AUDIT LOGGER
# ============================================================================

class AuditLogger:
    """
    Logs audit events to MongoDB and console
    """
    
    @staticmethod
    def _get_client_info(request: Optional[Request] = None) -> Dict[str, str]:
        """Extract client information from request"""
        if not request:
            return {}
        
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        
        # Hash IP for privacy (optional)
        ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:12]
        
        return {
            "ip_hash": ip_hash,
            "user_agent": user_agent[:200],  # Limit length
            "path": str(request.url.path),
            "method": request.method
        }
    
    @staticmethod
    async def log(
        event_type: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        severity: str = "info"
    ):
        """
        Log an audit event
        
        Args:
            event_type: Type of event (use AuditEventType constants)
            user_id: ID of the user performing the action
            user_email: Email of the user (for readability)
            resource_type: Type of resource affected (e.g., "class", "assignment")
            resource_id: ID of the affected resource
            details: Additional event details
            request: FastAPI request object for client info
            severity: Event severity (info, warning, error, critical)
        """
        
        timestamp = datetime.now(timezone.utc)
        
        audit_entry = {
            "timestamp": timestamp,
            "event_type": event_type,
            "severity": severity,
            "user_id": user_id,
            "user_email": user_email,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "client_info": AuditLogger._get_client_info(request)
        }
        
        # Log to console
        log_message = (
            f"[AUDIT] {event_type} | "
            f"user={user_email or user_id or 'anonymous'} | "
            f"resource={resource_type}:{resource_id or 'N/A'}"
        )
        
        if severity == "critical":
            logger.critical(log_message)
        elif severity == "error":
            logger.error(log_message)
        elif severity == "warning":
            logger.warning(log_message)
        else:
            logger.info(log_message)
        
        # Store in MongoDB
        if audit_collection is not None:
            try:
                await audit_collection.insert_one(audit_entry)
            except Exception as e:
                logger.error(f"Failed to store audit log: {e}")
    
    @staticmethod
    async def log_auth_success(user_id: str, user_email: str, request: Request):
        """Log successful authentication"""
        await AuditLogger.log(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            user_id=user_id,
            user_email=user_email,
            request=request
        )
    
    @staticmethod
    async def log_auth_failure(email: str, reason: str, request: Request):
        """Log failed authentication attempt"""
        await AuditLogger.log(
            event_type=AuditEventType.AUTH_LOGIN_FAILED,
            user_email=email,
            details={"reason": reason},
            request=request,
            severity="warning"
        )
    
    @staticmethod
    async def log_submission_action(
        action: str,
        submission_id: str,
        user_id: str,
        user_email: str,
        assignment_id: str,
        details: Optional[Dict] = None,
        request: Optional[Request] = None
    ):
        """Log submission-related action"""
        event_types = {
            "created": AuditEventType.SUBMISSION_CREATED,
            "submitted": AuditEventType.SUBMISSION_SUBMITTED,
            "graded": AuditEventType.SUBMISSION_GRADED,
            "returned": AuditEventType.SUBMISSION_RETURNED,
            "auto_graded": AuditEventType.SUBMISSION_AUTO_GRADED
        }
        
        await AuditLogger.log(
            event_type=event_types.get(action, f"submission.{action}"),
            user_id=user_id,
            user_email=user_email,
            resource_type="submission",
            resource_id=submission_id,
            details={**(details or {}), "assignment_id": assignment_id},
            request=request
        )
    
    @staticmethod
    async def log_integrity_event(
        event: str,
        user_id: str,
        user_email: str,
        submission_id: Optional[str] = None,
        score: Optional[float] = None,
        details: Optional[Dict] = None,
        request: Optional[Request] = None
    ):
        """Log integrity-related event"""
        severity = "warning" if event in ["face_failed", "plagiarism_detected", "trust_low"] else "info"
        
        event_types = {
            "face_verified": AuditEventType.INTEGRITY_FACE_VERIFIED,
            "face_failed": AuditEventType.INTEGRITY_FACE_FAILED,
            "plagiarism_detected": AuditEventType.INTEGRITY_PLAGIARISM_DETECTED,
            "trust_low": AuditEventType.INTEGRITY_TRUST_LOW
        }
        
        await AuditLogger.log(
            event_type=event_types.get(event, f"integrity.{event}"),
            user_id=user_id,
            user_email=user_email,
            resource_type="submission" if submission_id else None,
            resource_id=submission_id,
            details={**(details or {}), "score": score},
            request=request,
            severity=severity
        )
    
    @staticmethod
    async def log_security_event(
        event: str,
        details: Dict,
        request: Request,
        user_id: Optional[str] = None
    ):
        """Log security-related event"""
        event_types = {
            "rate_limited": AuditEventType.SECURITY_RATE_LIMITED,
            "suspicious": AuditEventType.SECURITY_SUSPICIOUS_ACTIVITY,
            "invalid_token": AuditEventType.SECURITY_INVALID_TOKEN
        }
        
        await AuditLogger.log(
            event_type=event_types.get(event, f"security.{event}"),
            user_id=user_id,
            details=details,
            request=request,
            severity="warning"
        )


# ============================================================================
# QUERY HELPERS
# ============================================================================

async def get_audit_logs(
    user_id: Optional[str] = None,
    event_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    skip: int = 0
) -> list:
    """
    Query audit logs with filters
    """
    if audit_collection is None:
        return []
    
    query = {}
    
    if user_id:
        query["user_id"] = user_id
    if event_type:
        query["event_type"] = {"$regex": f"^{event_type}"}
    if resource_type:
        query["resource_type"] = resource_type
    if resource_id:
        query["resource_id"] = resource_id
    if severity:
        query["severity"] = severity
    if start_date:
        query["timestamp"] = {"$gte": start_date}
    if end_date:
        query.setdefault("timestamp", {})["$lte"] = end_date
    
    cursor = audit_collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    
    logs = []
    async for log in cursor:
        log["_id"] = str(log["_id"])
        logs.append(log)
    
    return logs


async def get_user_activity_summary(user_id: str, days: int = 30) -> Dict:
    """
    Get activity summary for a user
    """
    if audit_collection is None:
        return {}
    
    from datetime import timedelta
    start_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0) - timedelta(days=days)
    
    pipeline = [
        {
            "$match": {
                "user_id": user_id,
                "timestamp": {"$gte": start_date}
            }
        },
        {
            "$group": {
                "_id": "$event_type",
                "count": {"$sum": 1},
                "last_occurrence": {"$max": "$timestamp"}
            }
        }
    ]
    
    cursor = audit_collection.aggregate(pipeline)
    
    summary = {}
    async for doc in cursor:
        summary[doc["_id"]] = {
            "count": doc["count"],
            "last_occurrence": doc["last_occurrence"]
        }
    
    return summary
