# Deployment and reproducibility

Project 1 is packaged as a Python 3.11 application and includes a minimal container image. The
primary deployment path is a **single container on a trusted host** with two mounted paths:
one for operator-supplied PDFs and one for the persistent SQLite index. This matches the
current local path-based ingestion API and avoids pretending the service is ready for an
unauthenticated public internet deployment.

## Local Python process

```powershell
python -m pip install -e .
$env:OPENAI_API_KEY = "your-key"
madi-api --host 127.0.0.1 --port 8000
```

The default loopback bind is the safest developer setting. Health does not require provider
credentials; indexing, retrieval, and generation do.

## Container image

Build from `01_company_document_intelligence/`:

```powershell
docker build -t madi-company-intelligence:1.0.0 .
```

Create the synthetic demo PDF on the host, then run the container:

```powershell
madi-create-demo-pdf

docker run --rm -p 8000:8000 `
  --env OPENAI_API_KEY=$env:OPENAI_API_KEY `
  --mount type=bind,source="$PWD/data/raw",target=/app/data/raw,readonly `
  --mount type=bind,source="$PWD/artifacts",target=/app/artifacts `
  madi-company-intelligence:1.0.0
```

The image:

- uses the official slim Python 3.11 base image;
- installs only runtime dependencies;
- runs as a non-root user;
- stores no credential in an image layer;
- starts Uvicorn through the `madi-api` entry point;
- exposes a container health check against `/health`;
- expects documents and the index through mounted paths.

The `.dockerignore` excludes environments, caches, secrets, raw data, indexes, tests, and local
artifacts from the build context.

## Environment

Use `.env.example` as the complete reference. The application does not auto-load `.env`; a
process manager or container runtime must inject values. Never place a key in the Dockerfile,
image, command history, or committed configuration. For a durable container, persist:

- `MADI_DOCUMENT_ROOT` (default `/app/data/raw` in the image);
- the parent directory of `MADI_VECTOR_DB_PATH` (default `/app/artifacts`).

The embedding model, dimension, and existing index manifest must agree. Changing the model or
dimension requires rebuilding the index.

## Hosted-platform boundary

Render, Railway, Fly.io, and similar services can run this container with persistent storage,
but the current path-reference ingestion endpoint assumes an operator can place a PDF in the
mounted document directory. The API has no upload endpoint, authentication, TLS termination,
or rate limiting. A public hosted demo therefore needs a separate trusted document-loading
mechanism and platform controls. Those concerns are documented rather than hidden behind an
unsafe sample configuration.

## Operational limits

- SQLite exact vector search is intended for a local or modest corpus and one service replica.
- Multiple replicas must not write independently to the same local SQLite file.
- Provider calls are synchronous, have a 30-second default timeout, and use at most two SDK
  retries.
- Reverse proxies should enforce body limits even though the API checks declared body size.
- Logs intentionally omit documents, prompts, credentials, local paths, and full model output.

Project 1 demonstrates a deployment-ready boundary and reproducible image. It does not claim
enterprise availability, multi-tenancy, or public-service security.
