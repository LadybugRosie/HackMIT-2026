import time

from fastapi import HTTPException, Request

from .cache import get_redis
from .settings import settings


async def rate_limit(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    api_keys = settings.get_api_keys()
    if api_keys and (not api_key or api_key not in api_keys):
        raise HTTPException(status_code=401, detail="Invalid API key")

    identifier = api_key or (request.client.host if request.client else "unknown")
    window = int(time.time() // 60)
    key = f"rate:{identifier}:{window}"

    redis = get_redis()
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)

    if count > settings.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return identifier
