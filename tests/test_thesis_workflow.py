"""Thesis creation from saved runs and the human-reviewed revision workflow."""

from __future__ import annotations

import pytest

from tradingagents.agents.schemas import PortfolioDecision, PortfolioRating
from tradingagents.thesis import (
    LivingThesisStore,
    RevisionStatus,
    ThesisStatus,
    build_thesis_update,
    create_thesis_from_run,
    propose_revision,
    review_revision,
)
from tradingagents.ui.sample import sample_final_state


@pytest.mark.unit
def test_create_thesis_from_structured_run(tmp_path):
    store = LivingThesisStore(tmp_path)
    run = sample_final_state("NVDA")
    run["portfolio_decision_struct"] = PortfolioDecision(
        rating="Overweight",
        executive_summary="Add on weakness.",
        investment_thesis="Structured thesis.",
        catalysts=["Earnings on 2026-02-25"],
        invalidation_conditions=["Data-center revenue declines"],
    ).model_dump(mode="json")

    snapshot, thesis = create_thesis_from_run(run, store, stance="manage")
    assert snapshot.rating is PortfolioRating.OVERWEIGHT
    assert snapshot.catalysts[0].description == "Earnings on 2026-02-25"
    assert store.load("NVDA").current_snapshot_id == snapshot.snapshot_id


@pytest.mark.unit
def test_create_thesis_from_legacy_markdown_run(tmp_path):
    store = LivingThesisStore(tmp_path)
    run = sample_final_state("NVDA")  # markdown carries **Rating**: Underweight
    snapshot, _ = create_thesis_from_run(run, store)
    assert snapshot.rating is PortfolioRating.UNDERWEIGHT
    assert snapshot.investment_thesis  # prose preserved


def _seeded_head(store, rating=PortfolioRating.BUY):
    decision = PortfolioDecision(
        rating=rating, executive_summary="Plan.", investment_thesis="Thesis."
    )
    snapshot, head = build_thesis_update(
        symbol="NVDA", trade_date="2026-01-15", stance="manage",
        decision=decision, evidence_ids=[], prior=None,
    )
    store.upsert_run(head, snapshot)
    return snapshot, head


@pytest.mark.unit
def test_rejected_revision_changes_nothing_but_is_audited(tmp_path):
    store = LivingThesisStore(tmp_path)
    current, head = _seeded_head(store)
    decision = PortfolioDecision(
        rating=PortfolioRating.SELL, executive_summary="Exit.", investment_thesis="Bear."
    )
    proposed_snapshot, _ = build_thesis_update(
        symbol="NVDA", trade_date="2026-02-15", stance="manage",
        decision=decision, evidence_ids=["ev_x"], prior=head,
    )
    proposal = propose_revision(store, proposed_snapshot, reason="Guidance cut")
    reviewed = review_revision(store, proposal, accept=False, note="Disagree")

    assert reviewed.status is RevisionStatus.REJECTED
    # current thesis untouched
    assert store.load("NVDA").current_snapshot_id == current.snapshot_id
    # audit history retains the rejected proposal
    audit = store.load_proposals("NVDA")
    assert audit[-1].status is RevisionStatus.REJECTED
    assert audit[-1].review_note == "Disagree"


@pytest.mark.unit
def test_accepted_revision_applies_and_double_review_fails(tmp_path):
    store = LivingThesisStore(tmp_path)
    _, head = _seeded_head(store)
    decision = PortfolioDecision(
        rating=PortfolioRating.HOLD, executive_summary="Trim.", investment_thesis="Neutral."
    )
    proposed_snapshot, _ = build_thesis_update(
        symbol="NVDA", trade_date="2026-02-15", stance="manage",
        decision=decision, evidence_ids=[], prior=head,
    )
    proposal = propose_revision(store, proposed_snapshot, reason="Momentum faded")
    reviewed = review_revision(store, proposal, accept=True)

    thesis = store.load("NVDA")
    assert reviewed.status is RevisionStatus.ACCEPTED
    assert thesis.current_snapshot_id == proposed_snapshot.snapshot_id
    assert thesis.status is ThesisStatus.WEAKENED
    assert len(thesis.snapshot_ids) == 2

    with pytest.raises(ValueError):
        review_revision(store, reviewed, accept=True)
