# Recruitment platform — backend

This folder contains two Python services:

| Service | Role |
|--------|------|
| **`api_server/`** | FastAPI REST API, async PostgreSQL, MinIO uploads, LangGraph screening, gRPC `RecruitmentData` facade, WebSockets for screening progress |
| **`mcp_server/`** | FastMCP server exposing tools (jobs, candidates, job–CV fit, structured CV parse) that call the API over **gRPC** (and LlamaCloud where needed) |

The repository root also has **`docker-compose.yml`** (PostgreSQL + pgvector, MinIO) used by both services.

---

## Prerequisites

- **Python 3.13+** (see each service’s `pyproject.toml`)
- **[uv](https://docs.astral.sh/uv/)** (recommended) or `pip` + `venv`
- **Docker Desktop** (or Docker Engine + Compose) for Postgres and MinIO
- **[Ollama](https://ollama.com/)** running locally for chat + embeddings used by screening
- **LlamaCloud API key** ([LlamaIndex Cloud](https://cloud.llamaindex.ai)) — required for PDF → markdown / structured CV parsing

Optional:

- **GNU Make** — only if you use the Makefiles to regenerate gRPC code from protos

---

## 1. Start infrastructure (Postgres + MinIO)

From the **repository root** (parent of `recruiter_platform_backend/`):

```bash
docker compose up -d
```

Defaults:

| Service    | Host port | Notes |
|-----------|-----------|--------|
| PostgreSQL (pgvector) | **5433** → 5432 in container | User `recruit`, password `recruit`, database `recruitment` |
| MinIO API | **9000** | S3-compatible API |
| MinIO console | **9001** | Web UI |

Wait until Postgres is healthy (`docker compose ps`).

---

## 2. Configure the API server (`api_server/`)

### 2.1 Install dependencies

```bash
cd recruiter_platform_backend/api_server
uv sync --all-groups
```

(`--all-groups` includes dev tools such as `grpcio-tools` and pytest.)

### 2.2 Environment file

Copy the example env and edit values as needed:

```bash
cp .env.example .env
```

On Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

**Minimum to set:**

| Variable | Purpose |
|----------|---------|
| `DB_URL` | Async SQLAlchemy URL; default points at Docker Postgres on `127.0.0.1:5433` |
| `LLAMA_CLOUD_API_KEY` | **Required** for CV upload / parsing (without it, ingest fails) |
| `MINIO_*` | Must match MinIO; defaults align with `docker-compose.yml` |
| `OLLAMA_BASE_URL` | Default `http://127.0.0.1:11434` |
| `OLLAMA_CHAT_MODEL` / `OLLAMA_EMBED_MODEL` | Models you have pulled in Ollama |
| `CORS_ALLOW_ORIGINS` | Browser origins allowed to call the API (e.g. Next.js on port 3000) |

Optional: `LLAMA_CLOUD_ORGANIZATION_ID`, `LLAMA_CLOUD_PROJECT_ID`, parse timeouts, `CV_PREVIEW_*`, etc. — see `app/core/config.py` and `.env.example`.

**`MCP_CV_TOOLS_URL`** — screening **`cv_parser`** always calls the MCP tool **`parse_candidate_cv_structured`** at this streamable-HTTP URL (default **`http://127.0.0.1:8765/mcp`** — avoid a trailing slash; FastMCP may **307**-redirect **`/mcp/`** to **`/mcp`**, which breaks the MCP HTTP client). LlamaCloud runs **inside the MCP server**; set **`LLAMA_CLOUD_API_KEY`** in **`mcp_server/.env`**. With **`MCP_CV_AUTO_START=true`** (default), the API starts MCP on that loopback port after gRPC is up (**`uv`** must be on your PATH). Set **`MCP_CV_AUTO_START=false`** to run MCP yourself from **`mcp_server/`** (see section 3.4). If the API runs in Docker and MCP on the host, use **`http://host.docker.internal:8765/mcp`** and configure MCP gRPC to reach the API (often **`API_GRPC_HOST=host.docker.internal`**).

You can also copy the repo root **`.env.example`** into `api_server/.env` if you keep one consolidated file; the API loads **`api_server/.env`** via Pydantic settings.

### 2.3 Database migrations

With `DB_URL` correct and Postgres running:

```bash
cd recruiter_platform_backend/api_server
uv run alembic upgrade head
```

### 2.4 Pull Ollama models

Match `OLLAMA_CHAT_MODEL` and `OLLAMA_EMBED_MODEL` in `.env`, for example:

```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

Ensure Ollama is serving:

```bash
ollama serve
```

### 2.5 Run the API

From `recruiter_platform_backend/api_server`:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **REST + OpenAPI:** [http://127.0.0.1:8000](http://127.0.0.1:8000) — docs at `/docs`
- **Health:** `GET /health`
- **gRPC:** listens on **`GRPC_PORT`** (default **50051**), started in the app lifespan together with Uvicorn

The app will try to ensure the MinIO bucket exists on startup; if MinIO is down, uploads may fail until it is reachable.

---

## 3. Configure the MCP server (`mcp_server/`)

The MCP server does **not** open its own database connection; it uses **gRPC** to the API process, which must already be running with a working DB.

### 3.1 Install dependencies

```bash
cd recruiter_platform_backend/mcp_server
uv sync
```

### 3.2 Environment file

```bash
cp .env.example .env
```

Set **`API_GRPC_HOST`** and **`API_GRPC_PORT`** to match the machine where `api_server` is running (defaults `127.0.0.1` and `50051`). Optionally set **`API_GRPC_TARGET`** to a full `host:port` string.

For **`parse_candidate_cv_structured`**, set **`LLAMA_CLOUD_API_KEY`** on the MCP server (same cloud account as ingest). Optional LlamaCloud fields match the API (see `mcp_server/.env.example`).

### 3.3 Run MCP (stdio, for Cursor / Claude Desktop)

From `recruiter_platform_backend/mcp_server`:

```bash
uv run fastmcp run app/main.py --transport stdio
```

### 3.4 Run MCP (streamable HTTP, for `MCP_CV_TOOLS_URL`)

Use a dedicated port (for example **8765**) so it does not clash with the API’s HTTP port:

```bash
cd recruiter_platform_backend/mcp_server
uv run fastmcp run app/main.py --transport streamable-http --host 127.0.0.1 --port 8765
```

Then set **`MCP_CV_TOOLS_URL=http://127.0.0.1:8765/mcp`** in `api_server/.env` (no trailing slash). The API must still be running with gRPC enabled so MCP can call **`GetCandidateCvPdf`** and other `RecruitmentData` RPCs.

Tools are implemented under **`mcp_server/app/tools/`** (one file per tool). They include **`db_get_job`**, **`db_list_candidates`**, **`compute_candidate_job_fit`**, and **`parse_candidate_cv_structured`** (gRPC fetch PDF → LlamaCloud structured JSON).

---

## 4. Regenerating gRPC / protobuf code (contributors)

Protos live under **`contracts/proto/recruitment/v1/recruitment.proto`**. After changing them, regenerate stubs for **both** services.

**API server:**

```bash
cd recruiter_platform_backend/api_server
# With dev deps (grpcio-tools):
uv run make gen-grpc
# Or manually:
uv run python -m grpc_tools.protoc -I "../../contracts/proto" \
  --python_out=app/gen --grpc_python_out=app/gen --pyi_out=app/gen \
  "../../contracts/proto/recruitment/v1/recruitment.proto"
```

**MCP server:**

```bash
cd recruiter_platform_backend/mcp_server
uv run make gen-grpc
```

Ensure `PYTHONPATH` / imports resolve to `app/gen` (see each service’s `main.py` or bootstrap).

---

## 5. Quick verification checklist

1. `docker compose ps` — Postgres and MinIO up  
2. `uv run alembic upgrade head` — migrations applied  
3. `GET http://127.0.0.1:8000/health` — `{"status":"ok"}`  
4. `LLAMA_CLOUD_API_KEY` set — CV upload path works  
5. Ollama models pulled — screening graph can run chat/embed steps  
6. MCP: API running on gRPC port — `compute_candidate_job_fit` returns JSON, not a gRPC error string  
7. MCP on streamable HTTP (default port **8765**) with `LLAMA_CLOUD_API_KEY` on MCP — screening `cv_parser` reaches it via `MCP_CV_TOOLS_URL` (check `logs/agent_traces.log` / agent steps; payloads include `via_mcp: true`)  

---

## 6. Common issues

| Symptom | Things to check |
|--------|------------------|
| DB connection errors | `DB_URL` host/port (`5433` vs local Postgres on `5432`), Docker container health |
| MinIO / upload failures | `MINIO_ENDPOINT`, credentials, bucket name; MinIO UI on port 9001 |
| CV upload 503 / “LLAMA_CLOUD_API_KEY” | Key missing or wrong in `api_server/.env` |
| Screening completes but empty LLM text | Ollama not running, wrong `OLLAMA_BASE_URL`, or model not pulled |
| MCP tools return gRPC errors | API not running, firewall, or `API_GRPC_*` mismatch |
| CORS errors from the web app | `CORS_ALLOW_ORIGINS` / regex in API config |

---

## 7. Project layout (backend)

```
recruiter_platform_backend/
├── README.md                 ← this file
├── api_server/
│   ├── app/
│   │   ├── main.py           # FastAPI + lifespan (gRPC, graph, MinIO)
│   │   ├── api/routes/       # REST routers
│   │   ├── graph/            # LangGraph screening
│   │   ├── rpc/              # gRPC servicer
│   │   └── services/         # DB, MinIO, LlamaParse, fit scoring, etc.
│   ├── alembic/              # Migrations
│   ├── pyproject.toml
│   └── .env.example
└── mcp_server/
    ├── app/
    │   ├── main.py           # FastMCP app + tool registration
    │   ├── tools/            # One module per MCP tool (gRPC + LlamaParse)
    │   ├── services/         # LlamaCloud HTTP helper for parse tool
    │   └── gen/              # Generated gRPC stubs (see Makefile)
    ├── pyproject.toml
    └── .env.example
```

For the **Next.js frontend**, see the separate app under `recruiter_platform_web/` and set `NEXT_PUBLIC_API_URL` (and WebSocket base if applicable) to point at this API.
