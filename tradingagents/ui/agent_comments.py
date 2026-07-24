"""Pick the most relevant agent takes for a feed card (Facebook-style thread).

Not every agent comments on every card — only the analysts (or researchers)
whose work is the primary signal for that slide.
"""

from __future__ import annotations

import re
from typing import Any

from .feed_schema import AgentComment, CardKind


def _first_sentence(text: str, limit: int = 220) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[#*`>]", "", text).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"^\*?\*?(Bull|Bear|Aggressive|Conservative|Neutral)\*?\*?:?\s*", "", cleaned, flags=re.I)
    match = re.search(r"(.+?[.!?])(\s|$)", cleaned)
    sentence = match.group(1) if match else cleaned
    return sentence[:limit].strip()


def _comment(agent: str, text: str, *, role: str = "") -> AgentComment | None:
    clipped = _first_sentence(text)
    if not clipped:
        return None
    return AgentComment(agent=agent, text=clipped, role=role)


def comments_for_card(
    *,
    kind: CardKind | str,
    title: str,
    final_state: dict[str, Any] | None = None,
    body: str = "",
    max_comments: int = 3,
) -> list[AgentComment]:
    """Return 0–N agent comments most relevant to this card type."""
    state = final_state or {}
    kind_value = kind.value if isinstance(kind, CardKind) else str(kind)
    title_l = (title or "").lower()
    out: list[AgentComment] = []

    def add(agent: str, text: str, *, role: str = "") -> None:
        if len(out) >= max_comments:
            return
        item = _comment(agent, text, role=role)
        if item is not None:
            out.append(item)

    debate = state.get("investment_debate_state") or {}
    risk = state.get("risk_debate_state") or {}

    if "macro" in title_l:
        add("News Analyst", state.get("news_report") or body, role="Macro")
        if body and body != state.get("news_report"):
            add("Macro", body, role="Data")
    elif "market" in title_l:
        add("Market Analyst", state.get("market_report") or body)
    elif "sentiment" in title_l:
        add("Sentiment Analyst", state.get("sentiment_report") or body)
    elif "fundamental" in title_l:
        add("Fundamentals Analyst", state.get("fundamentals_report") or body)
    elif "news" in title_l:
        add("News Analyst", state.get("news_report") or body)
    elif kind_value == "tension" or "debate" in title_l or "bull" in title_l:
        add("Bull Researcher", debate.get("bull_history") or "", role="Bull")
        add("Bear Researcher", debate.get("bear_history") or "", role="Bear")
        add("Research Manager", debate.get("judge_decision") or "")
    elif kind_value == "verdict" or "verdict" in title_l or "stance" in title_l:
        add(
            "Portfolio Manager",
            state.get("final_trade_decision") or body,
            role="PM",
        )
        add("Trader", state.get("trader_investment_plan") or "")
        add(
            "Conservative Analyst",
            risk.get("conservative_history") or "",
            role="Risk",
        )
    elif "thesis" in title_l:
        add(
            "Portfolio Manager",
            state.get("final_trade_decision")
            or body
            or "Thesis revision recorded; review catalysts and invalidation.",
            role="PM",
        )
        add("Research Manager", debate.get("judge_decision") or "")
    elif kind_value == "hook" or "desk" in title_l or "story" in title_l:
        add(
            "Portfolio Manager",
            state.get("final_trade_decision") or body,
            role="PM",
        )
    elif kind_value == "context" or "affected" in title_l:
        add("Portfolio Manager", body or "These names are in scope for this story.", role="PM")
    else:
        add("Portfolio Manager", body or state.get("final_trade_decision") or "")

    return out[:max_comments]


def comments_from_lines(
    lines: list[str],
    *,
    agent: str = "Portfolio Manager",
    role: str = "PM",
    max_comments: int = 3,
) -> list[AgentComment]:
    """Turn desk/theme bullet lines into a short PM comment thread."""
    out: list[AgentComment] = []
    for line in lines:
        text = re.sub(r"^[-•]\s*", "", (line or "").strip())
        if not text:
            continue
        item = _comment(agent, text, role=role)
        if item is None:
            continue
        out.append(item)
        if len(out) >= max_comments:
            break
    return out
