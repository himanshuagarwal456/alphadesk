"""Automated contract checks for analysis outputs (no live LLM required)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

_ISO_DATE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_MONEY = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?(?:\s*(?:million|billion|trillion|bn|mm|m|b))?",
    re.I,
)
_ALLOWED_RATINGS = {
    "Buy",
    "Overweight",
    "Hold",
    "Underweight",
    "Sell",
    "buy",
    "overweight",
    "hold",
    "underweight",
    "sell",
}


class ContractViolation(BaseModel):
    check: str
    message: str
    path: str = ""


class ContractCheckResult(BaseModel):
    passed: bool
    violations: list[ContractViolation] = Field(default_factory=list)

    @property
    def failure_count(self) -> int:
        return len(self.violations)


def run_contract_checks(payload: dict[str, Any]) -> ContractCheckResult:
    """Run deterministic quality contracts against a run-shaped payload.

    Expected keys (all optional except where a check needs them):

    - ``trade_date``: YYYY-MM-DD cutoff
    - ``final_rating`` / ``portfolio_decision_struct.rating``
    - ``claims``: list of ``{text, evidence_ids, as_of?}``
    - ``evidence_ids``: ids attached to the run
    - ``evidence``: list of ``{id, published_at?}``
    - ``bull_case`` / ``bear_case`` / ``risks``
    - ``portfolio_context``: optional held/candidate stance consistency
    """
    violations: list[ContractViolation] = []
    violations.extend(_check_rating_consistency(payload))
    violations.extend(_check_look_ahead(payload))
    violations.extend(_check_unsupported_claims(payload))
    violations.extend(_check_evidence_coverage(payload))
    violations.extend(_check_internal_structure(payload))
    violations.extend(_check_portfolio_awareness(payload))
    return ContractCheckResult(passed=not violations, violations=violations)


def _check_rating_consistency(payload: dict[str, Any]) -> list[ContractViolation]:
    out: list[ContractViolation] = []
    struct = payload.get("portfolio_decision_struct") or {}
    rating = payload.get("final_rating") or struct.get("rating")
    if rating is None:
        out.append(
            ContractViolation(
                check="rating_present",
                message="final rating missing",
                path="final_rating",
            )
        )
        return out
    if str(rating) not in _ALLOWED_RATINGS:
        out.append(
            ContractViolation(
                check="rating_allowed",
                message=f"rating {rating!r} is not in the allowed set",
                path="final_rating",
            )
        )
    if (
        struct.get("rating")
        and payload.get("final_rating")
        and str(struct["rating"]).lower() != str(payload["final_rating"]).lower()
    ):
        out.append(
            ContractViolation(
                check="rating_consistency",
                message="final_rating disagrees with portfolio_decision_struct.rating",
                path="final_rating",
            )
        )
    return out


def _parse_day(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value)
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _check_look_ahead(payload: dict[str, Any]) -> list[ContractViolation]:
    cutoff = _parse_day(payload.get("trade_date"))
    if cutoff is None:
        return []
    out: list[ContractViolation] = []
    for idx, claim in enumerate(payload.get("claims") or []):
        claim_day = _parse_day(claim.get("as_of") or claim.get("published_at"))
        if claim_day and claim_day > cutoff:
            out.append(
                ContractViolation(
                    check="look_ahead",
                    message=f"claim dated {claim_day} after trade_date {cutoff}",
                    path=f"claims[{idx}]",
                )
            )
        for match in _ISO_DATE.findall(str(claim.get("text") or "")):
            mentioned = _parse_day(match)
            if mentioned and mentioned > cutoff:
                out.append(
                    ContractViolation(
                        check="look_ahead",
                        message=f"claim text references future date {mentioned}",
                        path=f"claims[{idx}].text",
                    )
                )
    for idx, ev in enumerate(payload.get("evidence") or []):
        published = _parse_day(ev.get("published_at"))
        if published and published > cutoff:
            out.append(
                ContractViolation(
                    check="look_ahead",
                    message=f"evidence published {published} after trade_date {cutoff}",
                    path=f"evidence[{idx}]",
                )
            )
    return out


def _check_unsupported_claims(payload: dict[str, Any]) -> list[ContractViolation]:
    out: list[ContractViolation] = []
    known = {str(e.get("id")) for e in (payload.get("evidence") or []) if e.get("id")}
    known.update(str(x) for x in (payload.get("evidence_ids") or []))
    for idx, claim in enumerate(payload.get("claims") or []):
        text = str(claim.get("text") or "")
        evidence_ids = [str(x) for x in (claim.get("evidence_ids") or [])]
        needs_support = bool(_MONEY.search(text)) or bool(claim.get("requires_evidence"))
        if needs_support and not evidence_ids:
            out.append(
                ContractViolation(
                    check="unsupported_claim",
                    message="numerical/material claim has no evidence_ids",
                    path=f"claims[{idx}]",
                )
            )
        for eid in evidence_ids:
            if known and eid not in known:
                out.append(
                    ContractViolation(
                        check="citation_correctness",
                        message=f"claim cites unknown evidence id {eid}",
                        path=f"claims[{idx}]",
                    )
                )
    return out


def _check_evidence_coverage(payload: dict[str, Any]) -> list[ContractViolation]:
    if payload.get("allow_empty_evidence"):
        return []
    evidence_ids = payload.get("evidence_ids") or []
    evidence = payload.get("evidence") or []
    if not evidence_ids and not evidence:
        return [
            ContractViolation(
                check="evidence_coverage",
                message="run has no evidence_ids or evidence records",
                path="evidence_ids",
            )
        ]
    return []


def _check_internal_structure(payload: dict[str, Any]) -> list[ContractViolation]:
    out: list[ContractViolation] = []
    struct = payload.get("portfolio_decision_struct")
    if struct is not None and not isinstance(struct, dict):
        out.append(
            ContractViolation(
                check="structured_output",
                message="portfolio_decision_struct must be an object",
                path="portfolio_decision_struct",
            )
        )
        return out
    if isinstance(struct, dict):
        for key in ("executive_summary", "investment_thesis"):
            if not str(struct.get(key) or "").strip():
                out.append(
                    ContractViolation(
                        check="structured_output",
                        message=f"missing {key}",
                        path=f"portfolio_decision_struct.{key}",
                    )
                )
    risks = payload.get("risks")
    if risks is not None and not isinstance(risks, list):
        out.append(
            ContractViolation(
                check="risk_identification",
                message="risks must be a list",
                path="risks",
            )
        )
    elif isinstance(risks, list) and len(risks) == 0 and payload.get("require_risks"):
        out.append(
            ContractViolation(
                check="risk_identification",
                message="expected at least one risk",
                path="risks",
            )
        )
    return out


def _check_portfolio_awareness(payload: dict[str, Any]) -> list[ContractViolation]:
    ctx = payload.get("portfolio_context") or {}
    if not ctx:
        return []
    held = bool(ctx.get("held"))
    stance = str(ctx.get("stance") or payload.get("stance") or "").lower()
    if not stance:
        return []
    if held and stance in {"initiate", "open", "enter"}:
        return [
            ContractViolation(
                check="portfolio_awareness",
                message="held name used an initiate stance",
                path="stance",
            )
        ]
    if not held and stance in {"manage", "trim", "exit", "add"}:
        return [
            ContractViolation(
                check="portfolio_awareness",
                message="non-held name used a manage/exit stance",
                path="stance",
            )
        ]
    return []
