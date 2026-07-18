"""Model and prompt metadata attached to durable analysis runs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tradingagents.domain.schemas import AnalysisRun

EVAL_SUITE_VERSION = "evals-v1"


class RunModelMetadata(BaseModel):
    """Provider/model/prompt identity for governance and eval comparisons."""

    model_provider: str | None = None
    deep_think_llm: str | None = None
    quick_think_llm: str | None = None
    prompt_version: str = Field(default="default-v1")
    eval_suite_version: str = Field(default=EVAL_SUITE_VERSION)


def attach_model_metadata(
    run: AnalysisRun,
    metadata: RunModelMetadata | None = None,
    *,
    config: dict | None = None,
) -> AnalysisRun:
    """Return a copy of ``run`` with governance fields filled in.

    When ``config`` is a TradingAgents config dict, provider/model names are
    read from the usual keys if metadata fields are omitted.
    """
    meta = metadata or RunModelMetadata()
    cfg = config or {}
    return run.model_copy(
        update={
            "model_provider": meta.model_provider or cfg.get("llm_provider"),
            "deep_think_llm": meta.deep_think_llm or cfg.get("deep_think_llm"),
            "quick_think_llm": meta.quick_think_llm or cfg.get("quick_think_llm"),
            "prompt_version": meta.prompt_version,
            "eval_suite_version": meta.eval_suite_version,
        }
    )
