"""Rule-based materiality classifier for inbound monitoring events."""

from __future__ import annotations

from hashlib import sha256

from tradingagents.monitoring.schemas import DetectedEvent, MaterialityVerdict

_MATERIAL_FILINGS = {"8-k", "8k", "10-k", "10k", "10-q", "10q", "6-k", "6k", "20-f", "20f"}
_MATERIAL_KEYWORDS = (
    "earnings",
    "guidance",
    "gross margin",
    "operating margin",
    "lawsuit",
    "investigation",
    "bankruptcy",
    "acquisition",
    "merger",
    "downgrade",
    "upgrade",
    "restatement",
    "going concern",
    "sec charges",
    "clinical trial",
    "fda",
)
_IMMATERIAL_KEYWORDS = (
    "market wrap",
    "what to watch",
    "stocks to watch",
    "premarket movers",
    "after hours chatter",
)


def classify_materiality(event: DetectedEvent) -> MaterialityVerdict:
    text = f"{event.title} {event.summary} {event.event_type}".lower()
    form = str(event.payload.get("form") or event.payload.get("filing_form") or "").lower()
    price_move = event.payload.get("price_move_pct")

    if any(k in text for k in _IMMATERIAL_KEYWORDS) and not any(
        k in text for k in _MATERIAL_KEYWORDS
    ):
        return MaterialityVerdict(
            material=False,
            score=0.15,
            reason="Routine market chatter without company-specific catalyst",
            impact_key="routine_news",
            should_queue_analysis=False,
        )

    form_compact = form.replace(" ", "").replace("-", "")
    if form_compact in {f.replace("-", "") for f in _MATERIAL_FILINGS} or any(
        f.replace("-", "") in form_compact for f in _MATERIAL_FILINGS
    ):
        return MaterialityVerdict(
            material=True,
            score=0.9,
            reason=f"Material SEC filing ({form or 'filing'})",
            impact_key=f"filing:{form or 'sec'}",
            should_queue_analysis=True,
        )

    if isinstance(price_move, (int, float)) and abs(float(price_move)) >= 5.0:
        return MaterialityVerdict(
            material=True,
            score=min(1.0, 0.55 + abs(float(price_move)) / 100.0),
            reason=f"Price move {float(price_move):+.1f}% exceeds 5% threshold",
            impact_key="price_move",
            should_queue_analysis=True,
        )

    hits = [k for k in _MATERIAL_KEYWORDS if k in text]
    if hits:
        score = min(0.95, 0.45 + 0.1 * len(hits))
        return MaterialityVerdict(
            material=True,
            score=score,
            reason=f"Material keywords: {', '.join(hits[:4])}",
            impact_key=f"theme:{hits[0].replace(' ', '_')}",
            should_queue_analysis=score >= 0.65,
        )

    if event.source in {"sec", "thesis_trigger"}:
        return MaterialityVerdict(
            material=True,
            score=0.7,
            reason=f"Trusted source ({event.source}) treated as material by default",
            impact_key=event.event_type,
            should_queue_analysis=False,
        )

    return MaterialityVerdict(
        material=False,
        score=0.25,
        reason="No material filing, price breach, or catalyst keywords detected",
        impact_key="immaterial",
        should_queue_analysis=False,
    )


def fingerprint_for(event: DetectedEvent, verdict: MaterialityVerdict) -> str:
    evidence = event.evidence_id or event.id or event.title
    raw = f"{event.workspace_id}|{event.symbol}|{evidence}|{verdict.impact_key}"
    return sha256(raw.encode("utf-8")).hexdigest()
