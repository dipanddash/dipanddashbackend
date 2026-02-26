# API Load Testing

## Run with 200 concurrent users

From `food/`:

```powershell
locust -f locustfile.py --host http://127.0.0.1:8000 --users 200 --spawn-rate 20 --run-time 5m --headless --csv loadtest_200
```

## Optional: include authenticated APIs

Set a valid JWT before starting Locust:

```powershell
$env:LOCUST_BEARER_TOKEN="YOUR_ACCESS_TOKEN"
```

Then run the same command above.

## What to check after run

- `loadtest_200_stats.csv`: average/p95/p99 response times.
- `loadtest_200_failures.csv`: endpoints failing under load.
- `loadtest_200_stats_history.csv`: whether latency gets worse over time.

If p95 keeps rising or failure rate is above 1%, your server/database capacity is saturated for that workload.
