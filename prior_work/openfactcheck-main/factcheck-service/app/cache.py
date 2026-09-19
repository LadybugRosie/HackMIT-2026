import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Dict, Iterable, Optional

from redis.asyncio import Redis

from .settings import settings


class _MemoryStore:
    """In-process stand-in for Redis, used when Redis is unreachable.

    Expiry alone is not enough to bound this store: `_purge` only evicts the
    single key being read, so an entry written and never read again would live
    for the whole process lifetime (CACHE_TTL_SECONDS defaults to 7 days). Since
    the service falls back here silently on a Redis outage, that turned an
    outage into a slow memory leak. A full sweep plus a hard entry cap keeps it
    bounded; insertion order makes the overflow eviction FIFO.
    """

    def __init__(self) -> None:
        self._data: "OrderedDict[str, tuple[str, Optional[float]]]" = OrderedDict()
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def _purge(self, key: str) -> None:
        value = self._data.get(key)
        if not value:
            return
        _, expires_at = value
        if expires_at is not None and expires_at <= time.time():
            self._data.pop(key, None)

    def _sweep_locked(self) -> None:
        """Drop every expired entry, then any excess by insertion order."""
        now = time.monotonic()
        if now - self._last_sweep >= settings.MEMORY_CACHE_SWEEP_SECONDS:
            self._last_sweep = now
            wall = time.time()
            for key in [
                k for k, (_, exp) in self._data.items()
                if exp is not None and exp <= wall
            ]:
                self._data.pop(key, None)
        while len(self._data) > settings.MEMORY_CACHE_MAX_ENTRIES:
            self._data.popitem(last=False)

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            self._purge(key)
            value = self._data.get(key)
            return value[0] if value else None

    def mget(self, keys: Iterable[str]) -> list[Optional[str]]:
        return [self.get(key) for key in keys]

    def setex(self, key: str, ttl: int, value: str) -> None:
        expires_at = time.time() + ttl if ttl else None
        with self._lock:
            self._data[key] = (value, expires_at)
            self._data.move_to_end(key)
            self._sweep_locked()

    def incr(self, key: str) -> int:
        with self._lock:
            self._purge(key)
            value = self._data.get(key)
            current = int(value[0]) if value else 0
            current += 1
            self._data[key] = (str(current), value[1] if value else None)
            self._sweep_locked()
            return current

    def expire(self, key: str, ttl: int) -> None:
        with self._lock:
            if key in self._data:
                self._data[key] = (self._data[key][0], time.time() + ttl)

    def ping(self) -> bool:
        return True


class _AsyncMemoryRedis:
    def __init__(self, store: _MemoryStore) -> None:
        self._store = store

    async def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    async def mget(self, keys: Iterable[str]) -> list[Optional[str]]:
        return self._store.mget(keys)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store.setex(key, ttl, value)

    async def incr(self, key: str) -> int:
        return self._store.incr(key)

    async def expire(self, key: str, ttl: int) -> None:
        self._store.expire(key, ttl)

    async def ping(self) -> bool:
        return self._store.ping()

    def pipeline(self):
        return _AsyncMemoryPipeline(self._store)


class _AsyncMemoryPipeline:
    def __init__(self, store: _MemoryStore) -> None:
        self._store = store
        self._ops: list[tuple[str, int, str]] = []

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._ops.append((key, ttl, value))

    async def execute(self) -> None:
        for key, ttl, value in self._ops:
            self._store.setex(key, ttl, value)
        self._ops = []


class _SyncMemoryPipeline:
    def __init__(self, store: _MemoryStore) -> None:
        self._store = store
        self._ops: list[tuple[str, int, str]] = []

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._ops.append((key, ttl, value))

    def execute(self) -> None:
        for key, ttl, value in self._ops:
            self._store.setex(key, ttl, value)
        self._ops = []


class _SyncMemoryRedis:
    def __init__(self, store: _MemoryStore) -> None:
        self._store = store

    def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def mget(self, keys: Iterable[str]) -> list[Optional[str]]:
        return self._store.mget(keys)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._store.setex(key, ttl, value)

    def incr(self, key: str) -> int:
        return self._store.incr(key)

    def expire(self, key: str, ttl: int) -> None:
        self._store.expire(key, ttl)

    def ping(self) -> bool:
        return self._store.ping()

    def pipeline(self):
        return _SyncMemoryPipeline(self._store)


_redis: Optional[Redis] = None
_memory_store: Optional[_MemoryStore] = None
_use_memory_fallback: bool = False


def _get_memory_store() -> _MemoryStore:
    global _memory_store
    if _memory_store is None:
        _memory_store = _MemoryStore()
    return _memory_store


def set_memory_fallback() -> None:
    """Force using memory cache (called when Redis is unavailable)."""
    global _use_memory_fallback
    _use_memory_fallback = True


def get_redis() -> Redis:
    global _redis
    global _use_memory_fallback
    
    # Use memory if explicitly configured or if Redis failed
    if settings.REDIS_URL.startswith("memory://") or _use_memory_fallback:
        return _AsyncMemoryRedis(_get_memory_store())  # type: ignore[return-value]
    
    if _redis is None:
        _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def get_sync_redis():
    global _use_memory_fallback
    
    if settings.REDIS_URL.startswith("memory://") or _use_memory_fallback:
        return _SyncMemoryRedis(_get_memory_store())
    
    from redis import Redis as SyncRedis
    return SyncRedis.from_url(settings.REDIS_URL, decode_responses=True)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def claim_cache_key(claim: str, evidence_mode: str, context: Optional[str]) -> str:
    context_hash = _hash_text(context or "")
    raw = f"{claim}|{evidence_mode}|{context_hash}"
    return f"claim:{_hash_text(raw)}"


def doi_cache_key(doi: str) -> str:
    """Generate cache key for DOI result."""
    return f"doi:{_hash_text(doi.lower())}"


def url_cache_key(url: str) -> str:
    """Generate cache key for URL result."""
    return f"url:{_hash_text(url)}"


def wikipedia_cache_key(claim: str) -> str:
    """Generate cache key for Wikipedia evidence."""
    return f"wiki:{_hash_text(claim)}"


async def get_cached_claims(keys: Iterable[str]) -> Dict[str, dict]:
    keys_list = list(keys)
    if not keys_list:
        return {}
    redis = get_redis()
    values = await redis.mget(keys_list)
    results: Dict[str, dict] = {}
    for key, value in zip(keys_list, values):
        if value:
            results[key] = json.loads(value)
    return results


async def set_cached_claims(items: Dict[str, dict]) -> None:
    if not items:
        return
    redis = get_redis()
    pipe = redis.pipeline()
    for key, value in items.items():
        pipe.setex(key, settings.CACHE_TTL_SECONDS, json.dumps(value))
    await pipe.execute()


async def get_cached_doi(key: str) -> Optional[dict]:
    """Get cached DOI result."""
    redis = get_redis()
    value = await redis.get(key)
    if value:
        return json.loads(value)
    return None


async def set_cached_doi(key: str, result: dict) -> None:
    """Cache DOI result with TTL."""
    redis = get_redis()
    await redis.setex(key, settings.CACHE_TTL_SECONDS, json.dumps(result))


async def get_cached_url(key: str) -> Optional[dict]:
    """Get cached URL result."""
    redis = get_redis()
    value = await redis.get(key)
    if value:
        return json.loads(value)
    return None


async def set_cached_url(key: str, result: dict) -> None:
    """Cache URL result with TTL."""
    redis = get_redis()
    await redis.setex(key, settings.CACHE_TTL_SECONDS, json.dumps(result))


async def get_cached_wikipedia(key: str) -> Optional[list]:
    """Get cached Wikipedia evidence."""
    redis = get_redis()
    value = await redis.get(key)
    if value:
        return json.loads(value)
    return None


async def set_cached_wikipedia(key: str, evidence: list) -> None:
    """Cache Wikipedia evidence with 7-day TTL."""
    redis = get_redis()
    # Use 7-day TTL for Wikipedia results
    await redis.setex(key, settings.CACHE_TTL_SECONDS, json.dumps(evidence))
