# DocuFlow API process

The HTTP API is the `docuflow` Python package.

Local:

```bash
uv run uvicorn docuflow.main:app --host 127.0.0.1 --port 43124
```

Render start command:

```
uvicorn docuflow.main:app --host 0.0.0.0 --port $PORT
```

Pre-deploy (once per release):

```
alembic upgrade head
```
