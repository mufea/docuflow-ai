# DocuFlow worker process

The worker shares the `docuflow` package with the API.

```bash
JOB_BROKER=rq uv run python -m docuflow.worker
```

It consumes job IDs from Redis (RQ) and records status in PostgreSQL.
