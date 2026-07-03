import os
from fastapi import FastAPI, Header, HTTPException, Response
from redis.asyncio import Redis
from app.limiter.fixed_window_atomic import check

app = FastAPI(title="Rate Limiter")
redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

@app.get("/health")
async def health():
    pong = await redis.ping()
    return {"status": "ok", "redis": pong}

@app.get("/limited")
async def limited(response: Response, x_api_key: str = Header(...)):
    capacity, refill_rate = 10, 1
    allowed, remaining, retry_after = await check(redis, x_api_key, capacity, refill_rate)

    response.headers["X-RateLimit-Limit"] = str(capacity)
    response.headers["X-RateLimit-Remaining"] = str(remaining)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(capacity),
                "X-RateLimit-Remaining": str(remaining),
            },
        )

    return {"message": "request allowed"}

@app.get("/loadtest")
async def loadtest(response: Response, x_api_key: str = Header(...)):
    allowed, remaining, retry_after = await check(redis, x_api_key, capacity=1_000_000, refill_rate=100_000)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return {"message": "ok"}