# AI Recruitment Screening System — Technical Overview

This document describes what the system implements from an engineering perspective: orchestration, agents, MCP tools, data paths, and supporting services. It is not a step-by-step setup guide.

## Purpose

The project is a **multi-agent recruitment screening pipeline** that ingests job postings and candidate CVs, produces structured profiles, scores fit against roles, ranks candidates in narrative form, and generates interview-style prompts. The design emphasizes **explicit orchestration** (LangGraph), **tool-backed I/O** (MCP and gRPC), **local LLM inference** (Ollama), and **traceability** of agent steps.

## Repository Layout

| Area | Role |
|------|------|
| `recruiter_platform_backend/api_server` | FastAPI application: LangGraph screening graph, REST/WebSocket API, async SQLAlchemy + PostgreSQL (pgvector), MinIO for CV objects, gRPC **RecruitmentData** servicer as a DB/object-store facade, optional MCP client for CV parsing. |
| `recruiter_platform_backend/mcp_server` | Standalone **Model Context Protocol** server (FastMCP, streamable HTTP): tools that call the API over **gRPC** and **LlamaCloud** for structured PDF parsing. |
| `recruiter_platform_web` | Next.js UI for recruiters (jobs, candidates, screening progress). |
| `docker-compose.yml` | PostgreSQL (pgvector) and MinIO for local infrastructure. |

## Orchestration: LangGraph

Screening is implemented as a **compiled LangGraph** workflow (`langgraph`), not ad-hoc scripts.

- **State schema** (`ScreeningState`): typed shared state including `job_id`, `screening_run_id`, `candidate_ids`, per-phase string summaries (`parse_notes`, `match_summary`, `ranking_summary`, `interview_summary`), LangChain `messages` with `add_messages` reducers, and a `needs_reparse` flag for conditional routing.
- **Graph construction** (`build_screening_graph`): builds a `StateGraph(ScreeningState)` with four nodes wired as:

  1. `START` → `cv_parser`
  2. `cv_parser` → `skill_matcher`
  3. `skill_matcher` → **conditional**: if `needs_reparse` then back to `cv_parser`, else `ranker`
  4. `ranker` → `interview`
  5. `interview` → `END`

- **Execution**: the compiled graph is invoked asynchronously (`ainvoke`) from background tasks when a screening run is scheduled, with progress surfaced via WebSocket broadcast and structured trace events.

- **LLM binding**: nodes share a `ChatOllama` instance (`langchain-ollama`) configured from application settings (base URL and chat model).

The historical module path `app.graph.screening_graph` re-exports the builder from `app.agents.graph_builder` for a stable import surface.

## Agents (Graph Nodes)

Each node is a factory that closes over **ScreeningGraphDeps** (database session factory, broadcaster, MinIO handle, LLM).

### 1. CV Parser (`cv_parser`)

- **Primary external capability**: calls the MCP tool **`parse_candidate_cv_structured`** over streamable HTTP (`mcp` Python client + `httpx`), using `job_id` and `candidate_id` arguments.
- **Downstream logic**: normalizes MCP JSON into structured profiles, runs an additional **recruiter-brief** LLM pass (`run_cv_parser_recruiter_brief`), persists parse results on candidates, and emits parse notes for later nodes.
- **Tracing**: logs agent steps with structured `trace` payloads (inputs, tool calls, outputs).

### 2. Skill Matcher (`skill_matcher`)

- **Does not call MCP in the current API path**; it uses **in-process services**:
  - `compute_job_candidate_fit` for token overlap / fit scores vs the job posting.
  - `top_k_chunks_for_job_candidate` for **pgvector** retrieval over chunked CV/job text.
- **LLM**: builds a system prompt from fit scores, parse notes, and retrieved chunks; summarizes alignment and gaps (`ChatOllama`).
- **Persistence**: merges `job_fit` blobs into candidate `parse_result` for the UI and later reasoning.

### 3. Ranker (`ranker`)

- **LLM-only qualitative step**: consumes the skill matcher’s `match_summary` and produces an ordering / rationale narrative (`build_ranker_prompt`).

### 4. Interview (`interview`)

- **LLM**: system + human messages built from match, ranking, and parse notes to produce **interview-style questions**; marks the screening run complete in the database when successful.

## MCP Server: Transport and Tools

The MCP process is a **FastMCP** application (`mcp.server.fastmcp`) exposing tools over **streamable HTTP** (suitable for programmatic clients and IDE integrations).

Tools are registered in `mcp_server/app/tools/__init__.py`. Each tool is async where needed and returns strings (often JSON) for the MCP contract.

| MCP tool name | What it executes |
|---------------|------------------|
| **`parse_candidate_cv_structured`** | gRPC **`GetCandidateCvPdf`** to the API (PDF bytes + display name), then **LlamaCloud** structured parsing (`llama_parse_cv` HTTP client) using `LLAMA_CLOUD_API_KEY`. Returns JSON: `structured` profile, `structured_summary`, `display_name`, or `error`. |
| **`db_get_job`** | gRPC **`GetJob`**: authoritative job title, company, plain description, embedding flag. |
| **`db_list_candidates`** | gRPC **`ListCandidates`**: candidate ids, display names, CV storage keys for a job. |
| **`compute_candidate_job_fit`** | gRPC **`ComputeCandidateJobFit`**: 0–100 style score, matched/missing skill tokens, summary line — same conceptual fit as used inside the API’s skill matcher path. |

**Integration note:** the LangGraph **CV Parser node** is wired to **`parse_candidate_cv_structured` only**. The other MCP tools (`db_get_job`, `db_list_candidates`, `compute_candidate_job_fit`) exist so external MCP clients (or future agent refactors) can reason over the same gRPC-backed data plane without going through REST.

## API ↔ MCP ↔ gRPC Data Plane

- The **API server** implements **gRPC** `RecruitmentData` handlers (`recruitment_servicer.py`): jobs, candidate lists, CV PDF bytes from MinIO, and job–candidate fit computation backed by PostgreSQL and services.
- The **MCP server** uses generated protobuf stubs (`recruitment.v1`) and a shared gRPC channel helper to talk to that API.
- **CV parsing** therefore follows: **API graph node → MCP HTTP → MCP tool → gRPC GetCandidateCvPdf → LlamaCloud parse → JSON back to API**, where the API persists structured results and continues the graph.

## Additional Backend Capabilities

- **Embeddings and chunking**: LlamaIndex-related dependencies on the API server support embeddings (e.g. Ollama embeddings) and file reading; vector search feeds the skill matcher context.
- **Storage**: CV PDFs and related objects use **MinIO** (S3-compatible) via a storage service.
- **Observability**: `log_agent_step` persists rows (e.g. `AgentStep`) with JSON payloads; `app.agents.tracing` mirrors structured traces to a dedicated logger and optional rotating file (`agent_traces.log`) for audit-style review.
- **Real-time UI**: WebSocket broadcasting publishes coarse-grained screening phases (parsing, matching, ranking, interview generation, errors).

## Frontend

`recruiter_platform_web` is a **Next.js** application (React 19, TanStack Query, Tailwind/shadcn-style stack) that consumes the API for recruiter workflows and live updates where wired.

## Technology Summary

| Layer | Technologies |
|-------|----------------|
| Multi-agent orchestration | **LangGraph**, **LangChain Core** messages |
| LLM | **Ollama** via **langchain-ollama** |
| Agent I/O (CV parse) | **MCP** (streamable HTTP), **FastMCP** |
| Structured CV extraction (MCP path) | **LlamaCloud** parsing API |
| API & persistence | **FastAPI**, **SQLAlchemy 2** (async), **Alembic**, **PostgreSQL** + **pgvector** |
| Object storage | **MinIO** / S3 API (**boto3**) |
| Internal RPC facade | **gRPC** (`grpcio`), protobuf-generated servicers |
| Web | **Next.js** |

## Testing

Automated tests under `api_server/tests` cover areas such as MCP client response shaping, CV parser agent schema expectations, text chunking, and related contracts — reflecting emphasis on **parse and tool boundaries**, not only happy-path LLM text.

---

This overview aligns with the product narrative in `PROJECT_INFO.MD` while grounding it in the **actual** graph, agents, MCP tool surface, and integration boundaries implemented in this repository.
