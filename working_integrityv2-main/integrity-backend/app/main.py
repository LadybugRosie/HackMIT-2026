from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
import os
import logging
from dotenv import load_dotenv
import traceback

# Load environment variables FIRST before importing other modules
# override=False ensures Railway/system env vars take priority over .env file
load_dotenv(override=False)

from .routers import integrity_simple as integrity
from .routers import auth
from .routers import face_verification
from .routers import classes
from .routers import assignments
from .routers import submissions
from .routers import stylometry_v3
from .routers import plagiarism_check
from .routers import session_playback
from .routers import chunk_analyze
from .routers import beautify_equation
from .routers import fix_grammar
from .routers import generate_graph
from .routers import image_upload
from .routers import research
from .routers import hallucination
from .services import aws_rekognition
from .services import plagiarism_v2
from .services import image_storage
from .services import media
from .middleware.security import (
    SecurityHeadersMiddleware, 
    RateLimitMiddleware,
    RequestSizeMiddleware,
    initialize_rate_limiter
)
from .middleware.audit import set_audit_collection, AuditLogger
from .utils.http_client import close_client as close_http_client

# Maximum request body size (10MB)
MAX_REQUEST_SIZE = 10 * 1024 * 1024

# Setup logging
log_level = logging.INFO if os.getenv("ENVIRONMENT") == "production" else logging.DEBUG
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_client = None
database = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - handle startup and shutdown"""
    global mongo_client, database
    
    # Get MongoDB URI from environment (REQUIRED in production)
    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("DB_NAME", "editorrah_integrity")
    
    if not mongo_uri:
        logger.error("MONGO_URI environment variable is required!")
        raise ValueError("MONGO_URI environment variable must be set")
    
    try:
        mongo_client = AsyncIOMotorClient(mongo_uri)
        database = mongo_client[db_name]
        
        # Set up collections for auth
        users_collection = database["users"]
        auth.set_users_collection(users_collection)
        
        # CRITICAL: Set up sessions collection for PERSISTENT sessions
        sessions_collection = database["sessions"]
        auth.set_sessions_collection(sessions_collection)
        
        # Set up face verification collections
        face_verification.set_users_collection(users_collection)
        face_verification.set_sessions_collection(sessions_collection)
        
        # Server-side face check log collection (Fix for loophole #3)
        face_check_log_collection = database["face_check_logs"]
        face_verification.set_face_check_log_collection(face_check_log_collection)
        await face_check_log_collection.create_index("user_id")
        await face_check_log_collection.create_index("session_id")
        await face_check_log_collection.create_index("timestamp")
        
        # ============================================================
        # FIX #9: LOGIN ATTEMPTS COLLECTION (account lockout)
        # ============================================================
        login_attempts_collection = database["login_attempts"]
        auth.set_login_attempts_collection(login_attempts_collection)
        await login_attempts_collection.create_index("email")
        # TTL index - auto-expire old attempts after 1 hour
        await login_attempts_collection.create_index(
            "timestamp", expireAfterSeconds=3600
        )
        
        # ============================================================
        # PASSWORD RESET TOKENS COLLECTION
        # ============================================================
        password_reset_tokens_collection = database["password_reset_tokens"]
        auth.set_password_reset_tokens_collection(password_reset_tokens_collection)
        await password_reset_tokens_collection.create_index("token", unique=True)
        await password_reset_tokens_collection.create_index("email")
        # TTL index - auto-expire tokens after 1 hour (cleanup)
        await password_reset_tokens_collection.create_index(
            "created_at", expireAfterSeconds=3600
        )

        # ============================================================
        # FIX #2: INTEGRITY SESSIONS COLLECTION (MongoDB persistence)
        # ============================================================
        integrity_sessions_collection = database["integrity_sessions"]
        integrity.set_integrity_sessions_collection(integrity_sessions_collection)
        await integrity_sessions_collection.create_index("session_id", unique=True)
        await integrity_sessions_collection.create_index("user_id")
        # Compound index for cross-browser session lookup by (user_id, doc_id)
        await integrity_sessions_collection.create_index(
            [("user_id", 1), ("doc_id", 1)], background=True
        )
        # FIX #19: TTL index - auto-expire old integrity sessions after 30 days
        await integrity_sessions_collection.create_index(
            "created_at", expireAfterSeconds=30 * 24 * 3600
        )
        
        # ============================================================
        # CLASSROOM COLLECTIONS
        # ============================================================
        classes_collection = database["classes"]
        class_members_collection = database["class_members"]
        assignments_collection = database["assignments"]
        submissions_collection = database["submissions"]
        fingerprints_collection = database["document_fingerprints"]
        
        # Set up classroom routers
        classes.set_collections(
            classes=classes_collection,
            members=class_members_collection,
            users=users_collection,
            assignments=assignments_collection,
            submissions=submissions_collection
        )
        
        assignments.set_collections(
            assignments=assignments_collection,
            classes=classes_collection,
            members=class_members_collection,
            submissions=submissions_collection,
            users=users_collection
        )
        
        # Give face_verification access to assignments, classes & members for deletion restriction
        face_verification.set_assignments_collection(assignments_collection)
        face_verification.set_classes_collection(classes_collection)
        # FIX #8: face_verification needs class_members to check student enrollment correctly
        face_verification.set_class_members_collection(class_members_collection)
        
        submissions.set_collections(
            submissions=submissions_collection,
            assignments=assignments_collection,
            classes=classes_collection,
            members=class_members_collection,
            users=users_collection,
            fingerprints=fingerprints_collection
        )
        
        # Set up stylometry V3 router
        stylometry_v3.set_collections(
            users=users_collection,
            sessions=sessions_collection,
            members=class_members_collection,
            classes=classes_collection,
            assignments=assignments_collection,
            submissions=submissions_collection,
        )
        
        # Set up plagiarism v2 service + router
        plagiarism_checks_collection = database["plagiarism_checks"]
        scholarly_cache_collection = database["scholarly_cache"]

        plagiarism_v2.set_collections(
            submissions=submissions_collection,
            fingerprints=fingerprints_collection,
            plagiarism_checks=plagiarism_checks_collection,
            scholarly_cache=scholarly_cache_collection,
            users=users_collection,
        )

        plagiarism_check.set_collections(
            submissions=submissions_collection,
            assignments=assignments_collection,
            classes=classes_collection,
            members=class_members_collection,
            users=users_collection,
        )
        
        # ============================================================
        # SESSION PLAYBACK
        # ============================================================
        session_snapshots_collection = database["session_snapshots"]
        session_events_collection = database["session_events"]
        session_playback.set_collections(
            snapshots=session_snapshots_collection,
            submissions=submissions_collection,
            assignments=assignments_collection,
            classes=classes_collection,
            events=session_events_collection,
            users=users_collection,
        )
        try:
            await session_snapshots_collection.create_index("submission_id")
        except Exception:
            pass  # Index may already exist with different options
        try:
            await session_snapshots_collection.create_index(
                [("student_id", 1), ("assignment_id", 1)]
            )
        except Exception:
            pass
        try:
            await session_events_collection.create_index("submission_id")
            await session_events_collection.create_index(
                [("student_id", 1), ("assignment_id", 1), ("chunk_seq", 1)]
            )
            logger.info("Session events collection ready (session_events)")
        except Exception as e:
            logger.warning(f"session_events index creation failed: {e}")

        # ============================================================
        # CHUNK-LEVEL ANALYSIS
        # ============================================================
        chunk_analyze.set_collections(
            users=users_collection,
            sessions=sessions_collection,
            members=class_members_collection,
        )

        # ============================================================
        # IMAGE STORAGE (for graph exports etc.)
        # ============================================================
        editor_images_collection = database["editor_images"]
        image_upload.set_images_collection(editor_images_collection)

        # ============================================================
        # RESEARCHER ACCOUNTS — labs/topics/deliverables/sharing
        # ============================================================
        share_tokens_collection = database["share_tokens"]
        research.set_collections(
            classes=classes_collection,
            members=class_members_collection,
            assignments=assignments_collection,
            submissions=submissions_collection,
            snapshots=session_snapshots_collection,
            users=users_collection,
            share_tokens=share_tokens_collection,
        )
        await share_tokens_collection.create_index("token", unique=True)
        await share_tokens_collection.create_index("submission_id")
        # TTL — share links auto-expire after 30 days
        await share_tokens_collection.create_index(
            "created_at", expireAfterSeconds=30 * 24 * 3600
        )

        # GridFS fallback for PDF/MP4 blobs when S3 is unavailable
        media.set_database(database)

        # ============================================================
        # HALLUCINATION CHECKS (standalone fact-check surface)
        # ============================================================
        hallucination_checks_collection = database["hallucination_checks"]
        hallucination.set_collections(
            checks=hallucination_checks_collection,
            users=users_collection,
        )
        await hallucination_checks_collection.create_index("user_id")
        await hallucination_checks_collection.create_index("created_at")

        # ============================================================
        # AUDIT LOGGING
        # ============================================================
        audit_collection = database["audit_logs"]
        set_audit_collection(audit_collection)
        
        # Create indexes for audit logs
        await audit_collection.create_index("user_id")
        await audit_collection.create_index("event_type")
        # TTL index - auto-expire audit logs after 90 days
        # Must drop old non-TTL index on "timestamp" first if it exists
        try:
            await audit_collection.create_index(
                "timestamp", expireAfterSeconds=90 * 24 * 3600
            )
        except Exception:
            try:
                await audit_collection.drop_index("timestamp_1")
                await audit_collection.create_index(
                    "timestamp", expireAfterSeconds=90 * 24 * 3600
                )
                logger.info("Replaced audit_logs timestamp index with TTL index (90 days)")
            except Exception as idx_err:
                logger.warning(f"Could not create TTL index on audit_logs: {idx_err}")
        
        # Initialize Redis-backed rate limiter (non-fatal if Redis unavailable)
        try:
            initialize_rate_limiter()
        except Exception as e:
            logger.warning(f"Rate limiter init failed (using in-memory fallback): {e}")

        # Initialize AWS Rekognition (non-fatal)
        try:
            aws_initialized = aws_rekognition.initialize_aws_rekognition()
            if aws_initialized:
                logger.info("AWS Rekognition ready for face verification")
            else:
                logger.warning("AWS Rekognition not initialized - face verification may not work")
        except Exception as e:
            logger.warning(f"AWS Rekognition init failed: {e}")

        # Initialize S3 image storage (non-fatal - falls back to MongoDB)
        try:
            s3_initialized = image_storage.initialize_s3()
            if s3_initialized:
                logger.info("S3 image storage ready")
            else:
                logger.warning("S3 not available - images will be stored in MongoDB")
        except Exception as e:
            logger.warning(f"S3 init failed (using MongoDB fallback): {e}")
        
        # Create indexes for auth
        await users_collection.create_index("email", unique=True)
        await users_collection.create_index("user_id", unique=True)
        await sessions_collection.create_index("token", unique=True)
        await sessions_collection.create_index("expires")
        await sessions_collection.create_index("user.email")
        
        # Create indexes for classroom
        await classes_collection.create_index("class_id", unique=True)
        await classes_collection.create_index("class_code", unique=True)
        await classes_collection.create_index("teacher_id")
        await class_members_collection.create_index([("class_id", 1), ("user_id", 1)], unique=True)
        await class_members_collection.create_index("user_id")
        await assignments_collection.create_index("assignment_id", unique=True)
        await assignments_collection.create_index("class_id")
        await assignments_collection.create_index("due_date")
        await submissions_collection.create_index("submission_id", unique=True)
        await submissions_collection.create_index([("assignment_id", 1), ("student_id", 1)], unique=True)
        await submissions_collection.create_index("student_id")
        await submissions_collection.create_index("status")
        await fingerprints_collection.create_index("submission_id", unique=True)
        await fingerprints_collection.create_index("assignment_id")
        await plagiarism_checks_collection.create_index("check_id", unique=True)
        await scholarly_cache_collection.create_index("query_hash")
        
        # Clean up expired sessions on startup
        from datetime import datetime, timezone
        deleted = await sessions_collection.delete_many({"expires": {"$lt": datetime.now(timezone.utc)}})
        if deleted.deleted_count > 0:
            logger.info(f"Cleaned up {deleted.deleted_count} expired sessions")
        
        # ============================================================
        # BATCH SIMILARITY SCHEDULER
        # Background task that checks for assignments past their
        # deadline and runs batch similarity comparison for all
        # submissions. Runs every 5 minutes.
        # ============================================================
        import asyncio
        
        async def _batch_similarity_loop():
            """Periodically check for assignments needing batch similarity."""
            while True:
                try:
                    await asyncio.sleep(300)  # Check every 5 minutes
                    now = datetime.now(timezone.utc)
                    
                    # Find assignments past deadline that haven't had batch similarity run
                    past_due = await assignments_collection.find(
                        {
                            "due_date": {"$lt": now},
                            "batch_similarity_completed": {"$ne": True},
                        },
                        {"assignment_id": 1}
                    ).to_list(length=50)
                    
                    if past_due:
                        from .services.plagiarism_v2 import batch_check_v2
                        seen_aids = set()
                        for assignment in past_due:
                            aid = assignment["assignment_id"]
                            if aid in seen_aids:
                                continue
                            seen_aids.add(aid)
                            try:
                                result = await batch_check_v2(aid)
                                await assignments_collection.update_one(
                                    {"assignment_id": aid},
                                    {"$set": {
                                        "batch_similarity_completed": True,
                                        "batch_similarity_at": now,
                                    }}
                                )
                                if not result.get("skipped"):
                                    logger.info(f"Batch similarity completed for assignment {aid}: {result}")
                            except Exception as e:
                                logger.error(f"Batch similarity failed for assignment {aid}: {e}")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Batch similarity scheduler error: {e}")
        
        similarity_task = asyncio.create_task(_batch_similarity_loop())
        
        logger.info(f"Connected to MongoDB: {db_name}")
        logger.info("Users collection ready")
        logger.info("Sessions collection ready (PERSISTENT)")
        logger.info("Classroom collections ready (classes, assignments, submissions)")
        logger.info("Batch similarity scheduler started (checks every 5 minutes)")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        raise e
    
    yield
    
    # Shutdown
    try:
        similarity_task.cancel()
        await similarity_task
    except (asyncio.CancelledError, NameError):
        pass
    await close_http_client()
    if mongo_client:
        mongo_client.close()
        logger.info("MongoDB connection closed")


# Determine if we're in production
# Check both ENVIRONMENT var and Railway's auto-set vars for robust detection
is_production = (
    os.getenv("ENVIRONMENT") == "production"
    or os.getenv("RAILWAY_ENVIRONMENT") is not None
    or os.getenv("RAILWAY_PROJECT_ID") is not None
)

# Create FastAPI app
app = FastAPI(
    title="Editorrah API",
    description="Document integrity tracking with authentication",
    version="2.0.0",
    lifespan=lifespan,
    # Disable docs in production for security
    docs_url="/docs" if not is_production else None,
    redoc_url="/redoc" if not is_production else None
)

# Add security middleware (order matters - executed bottom to top)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestSizeMiddleware)

# Configure CORS - Always allow production domains + localhost for dev
cors_origins = [
    # Production domains
    "https://editorrah.com",
    "https://www.editorrah.com",
    # Local development
    "http://localhost:9000",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:9000",
    "http://127.0.0.1:8000",
]

# Add any custom CORS_ORIGINS from environment
custom_origins = os.getenv("CORS_ORIGINS", "")
if custom_origins:
    cors_origins.extend([o.strip() for o in custom_origins.split(",") if o.strip()])

# Allow all Railway subdomains AND editorrah.com subdomains
allow_origin_regex = r"https://(.*\.up\.railway\.app|.*\.editorrah\.com)"

logger.info(f"CORS origins configured: {cors_origins}")
logger.info(f"CORS origin regex: {allow_origin_regex}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
    max_age=86400,
)

# Include routers
app.include_router(integrity.router, prefix="/api/integrity", tags=["integrity"])
app.include_router(auth.router, tags=["authentication"])
app.include_router(face_verification.router, tags=["face-verification"])
app.include_router(classes.router, tags=["classes"])
app.include_router(assignments.router, tags=["assignments"])
app.include_router(submissions.router, tags=["submissions"])
app.include_router(stylometry_v3.router, tags=["stylometry-v3"])
app.include_router(plagiarism_check.router, tags=["plagiarism-v2"])
app.include_router(session_playback.router, tags=["session-playback"])
app.include_router(chunk_analyze.router, tags=["chunk-analysis"])
app.include_router(beautify_equation.router, tags=["beautify-equation"])
app.include_router(fix_grammar.router, tags=["fix-grammar"])
app.include_router(generate_graph.router, tags=["generate-graph"])
app.include_router(image_upload.router, tags=["images"])
app.include_router(research.router, tags=["research"])
app.include_router(research.share_router, tags=["share"])
app.include_router(hallucination.router, tags=["hallucination"])

# ============================================================================
# SECURITY: Global Exception Handler - Hide internal errors in production
# ============================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions securely, always include CORS headers"""
    logger.error(f"Unhandled exception: {exc}")
    logger.error(traceback.format_exc())
    
    # Build CORS headers so the browser shows the real error, not "CORS blocked"
    origin = request.headers.get("origin", "")
    cors_headers = {}
    allowed = set(cors_origins)
    if origin in allowed or (allow_origin_regex and __import__("re").match(allow_origin_regex, origin)):
        cors_headers["Access-Control-Allow-Origin"] = origin
        cors_headers["Access-Control-Allow-Credentials"] = "true"
    
    if is_production:
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred. Please try again later."},
            headers=cors_headers,
        )
    else:
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__},
            headers=cors_headers,
        )



@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Editorrah API",
        "version": "2.0.0",
        "environment": "production" if is_production else "development",
        "database": "connected" if database is not None else "not connected"
    }


@app.get("/health")
async def health_check():
    """Detailed health check for Railway"""
    return {
        "status": "healthy",
        "checks": {
            "api": "ok",
            "database": "ok" if database is not None else "not connected",
            "memory": "ok"
        }
    }


@app.get("/api/config")
async def public_config():
    """Public runtime config the frontend reads at startup.

    `integrity_legacy_mode` is the student-visibility revert switch: when true,
    students see their individual integrity signals (trust, stylometry, AI)
    again. The composite score no longer exists and cannot be restored by this
    flag. Flipping the INTEGRITY_LEGACY_MODE env var changes this with no
    rebuild required.
    """
    from .services.integrity_visibility import legacy_mode
    return {"integrity_legacy_mode": legacy_mode()}


# Dependency injection for database
async def get_database():
    return database

# Force rebuild 1768393369
