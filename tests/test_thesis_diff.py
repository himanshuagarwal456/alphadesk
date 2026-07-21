"""Deterministic thesis diffs, triggers, and feed cards."""

from tradingagents.agents.schemas import PortfolioDecision, PortfolioRating
from tradingagents.thesis import (
    LivingThesisStore,
    ThesisTrigger,
    build_thesis_update,
    diff_or_none,
    evaluate_triggers,
)
from tradingagents.ui.deck_builder import build_narrative
from tradingagents.ui.sample import sample_final_state, sample_ohlcv


def _decision(rating, thesis="Demand remains durable."):
    return PortfolioDecision(
        rating=rating, executive_summary="Plan.", investment_thesis=thesis
    )


def test_diff_and_triggers_for_rating_downgrade():
    first, head = build_thesis_update(
        symbol="NVDA", trade_date="2026-01-15", stance="manage",
        decision=_decision(PortfolioRating.BUY), evidence_ids=["ev_a"], prior=None,
    )
    second, _ = build_thesis_update(
        symbol="NVDA", trade_date="2026-02-15", stance="manage",
        decision=_decision(PortfolioRating.HOLD), evidence_ids=["ev_b"], prior=head,
    )
    diff = diff_or_none(first, second)
    assert diff.rating_downgraded
    assert diff.evidence_added == ["ev_b"]
    assert ThesisTrigger.RATING_DOWNGRADE in evaluate_triggers(diff)


def test_feed_inserts_thesis_change_card(tmp_path):
    store = LivingThesisStore(tmp_path)
    first, head = build_thesis_update(
        symbol="NVDA", trade_date="2026-01-15", stance="manage",
        decision=_decision(PortfolioRating.BUY), evidence_ids=[], prior=None,
    )
    store.upsert_run(head, first)
    second, head = build_thesis_update(
        symbol="NVDA", trade_date="2026-02-15", stance="manage",
        decision=_decision(PortfolioRating.HOLD), evidence_ids=[], prior=head,
    )
    store.upsert_run(head, second)
    state = sample_final_state("NVDA")
    state["trade_date"] = "2026-02-15"
    narrative = build_narrative(state, ohlcv=sample_ohlcv(), thesis_store=store)
    card = next(card for card in narrative.cards if card.card_type == "thesis_change")
    assert card.kind.value == "context"
    assert "downgraded" in card.headline.lower()
    assert card.learn_more
    assert any(
        item.slug in {"thesis", "catalyst", "invalidation", "concentration-risk"}
        or "thesis" in item.title.lower()
        for item in card.learn_more
    )


def test_sample_feed_includes_thesis_learn_more():
    from tradingagents.ui.render import render_feed_html
    from tradingagents.ui.sample import sample_feed

    feed = sample_feed()
    thesis_story = next(
        (n for n in feed.narratives if n.meta.get("story_kind") == "thesis_change"),
        None,
    )
    assert thesis_story is not None
    thesis_cards = [c for c in thesis_story.cards if c.card_type == "thesis_change"]
    assert thesis_cards
    assert any(c.learn_more for c in thesis_cards)
    html = render_feed_html(feed)
    assert "Learn More" in html
    assert "learn_more" in html or "openLearnMore" in html
