# rate-limiter

A distributed rate limiter built on FastAPI and Redis, implementing the token
bucket algorithm with atomic Lua scripting. Built to explore how production API
gateways enforce request limits correctly under concurrency.

## Why this exists

Rate limiting looks trivial until you run it under concurrent load. The naive
"read the count, check it, increment it" approach has a race condition: multiple
requests read the same count before any of them increments, so far more requests
slip through than the limit allows. This project builds that broken version
first, measures the failure, then fixes it — because the fix is the interesting
part.

## What it does

- Token bucket rate limiting (burst capacity + sustained refill rate)
- Atomic enforcement via Redis Lua scripts — no race conditions under concurrency
- Lazy refill: tokens are computed on read, not topped up by a background job
- Standard rate-limit response headers (`Retry-After`, `X-RateLimit-*`)
- Per-key buckets, keyed by API key

## The concurrency problem (and the fix)

The first implementation used three separate Redis calls per request: `GET` the
count, compare it to the limit, then `INCR`. Under a concurrent burst this races —
requests read a stale count in the gap between `GET` and `INCR` and are allowed
through when they shouldn't be.

I measured this with a script firing 100 concurrent requests against a limit of 10:

| Implementation                | Allowed | Over limit |
|-------------------------------|---------|------------|
| Naive (GET / check / INCR)    | 10      | 8          |
| Atomic (Lua script)           | 10      | 0          |

The fix moves the entire read-check-increment sequence into a single Lua script.
Redis executes Lua scripts atomically — it runs commands single-threaded, so no
other client can interleave mid-script. The race window disappears. Same load,
zero leakage.

## Token bucket

Fixed-window counting has a boundary problem (a client can burst at the edge of
two windows) and can't express "allow a burst, then throttle." Token bucket can:

- **Capacity** — max tokens = burst size
- **Refill rate** — tokens added per second = sustained rate

Tokens refill lazily: instead of a background job topping up every bucket, the
script calculates how many tokens should have accrued since the bucket was last
touched (`elapsed * refill_rate`, capped at capacity) at the moment of each
request. Each bucket stores only its token count and last-refill timestamp.

## Response headers

Every response carries the client's remaining budget; rejections tell the client
when to retry:

- `X-RateLimit-Limit` — total capacity
- `X-RateLimit-Remaining` — tokens left right now
- `Retry-After` — seconds until a token is available (on 429s)

## Design decisions & tradeoffs

- **Token bucket over fixed window** — supports controlled bursting and avoids
  the window-boundary burst problem. It's what Stripe and AWS use.
- **Lua over `MULTI`/`WATCH`** — Lua gives atomicity without an
  optimistic-locking retry loop. Simpler and no retries on contention.
- **`now` passed in from Python, not read inside Lua** — keeps the time source in
  one place and makes the script testable with a fixed timestamp. Tradeoff: in a
  multi-server deployment this assumes app servers' clocks are roughly in sync;
  clock skew would affect refill timing.
- **`Retry-After` rounds up** — rounding down could tell a client to retry before
  a token has actually refilled, causing an immediate second rejection.

## Performance

Load tested with [k6](https://k6.io): 50 concurrent virtual users over 45s, ramping.

Environment: single API container + Redis via Docker Compose on a developer
laptop. Load generator, API, and Redis shared one machine, so these are relative
benchmarks, not production capacity.

| Metric          | Result        |
|-----------------|---------------|
| Throughput      | ~5,600 req/s  |
| Requests served | 253,022       |
| Latency p50     | 7.8 ms        |
| Latency p95     | 10.2 ms       |
| Latency p99     | 19.4 ms       |
| Failed requests | 0 (0.00%)     |

## Running it

```bash
docker compose up --build
```

The API listens on `http://localhost:8000`. Try it:

```bash
curl -i -H "x-api-key: test123" http://localhost:8000/limited
```

Watch `X-RateLimit-Remaining` count down; after the limit, you'll get a `429`
with a `Retry-After` header.

## Stack

FastAPI · Redis · Lua · Docker · k6 (load testing)