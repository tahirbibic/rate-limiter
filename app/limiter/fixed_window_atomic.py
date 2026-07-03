import time
from redis.asyncio import Redis
import math

LUA_SCRIPT = """
local capacity    = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now         = tonumber(ARGV[3])

local state       = redis.call('HMGET', KEYS[1], 'tokens', 'last_refill')
local tokens      = tonumber(state[1])
local last_refill = tonumber(state[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

local elapsed = now - last_refill
    tokens = math.min(capacity, tokens + elapsed * refill_rate)

    local allowed
    if tokens >= 1 then
        tokens = tokens - 1
        allowed = 1
    else
        allowed = 0
    end

redis.call('HSET', KEYS[1], 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', KEYS[1], math.ceil(capacity / refill_rate) * 2)

return {allowed, math.floor(tokens)}
"""

async def is_allowed(
    redis: Redis,
    api_key: str,
    capacity: int,
    refill_rate: float,
) -> bool:
    key = f"ratelimit:bucket:{api_key}"
    result = await redis.eval(
        LUA_SCRIPT,
        1,
        key,
        capacity,
        refill_rate,
        time.time(),
    )
    return result == 1

async def check(
    redis: Redis,
    api_key: str,
    capacity: int,
    refill_rate: float,
) -> tuple[bool, int, int]:
    """
    Returns (allowed, remaining, retry_after_seconds).
    """
    key = f"ratelimit:bucket:{api_key}"
    allowed, remaining = await redis.eval(
        LUA_SCRIPT, 1, key, capacity, refill_rate, time.time(),
    )

    retry_after = math.ceil(1 / refill_rate)

    return bool(allowed), remaining, retry_after