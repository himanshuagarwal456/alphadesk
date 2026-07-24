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
    assert card.learn_brief is not None
    assert "claim" in card.learn_brief.what_this_means.lower() or "downgraded" in card.learn_brief.what_this_means.lower()
    assert card.learn_more or card.learn_brief.concepts
    assert any(
        item.slug in {"thesis", "catalyst", "invalidation", "concentration-risk"}
        or "thesis" in item.title.lower()
        for item in (card.learn_more or card.learn_brief.concepts)
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
    assert any(c.learn_brief or c.learn_more for c in thesis_cards)
    html = render_feed_html(feed)
    assert "Learn More" in html
    assert "What this card means" in html
    assert "openLearnMore" in html


def test_learn_brief_explains_card_not_only_catalog():
    from tradingagents.ui.feed_schema import AgentComment, Card, CardKind
    from tradingagents.ui.knowledge_attach import build_learn_brief

    card = Card(
        id="nvda-news",
        kind=CardKind.EVIDENCE,
        title="News",
        headline="Export controls tighten for NVDA customers",
        body="Sector headlines flag softer enterprise demand ahead of earnings.",
        comments=[
            AgentComment(
                agent="News Analyst",
                text="No company-specific catalyst before the print.",
            )
        ],
        portfolio_impact="Held position: 22.0% of portfolio; review sizing and thesis.",
        symbols=["NVDA"],
        card_type="event",
    )
    brief = build_learn_brief(card, symbol="NVDA")
    assert "Export controls" in brief.what_this_means or "claim" in brief.what_this_means.lower()
    assert "22.0%" in brief.why_it_matters or "NVDA" in brief.why_it_matters
    assert brief.what_to_check
    assert any("News Analyst" in t for t in brief.agent_takeaways)
