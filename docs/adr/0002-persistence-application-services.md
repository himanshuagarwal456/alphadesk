# ADR 0002: Persistence and application services

**Status:** Accepted
**Date:** 2026-07-18

## Context

AlphaDesk's research engine persisted runs, evidence, theses, and journals as
local JSON/Markdown files. Phase 3 of `docs/alpha-release.md` requires a durable
multi-user product: workspace ownership, restart-safe jobs, an HTTP API, and
migration-managed schema — without abandoning the existing file layouts yet.

## Decision

1. **Optional `[server]` extra.** FastAPI, SQLAlchemy, Alembic, and Postgres
   drivers stay out of the core CLI install. `pip install "alphadesk[server]"`.
2. **Workspace-scoped rows.** Every user-owned table carries `workspace_id`
   with unique constraints of the form `(workspace_id, id)`. Auth (phase 4,
   delivered late per `docs/alpha-release.md` §12) will bind callers to
   memberships; until then the API accepts `X-Workspace-Id`.
3. **Canonical Pydantic payloads in JSON columns.** Indexed columns support
   queries (`symbol`, `status`, …); the full domain object lives in `payload`
   so schema evolution stays additive.
4. **Durable job status + run events.** `AnalysisRun.status` uses the Phase 3
   lifecycle enum; `run_events` is an append-only progress stream for the UI.
5. **Local object store with a narrow protocol.** Documents and raw artifacts
   go under `ALPHADESK_OBJECT_STORE_DIR`; an S3 backend can replace it later.
6. **Compatibility exporters.** Repositories remain canonical; exporters rewrite
   the historical JSON/Markdown shapes so CLI and feed consumers keep working.
7. **Alembic migrations.** Scripts live under ``migrations/`` (not a top-level
   ``alembic/`` package name, which would shadow the Alembic library on
   ``sys.path``). ``alembic upgrade head`` / ``downgrade`` are supported; tests
   may also call ``SessionFactory.create_all()`` on SQLite.

## Consequences

- Core research tests do not require the server extra.
- Cross-workspace access is a hard failure at the repository/API boundary.
- Auth, invite-only signup, and role checks remain phase 4 scope, delivered
  after the product surfaces and evals (not immediately after persistence).
