"""Phase 10 evaluation harness and governance metadata."""

from __future__ import annotations

from tradingagents.domain.schemas import AnalysisRun, RunStatus
from tradingagents.evals import (
    attach_model_metadata,
    load_eval_dataset,
    run_contract_checks,
)
from tradingagents.evals.governance import EVAL_SUITE_VERSION, RunModelMetadata
from tradingagents.evals.runner import main as evals_main


def test_dataset_has_breadth() -> None:
    cases = load_eval_dataset()
    assert 25 <= len(cases) <= 50
    assert {c.cap_bucket for c in cases} >= {"large", "mid", "small"}
    assert {c.scenario for c in cases} >= {
        "earnings",
        "filing",
        "sparse_data",
        "contested",
        "normal",
    }
    assert any(not c.profitable for c in cases)
    assert any(c.news_intensity == "low" for c in cases)


def test_contract_pass_and_fail_cases() -> None:
    good = run_contract_checks(
        {
            "trade_date": "2026-01-15",
            "final_rating": "Hold",
            "portfolio_decision_struct": {
                "rating": "Hold",
                "executive_summary": "Stay patient.",
                "investment_thesis": "Balanced risk/reward.",
            },
            "evidence_ids": ["ev_1"],
            "claims": [
                {
                    "text": "Cash was $2 billion at year end.",
                    "evidence_ids": ["ev_1"],
                    "as_of": "2026-01-10",
                }
            ],
            "risks": ["Multiple compression"],
            "require_risks": True,
            "portfolio_context": {"held": True, "stance": "manage"},
        }
    )
    assert good.passed

    bad = run_contract_checks(
        {
            "trade_date": "2026-01-15",
            "final_rating": "Buy",
            "portfolio_decision_struct": {
                "rating": "Sell",
                "executive_summary": "x",
                "investment_thesis": "y",
            },
            "evidence_ids": [],
            "claims": [{"text": "EPS printed $4.10", "evidence_ids": []}],
            "portfolio_context": {"held": True, "stance": "initiate"},
        }
    )
    assert not bad.passed
    checks = {v.check for v in bad.violations}
    assert "rating_consistency" in checks
    assert "unsupported_claim" in checks
    assert "evidence_coverage" in checks
    assert "portfolio_awareness" in checks


def test_attach_model_metadata() -> None:
    run = AnalysisRun(
        symbol="NVDA",
        trade_date="2026-01-15",
        status=RunStatus.COMPLETED,
        final_rating="Buy",
    )
    updated = attach_model_metadata(
        run,
        RunModelMetadata(prompt_version="desk-v2"),
        config={
            "llm_provider": "openai",
            "deep_think_llm": "gpt-5.5",
            "quick_think_llm": "gpt-5.4-mini",
        },
    )
    assert updated.model_provider == "openai"
    assert updated.deep_think_llm == "gpt-5.5"
    assert updated.prompt_version == "desk-v2"
    assert updated.eval_suite_version == EVAL_SUITE_VERSION


def test_evals_cli_fixtures_pass() -> None:
    assert evals_main([]) == 0
