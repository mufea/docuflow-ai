# DocuFlow API process

The HTTP API is the `docuflow` Python package.

Local:

```bash
uv run uvicorn docuflow.main:app --host 127.0.0.1 --port 43124
```

Render start command (Free web cannot use `preDeployCommand`):

```
python -m docuflow.migrate && uvicorn docuflow.main:app --host 0.0.0.0 --port $PORT
```
