# DocuFlow worker process

The worker shares the `docuflow` package with the API.

The default cost-efficient Render stack does **not** deploy this process.
Keep `JOB_BROKER=inline` on the API and skip the paid worker until queue-based
scaling is required. See `infra/render.scaling.yaml`.

```bash
JOB_BROKER=rq uv run python -m docuflow.worker
```

It consumes job IDs from Redis (RQ) and records status in PostgreSQL. Redis is
not used when `JOB_BROKER=inline`.
