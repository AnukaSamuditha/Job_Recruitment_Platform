# Contracts (protobuf)

Proto definitions for **gRPC only** where MCP tools need PostgreSQL-backed data.

This folder can later be replaced by or synced with a Git submodule pointing at a shared `contracts` repository.

- `proto/recruitment/v1/recruitment.proto` — `RecruitmentData` service

Regenerate Python stubs from `recruiter_platform_backend/api_server` or `mcp_server` using the project `Makefile` (`make gen-grpc`).
