"""Background research execution for ``POST /v1/runs/start``.

Alpha runs the LangGraph desk in a daemon thread and persists structured
outputs onto the durable ``AnalysisRun``. A process-wide lock keeps concurrent
graphs from racing on the global ``set_config`` used by ``TradingAgentsGraph``.
"""

from __future__ import annotations

import copy
import logging
import time
import traceback
from collections.abc import Callable
from datetime import date, datetime, timezone
from threading import Lock, Thread
from typing import Any
from uuid import uuid4

from tradingagents.agents.utils.rating import parse_rating
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.domain.schemas import AnalysisRun, RunStatus
from tradingagents.evals.governance import attach_model_metadata
from tradingagents.evidence.schemas import Evidence
from tradingagents.observability.logging import bind_trace_id, get_trace_id
from tradingagents.observability.pricing import PRICING_TABLE_VERSION, estimate_llm_cost_usd
from tradingagents.observability.schemas import AuditEvent, DeadLetterRecord, UsageRecord
from tradingagents.observability.usage import UsageTracker
from tradingagents.persistence.repositories import (
    AnalysisRunRepository,
    EvidenceRepository,
    PortfolioRepository,
    PortfolioStateRepository,
    RunEventRepository,
)
from tradingagents.persistence.repositories.ops import OpsRepository
from tradingagents.persistence.session import SessionFactory
from tradingagents.portfolio.service import CURRENT_SNAPSHOT_ID

logger = logging.getLogger(__name__)

_GRAPH_LOCK = Lock()
DEFAULT_ANALYSTS = ["market", "social", "news", "fundamentals"]

GraphFactory = Callable[..., Any]


def new_run_id() -> str:
    return f"ar_{uuid4().hex[:24]}"


def analysis_run_from_final_state(
    run: AnalysisRun,
    final_state: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> AnalysisRun:
    """Map graph ``final_state`` onto durable AnalysisRun fields."""
    debate = final_state.get("investment_debate_state") or {}
    structured = final_state.get("portfolio_decision_struct")
    if hasattr(structured, "model_dump"):
        structured = structured.model_dump(mode="json")
    if structured is not None and not isinstance(structured, dict):
        structured = None

    evidence_ids: list[str] = []
    for item in final_state.get("evidence") or []:
        try:
            record = item if isinstance(item, Evidence) else Evidence.model_validate(item)
        except (TypeError, ValueError):
            continue
        if record.id:
            evidence_ids.append(record.id)

    # Prefer IDs already on the run payload if the graph also stored them.
    for eid in final_state.get("evidence_ids") or []:
        evidence_ids.append(str(eid))

    final_trade_decision = str(final_state.get("final_trade_decision") or "")
    rating = None
    risks: list[str] = []
    if isinstance(structured, dict):
        rating = structured.get("rating")
        raw_risks = structured.get("invalidation_conditions") or []
        risks = [str(r) for r in raw_risks if r] if isinstance(raw_risks, list) else []

    if not rating:
        rating = parse_rating(final_trade_decision)

    bull = debate.get("bull_history") or final_state.get("bull_case") or ""
    bear = debate.get("bear_history") or final_state.get("bear_case") or ""
    if isinstance(bull, list):
        bull = "\n".join(str(x) for x in bull)
    if isinstance(bear, list):
        bear = "\n".join(str(x) for x in bear)

    updated = run.model_copy(
        update={
            "status": RunStatus.COMPLETED,
            "evidence_ids": sorted(set(evidence_ids)),
            "final_rating": str(rating) if rating else None,
            "portfolio_decision_struct": structured,
            "final_trade_decision": final_trade_decision,
            "bull_case": str(bull),
            "bear_case": str(bear),
            "risks": risks,
            "error": None,
            "completed_at": datetime.now(timezone.utc),
        }
    )
    return attach_model_metadata(updated, config=config or {})


def _extract_evidence(final_state: dict[str, Any]) -> list[Evidence]:
    out: list[Evidence] = []
    for item in final_state.get("evidence") or []:
        try:
            out.append(item if isinstance(item, Evidence) else Evidence.model_validate(item))
        except (TypeError, ValueError):
            continue
    return out


def _load_portfolio(session_factory: SessionFactory, workspace_id: str):
    with session_factory.session_scope() as session:
        controls = PortfolioStateRepository(session).get_controls(workspace_id)
        snapshot_id = controls.current_snapshot_id or CURRENT_SNAPSHOT_ID
        portfolio = PortfolioRepository(session).get(workspace_id, snapshot_id)
        if portfolio is None and snapshot_id != CURRENT_SNAPSHOT_ID:
            portfolio = PortfolioRepository(session).get(
                workspace_id, CURRENT_SNAPSHOT_ID
            )
        return portfolio


def _append_event(
    session_factory: SessionFactory,
    *,
    workspace_id: str,
    run_id: str,
    event_type: str,
    message: str = "",
    payload: dict | None = None,
) -> None:
    with session_factory.session_scope() as session:
        RunEventRepository(session).append(
            workspace_id=workspace_id,
            analysis_run_id=run_id,
            event_type=event_type,
            message=message,
            payload=payload,
        )


def _persist_usage(
    session_factory: SessionFactory,
    *,
    workspace_id: str,
    run: AnalysisRun,
    tracker: UsageTracker,
    duration_ms: int,
) -> AnalysisRun:
    cost = estimate_llm_cost_usd(
        tokens_in=tracker.tokens_in,
        tokens_out=tracker.tokens_out,
        deep_think_llm=run.deep_think_llm,
        quick_think_llm=run.quick_think_llm,
    )
    updated = run.model_copy(
        update={
            "llm_calls": tracker.llm_calls,
            "tool_calls": tracker.tool_calls,
            "tokens_in": tracker.tokens_in,
            "tokens_out": tracker.tokens_out,
            "provider_calls": tracker.provider_calls,
            "provider_errors": tracker.provider_errors,
            "estimated_cost_usd": cost,
            "duration_ms": duration_ms,
            "trace_id": run.trace_id or get_trace_id(),
        }
    )
    usage = UsageRecord(
        workspace_id=workspace_id,
        analysis_run_id=updated.id,
        kind="research_run",
        llm_calls=updated.llm_calls,
        tool_calls=updated.tool_calls,
        tokens_in=updated.tokens_in,
        tokens_out=updated.tokens_out,
        provider_calls=updated.provider_calls,
        provider_errors=updated.provider_errors,
        estimated_cost_usd=updated.estimated_cost_usd,
        duration_ms=duration_ms,
        pricing_version=PRICING_TABLE_VERSION,
        model_provider=updated.model_provider,
        deep_think_llm=updated.deep_think_llm,
        quick_think_llm=updated.quick_think_llm,
        trace_id=updated.trace_id,
    )
    with session_factory.session_scope() as session:
        saved = AnalysisRunRepository(session).save(updated, workspace_id=workspace_id)
        OpsRepository(session).save_usage(usage)
        RunEventRepository(session).append(
            workspace_id=workspace_id,
            analysis_run_id=saved.id or run.id or "",
            event_type="run.usage",
            message="Recorded token and cost usage",
            payload=usage.model_dump(mode="json"),
        )
        return saved


def execute_research_job(
    session_factory: SessionFactory,
    *,
    workspace_id: str,
    run_id: str,
    graph_factory: GraphFactory | None = None,
) -> AnalysisRun:
    """Run research for an existing queued AnalysisRun and persist results."""
    started = time.perf_counter()
    tracker = UsageTracker()
    with session_factory.session_scope() as session:
        run = AnalysisRunRepository(session).get(workspace_id, run_id)
        if run is None:
            raise ValueError(f"run not found: {run_id}")
        trace_id = bind_trace_id(run.trace_id)
        if not run.trace_id:
            run = run.model_copy(update={"trace_id": trace_id})
            AnalysisRunRepository(session).save(run, workspace_id=workspace_id)
        AnalysisRunRepository(session).update_status(
            workspace_id, run_id, RunStatus.RUNNING
        )
        RunEventRepository(session).append(
            workspace_id=workspace_id,
            analysis_run_id=run_id,
            event_type="run.started",
            message=f"Research started for {run.symbol}",
            payload={"trace_id": trace_id, "attempt": run.attempt},
        )

    portfolio = None
    try:
        portfolio = _load_portfolio(session_factory, workspace_id)
        _append_event(
            session_factory,
            workspace_id=workspace_id,
            run_id=run_id,
            event_type="run.portfolio_loaded",
            message=(
                f"Loaded portfolio ({len(portfolio.positions)} positions)"
                if portfolio is not None
                else "No current portfolio; running without book context"
            ),
            payload={"has_portfolio": portfolio is not None},
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("portfolio load failed for %s: %s", run_id, exc)
        _append_event(
            session_factory,
            workspace_id=workspace_id,
            run_id=run_id,
            event_type="run.portfolio_loaded",
            message=f"Portfolio load skipped: {exc}",
            payload={"has_portfolio": False},
        )

    config = copy.deepcopy(DEFAULT_CONFIG)
    factory = graph_factory
    if factory is None:
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        factory = TradingAgentsGraph

    try:
        with _GRAPH_LOCK:
            _append_event(
                session_factory,
                workspace_id=workspace_id,
                run_id=run_id,
                event_type="run.graph_started",
                message="Invoking multi-agent research graph",
            )
            graph = factory(
                list(run.selected_analysts or DEFAULT_ANALYSTS),
                config=config,
                debug=False,
                callbacks=[tracker],
            )
            final_state, _decision = graph.propagate(
                run.symbol,
                run.trade_date,
                asset_type="stock",
                portfolio=portfolio,
                market_view="",
            )
    except Exception as exc:
        logger.exception("research run %s failed", run_id)
        duration_ms = int((time.perf_counter() - started) * 1000)
        with session_factory.session_scope() as session:
            failed = AnalysisRunRepository(session).update_status(
                workspace_id,
                run_id,
                RunStatus.FAILED,
                error=str(exc),
            )
            RunEventRepository(session).append(
                workspace_id=workspace_id,
                analysis_run_id=run_id,
                event_type="run.failed",
                message=str(exc),
                payload={"traceback": traceback.format_exc()[-2000:]},
            )
            if failed is None:
                raise
            failed = failed.model_copy(
                update={
                    "llm_calls": tracker.llm_calls,
                    "tool_calls": tracker.tool_calls,
                    "tokens_in": tracker.tokens_in,
                    "tokens_out": tracker.tokens_out,
                    "duration_ms": duration_ms,
                    "trace_id": failed.trace_id or get_trace_id(),
                }
            )
            AnalysisRunRepository(session).save(failed, workspace_id=workspace_id)
            if failed.attempt >= failed.max_attempts:
                OpsRepository(session).save_dead_letter(
                    DeadLetterRecord(
                        workspace_id=workspace_id,
                        analysis_run_id=run_id,
                        attempts=failed.attempt,
                        last_error=str(exc),
                        payload={"symbol": failed.symbol, "trade_date": failed.trade_date},
                    )
                )
                OpsRepository(session).save_audit(
                    AuditEvent(
                        workspace_id=workspace_id,
                        action="run.dead_lettered",
                        resource_type="analysis_run",
                        resource_id=run_id,
                        message=str(exc),
                        trace_id=failed.trace_id,
                    )
                )
            return failed

    final_state = final_state or {}
    _append_event(
        session_factory,
        workspace_id=workspace_id,
        run_id=run_id,
        event_type="run.graph_completed",
        message="Graph finished; persisting structured decision",
    )

    duration_ms = int((time.perf_counter() - started) * 1000)
    with session_factory.session_scope() as session:
        current = AnalysisRunRepository(session).get(workspace_id, run_id)
        if current is None:
            raise ValueError(f"run disappeared: {run_id}")
        evidence = _extract_evidence(final_state)
        if evidence:
            EvidenceRepository(session).save_many(evidence, workspace_id=workspace_id)
        completed = analysis_run_from_final_state(current, final_state, config=config)
        saved = AnalysisRunRepository(session).save(completed, workspace_id=workspace_id)
        RunEventRepository(session).append(
            workspace_id=workspace_id,
            analysis_run_id=run_id,
            event_type="run.completed",
            message=(
                f"Completed with rating {saved.final_rating or 'n/a'}"
            ),
            payload={"final_rating": saved.final_rating},
        )

    return _persist_usage(
        session_factory,
        workspace_id=workspace_id,
        run=saved,
        tracker=tracker,
        duration_ms=duration_ms,
    )


def start_research_thread(
    session_factory: SessionFactory,
    *,
    workspace_id: str,
    run_id: str,
    graph_factory: GraphFactory | None = None,
) -> Thread:
    """Kick off ``execute_research_job`` on a daemon thread."""

    def _target() -> None:
        try:
            execute_research_job(
                session_factory,
                workspace_id=workspace_id,
                run_id=run_id,
                graph_factory=graph_factory,
            )
        except Exception:  # pragma: no cover
            logger.exception("unhandled research worker error for %s", run_id)

    thread = Thread(
        target=_target,
        name=f"alphadesk-run-{run_id}",
        daemon=True,
    )
    thread.start()
    return thread


def queue_research_run(
    session_factory: SessionFactory,
    *,
    workspace_id: str,
    symbol: str,
    trade_date: str | None = None,
    selected_analysts: list[str] | None = None,
    start_worker: bool = True,
    graph_factory: GraphFactory | None = None,
    trace_id: str | None = None,
    attempt: int = 1,
    max_attempts: int = 3,
) -> AnalysisRun:
    """Create a queued AnalysisRun and optionally start the background worker."""
    resolved_date = trade_date or date.today().isoformat()
    analysts = selected_analysts or list(DEFAULT_ANALYSTS)
    config = copy.deepcopy(DEFAULT_CONFIG)
    run = AnalysisRun(
        id=new_run_id(),
        symbol=symbol,
        trade_date=resolved_date,
        status=RunStatus.QUEUED,
        selected_analysts=analysts,
        workspace_id=workspace_id,
        model_provider=config.get("llm_provider"),
        deep_think_llm=config.get("deep_think_llm"),
        quick_think_llm=config.get("quick_think_llm"),
        trace_id=trace_id or bind_trace_id(),
        attempt=attempt,
        max_attempts=max_attempts,
    )
    with session_factory.session_scope() as session:
        saved = AnalysisRunRepository(session).save(run, workspace_id=workspace_id)
        RunEventRepository(session).append(
            workspace_id=workspace_id,
            analysis_run_id=saved.id,
            event_type="run.created",
            message=f"Run queued for {saved.symbol} on {saved.trade_date}",
            payload={"status": saved.status.value, "attempt": saved.attempt},
        )
        OpsRepository(session).save_audit(
            AuditEvent(
                workspace_id=workspace_id,
                action="run.queued",
                resource_type="analysis_run",
                resource_id=saved.id or "",
                message=f"Queued {saved.symbol}",
                trace_id=saved.trace_id,
            )
        )
    if start_worker:
        start_research_thread(
            session_factory,
            workspace_id=workspace_id,
            run_id=saved.id,
            graph_factory=graph_factory,
        )
    return saved


def retry_research_run(
    session_factory: SessionFactory,
    *,
    workspace_id: str,
    run_id: str,
    start_worker: bool = True,
    graph_factory: GraphFactory | None = None,
) -> AnalysisRun:
    """Requeue a failed run, or dead-letter when attempts are exhausted."""
    with session_factory.session_scope() as session:
        run = AnalysisRunRepository(session).get(workspace_id, run_id)
        if run is None:
            raise KeyError("run not found")
        if run.status is not RunStatus.FAILED:
            raise ValueError("only failed runs can be retried")
        next_attempt = run.attempt + 1
        if next_attempt > run.max_attempts:
            OpsRepository(session).save_dead_letter(
                DeadLetterRecord(
                    workspace_id=workspace_id,
                    analysis_run_id=run_id,
                    attempts=run.attempt,
                    last_error=run.error or "max attempts exceeded",
                )
            )
            raise ValueError("max attempts exceeded; run dead-lettered")
        updated = run.model_copy(
            update={
                "status": RunStatus.QUEUED,
                "attempt": next_attempt,
                "error": None,
                "completed_at": None,
            }
        )
        saved = AnalysisRunRepository(session).save(updated, workspace_id=workspace_id)
        RunEventRepository(session).append(
            workspace_id=workspace_id,
            analysis_run_id=run_id,
            event_type="run.retry",
            message=f"Retry attempt {next_attempt}/{saved.max_attempts}",
            payload={"attempt": next_attempt},
        )
        OpsRepository(session).save_audit(
            AuditEvent(
                workspace_id=workspace_id,
                action="run.retry",
                resource_type="analysis_run",
                resource_id=run_id,
                message=f"Retry attempt {next_attempt}",
                trace_id=saved.trace_id,
            )
        )
    if start_worker:
        start_research_thread(
            session_factory,
            workspace_id=workspace_id,
            run_id=saved.id,
            graph_factory=graph_factory,
        )
    return saved
