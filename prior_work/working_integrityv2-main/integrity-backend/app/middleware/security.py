"""
Security Middleware
Implements rate limiting, request validation, and security headers
"""

import os
import time
import hashlib
import re
import logging
from collections import OrderedDict
from functools import wraps
from typing import Callable, Dict, Optional, Tuple
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import html

logger = logging.getLogger(__name__)


# ============================================================================
# RATE LIMITING (Redis-backed with bounded in-memory fallback)
# ============================================================================

_redis_client = None


def initialize_rate_limiter():
    """
    Try to connect to Redis for rate limiting.
    Call during app startup.  Falls back to in-memory if Redis is unavailable.
    """
    global _redis_client
    redis_url = os.getenv("REDIS_URL")
    if not redis_url or redis_url == "memory://":
        logger.info("Rate limiter: using bounded in-memory backend (set REDIS_URL for production)")
        return False
    try:
        import redis
        _redis_client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=3)
        _redis_client.ping()
        logger.info("Rate limiter: connected to Redis")
        return True
    except Exception as e:
        logger.warning(f"Rate limiter: Redis connection failed ({e}), falling back to in-memory")
        _redis_client = None
        return False


class RateLimiter:
    """
    Sliding-window rate limiter.
    Uses Redis when available (works across workers), or a bounded in-memory
    OrderedDict (LRU eviction at 50k entries) for development.
    """
    MAX_MEMORY_ENTRIES = 50_000  # Prevent unbounded memory growth

    def __init__(self):
        # In-memory fallback: OrderedDict for LRU eviction
        self._mem_requests: OrderedDict = OrderedDict()
        self._mem_blocked: OrderedDict = OrderedDict()

    # ------------------------------------------------------------------
    def _get_client_id(self, request: Request) -> str:
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        return hashlib.sha256(f"{client_ip}:{user_agent}".encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Redis-backed implementation
    # ------------------------------------------------------------------
    def _redis_is_allowed(
        self, client_id: str, category: str, max_requests: int, window: int, block_duration: int
    ) -> Tuple[bool, Optional[int]]:
        bucket = f"rl:{client_id}:{category}"
        block_key = f"rl_block:{client_id}:{category}"

        # Check block
        block_ttl = _redis_client.ttl(block_key)
        if block_ttl and block_ttl > 0:
            return False, block_ttl

        now = time.time()
        pipe = _redis_client.pipeline()
        pipe.zremrangebyscore(bucket, 0, now - window)
        pipe.zcard(bucket)
        pipe.zadd(bucket, {str(now): now})
        pipe.expire(bucket, window + 1)
        results = pipe.execute()

        count = results[1]
        if count >= max_requests:
            _redis_client.setex(block_key, block_duration, "1")
            return False, block_duration

        return True, None

    # ------------------------------------------------------------------
    # In-memory fallback (bounded)
    # ------------------------------------------------------------------
    def _mem_is_allowed(
        self, client_id: str, category: str, max_requests: int, window: int, block_duration: int
    ) -> Tuple[bool, Optional[int]]:
        bucket_key = f"{client_id}:{category}"
        now = time.time()

        # Evict oldest entries if we're over the limit
        while len(self._mem_blocked) > self.MAX_MEMORY_ENTRIES:
            self._mem_blocked.popitem(last=False)
        while len(self._mem_requests) > self.MAX_MEMORY_ENTRIES:
            self._mem_requests.popitem(last=False)

        # Check block
        if bucket_key in self._mem_blocked:
            block_end = self._mem_blocked[bucket_key]
            if now < block_end:
                return False, int(block_end - now)
            del self._mem_blocked[bucket_key]

        # Sliding window
        timestamps = self._mem_requests.get(bucket_key, [])
        timestamps = [t for t in timestamps if now - t < window]

        if len(timestamps) >= max_requests:
            self._mem_blocked[bucket_key] = now + block_duration
            self._mem_requests[bucket_key] = timestamps
            return False, block_duration

        timestamps.append(now)
        self._mem_requests[bucket_key] = timestamps
        # Move to end (LRU)
        self._mem_requests.move_to_end(bucket_key)
        return True, None

    # ------------------------------------------------------------------
    def is_allowed(
        self,
        request: Request,
        max_requests: int = 100,
        window: int = 60,
        block_duration: int = 300,
        category: str = "default",
    ) -> Tuple[bool, Optional[int]]:
        client_id = self._get_client_id(request)
        if _redis_client:
            try:
                return self._redis_is_allowed(client_id, category, max_requests, window, block_duration)
            except Exception:
                pass  # Fall through to in-memory
        return self._mem_is_allowed(client_id, category, max_requests, window, block_duration)


# Global rate limiter instance
rate_limiter = RateLimiter()


# Rate limit configurations for different endpoints
RATE_LIMITS = {
    "default": {"max_requests": 100, "window": 60},
    "auth_login": {"max_requests": 5, "window": 60},    # FIX #9: Stricter for login (5/min)
    "auth_signup": {"max_requests": 3, "window": 60},    # 3 signups per minute
    "auth_general": {"max_requests": 30, "window": 60},  # General auth (verify/me)
    "submission": {"max_requests": 30, "window": 60},
    "file_upload": {"max_requests": 20, "window": 60},
    "class_join": {"max_requests": 5, "window": 60},     # FIX #20: Limit class code guessing
    "integrity": {"max_requests": 60, "window": 60},     # Integrity endpoints (frequent)
}


def get_rate_limit_config(path: str) -> dict:
    """Get rate limit config based on path. Returns config dict with 'category' key."""
    # Auth verify/me are called frequently by the SPA router guard
    if "/auth/verify" in path or "/auth/me" in path:
        return {**RATE_LIMITS["auth_general"], "category": "auth_general"}
    if "/auth/login" in path:
        return {**RATE_LIMITS["auth_login"], "category": "auth_login"}
    if "/auth/signup" in path:
        return {**RATE_LIMITS["auth_signup"], "category": "auth_signup"}
    if "/auth/" in path:
        return {**RATE_LIMITS["auth_general"], "category": "auth_general"}
    # FIX #20: Strict limit on class join to prevent brute-force
    if "/classes/join" in path:
        return {**RATE_LIMITS["class_join"], "category": "class_join"}
    if "/integrity/" in path:
        return {**RATE_LIMITS["integrity"], "category": "integrity"}
    if "/submissions" in path:
        return {**RATE_LIMITS["submission"], "category": "submission"}
    if "/upload" in path:
        return {**RATE_LIMITS["file_upload"], "category": "file_upload"}
    return {**RATE_LIMITS["default"], "category": "default"}


# ============================================================================
# INPUT SANITIZATION
# ============================================================================

class InputSanitizer:
    """
    Sanitize user input to prevent XSS and injection attacks
    """
    
    # Patterns for dangerous content
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'data:text/html',
        r'vbscript:',
    ]
    
    @staticmethod
    def sanitize_string(value: str) -> str:
        """Sanitize a string value"""
        if not isinstance(value, str):
            return value
        
        # HTML escape
        sanitized = html.escape(value)
        
        # Remove null bytes
        sanitized = sanitized.replace('\x00', '')
        
        return sanitized
    
    @staticmethod
    def sanitize_html_content(value: str) -> str:
        """
        Sanitize HTML content while preserving safe formatting
        Used for rich text editor content
        """
        if not isinstance(value, str):
            return value
        
        # Remove script tags
        value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove event handlers
        value = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', value, flags=re.IGNORECASE)
        value = re.sub(r'\s*on\w+\s*=\s*\S+', '', value, flags=re.IGNORECASE)
        
        # Remove javascript: URLs
        value = re.sub(r'javascript:', '', value, flags=re.IGNORECASE)
        
        # Remove data: URLs (except images)
        value = re.sub(r'data:(?!image/)[^;]+;', '', value, flags=re.IGNORECASE)
        
        return value
    
    @staticmethod
    def is_safe_input(value: str) -> bool:
        """Check if input contains dangerous patterns"""
        if not isinstance(value, str):
            return True
        
        for pattern in InputSanitizer.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        return True
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize a filename to prevent path traversal"""
        if not filename:
            return filename
        
        # Remove path separators
        filename = filename.replace('/', '_').replace('\\', '_')
        
        # Remove null bytes and other dangerous chars
        filename = re.sub(r'[\x00-\x1f<>:"|?*]', '', filename)
        
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:250] + ('.' + ext if ext else '')
        
        return filename


sanitizer = InputSanitizer()


# ============================================================================
# SECURITY HEADERS MIDDLEWARE
# ============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses
    """
    
    # Paths that serve their own JS/CSS from CDNs (Swagger UI, ReDoc)
    _DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next: Callable):
        if request.method == "OPTIONS":
            return await call_next(request)
        
        response = await call_next(request)
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(self \"https://editorrah.com\" \"https://www.editorrah.com\"), "
            "microphone=(), geolocation=()"
        )
        
        if "/report" in str(request.url.path):
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
        else:
            response.headers["X-Frame-Options"] = "DENY"
        
        # Swagger/ReDoc pages load JS from cdn.jsdelivr.net — don't restrict them
        if request.url.path not in self._DOCS_PATHS:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https://*.railway.app https://*.amazonaws.com https://editorrah.com https://*.editorrah.com; "
                "frame-ancestors 'self' http://localhost:* https://editorrah.com https://www.editorrah.com https://*.editorrah.com https://*.railway.app;"
            )
        
        if "server" in response.headers:
            del response.headers["server"]
        
        return response


# ============================================================================
# RATE LIMITING MIDDLEWARE
# ============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Apply rate limiting to requests
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Skip rate limiting for health checks and CORS preflight
        if request.url.path in ["/health", "/api/health", "/"]:
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        config = get_rate_limit_config(request.url.path)
        is_allowed, retry_after = rate_limiter.is_allowed(
            request,
            max_requests=config["max_requests"],
            window=config["window"],
            category=config["category"]
        )
        
        if not is_allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )
        
        return await call_next(request)


# ============================================================================
# REQUEST SIZE VALIDATION
# ============================================================================

class RequestSizeMiddleware(BaseHTTPMiddleware):
    """
    Validate request body size
    """
    
    MAX_BODY_SIZE = 10 * 1024 * 1024  # 10MB default
    MAX_JSON_SIZE = 5 * 1024 * 1024   # 5MB for JSON (integrity data can be large)
    MAX_VIDEO_SIZE = 80 * 1024 * 1024  # 80MB for session-replay video uploads only
    MAX_HALLUCINATION_SIZE = 100 * 1024 * 1024  # 100MB for hallucination document uploads

    async def dispatch(self, request: Request, call_next: Callable):
        if request.method == "OPTIONS":
            return await call_next(request)

        content_length = request.headers.get("content-length")
        content_type = request.headers.get("content-type", "")

        if content_length:
            size = int(content_length)
            if request.url.path.endswith("/video") and request.url.path.startswith("/api/research/"):
                max_size = self.MAX_VIDEO_SIZE
            elif request.url.path.startswith("/api/hallucination/check-file"):
                max_size = self.MAX_HALLUCINATION_SIZE
            else:
                max_size = self.MAX_JSON_SIZE if "json" in content_type else self.MAX_BODY_SIZE
            
            if size > max_size:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": f"Request too large. Maximum size: {max_size // 1024 // 1024}MB"}
                )
        
        return await call_next(request)


# ============================================================================
# HELPER DECORATORS
# ============================================================================

def validate_input(func: Callable) -> Callable:
    """
    Decorator to validate and sanitize input
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Sanitize string arguments
        sanitized_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, str):
                if not sanitizer.is_safe_input(value):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid input detected in field: {key}"
                    )
                sanitized_kwargs[key] = sanitizer.sanitize_string(value)
            else:
                sanitized_kwargs[key] = value
        
        return await func(*args, **sanitized_kwargs)
    
    return wrapper


def require_https(func: Callable) -> Callable:
    """
    Decorator to require HTTPS in production
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        # Skip in development
        if request.url.scheme == "http" and request.client.host not in ["127.0.0.1", "localhost"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="HTTPS required"
            )
        return await func(request, *args, **kwargs)
    
    return wrapper
