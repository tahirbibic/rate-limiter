## Performance

Load tested with [k6](https://k6.io): 50 concurrent virtual users, 45s, ramping.

Environment: single API container + Redis via Docker Compose on a developer
laptop (Windows). The load generator, API, and Redis all shared one machine,
so these are relative benchmarks, not production capacity numbers.

| Metric              | Result          |
|---------------------|-----------------|
| Throughput          | ~5,600 req/s    |
| Requests served     | 253,022         |
| Latency p50         | 7.8 ms          |
| Latency p95         | 10.2 ms         |
| Latency p99         | 19.4 ms         |
| Failed requests     | 0 (0.00%)       |

The token-bucket check (atomic Redis Lua script) added single-digit
millisecond latency at the p50/p95 level under sustained concurrent load.