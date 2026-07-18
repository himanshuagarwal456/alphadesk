# ADR 0001: Canonical evidence layer

**Status:** Accepted
**Date:** 2026-07-18

## Context

Agent conclusions originally flowed through the system as rendered markdown,
so sources (news articles, macro series, SEC filings) were only recoverable by
re-parsing prose. The alpha product requires every material claim to be
traceable to a durable, source-linked record (`docs/alpha-release.md` §5, §7).

## Decision

1. **`Evidence` is the canonical unit of retrieved knowledge.** It is an
   immutable, versioned Pydantic record with a stable content-derived ID,
   provider ID, source type (`news` / `macro` / `filing`), source URL,
   publisher, published/retrieved timestamps, a bounded normalized excerpt,
   and a source-quality score. Publisher-owned raw bodies are not stored.
2. **Providers capture evidence as a side channel.** Existing agent tools keep
   their string-returning contracts; each provider normalizes its already
   parsed metadata into `Evidence` records in a run-scoped buffer
   (`clear_captured_*` / `consume_captured_*`), which the graph merges into
   `final_state["evidence"]` after the run.
3. **Persistence is an atomic sidecar per run.** `EvidenceStore` writes
   `evidence_{trade_date}.json` next to each saved run; the run log carries
   only `evidence_ids`. Downstream layers (feed cards, theses, journal
   entries) reference evidence by ID, never by copying content.
4. **Structured objects are canonical; markdown is presentation.** New
   consumers must read structured records; regex extraction from prose is
   legacy and is being retired incrementally.

## Consequences

- New providers integrate by adding a normalizer, not by changing tool or
  graph contracts.
- Look-ahead safety and licensing boundaries are enforced at the normalizer.
- The evidence schema will grow (ownership/workspace classification for
  user-owned documents) via additive, versioned fields.
