"""Official SEC EDGAR fundamentals vendor with filing-evidence capture."""

from __future__ import annotations

import os
import threading
from datetime import datetime

import requests

from tradingagents.evidence import Evidence

from .errors import NoMarketDataError, VendorNotConfiguredError

SEC_DATA = "https://data.sec.gov"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
_captured: dict[str, list[Evidence]] = {}
_lock = threading.Lock()

# Normalized metric -> ordered us-gaap concept fallbacks. Companies tag the
# same economic quantity under different taxonomy concepts; the first concept
# present in companyfacts wins, and the chosen concept is always recorded on
# the evidence so the value stays traceable to its exact XBRL source.
COMPANYFACTS_METRICS: dict[str, tuple[str, ...]] = {
    "Revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "Net income": ("NetIncomeLoss",),
    "Operating income": ("OperatingIncomeLoss",),
    "Total assets": ("Assets",),
    "Total liabilities": ("Liabilities",),
    "Diluted EPS": ("EarningsPerShareDiluted",),
    "Operating cash flow": ("NetCashProvidedByUsedInOperatingActivities",),
}


class SecNotConfiguredError(VendorNotConfiguredError):
    """Raised when SEC's required descriptive User-Agent is absent."""


def _headers() -> dict[str, str]:
    user_agent = os.getenv("SEC_USER_AGENT")
    if not user_agent:
        raise SecNotConfiguredError("SEC_USER_AGENT is required by SEC EDGAR fair-access policy.")
    return {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}


def _request(url: str) -> dict:
    response = requests.get(url, headers=_headers(), timeout=30)
    response.raise_for_status()
    return response.json()


def _cik(ticker: str) -> str:
    ticker = ticker.upper()
    for item in _request(SEC_TICKERS).values():
        if item["ticker"].upper() == ticker:
            return str(item["cik_str"]).zfill(10)
    raise NoMarketDataError(ticker, ticker, "no SEC CIK mapping")


def clear_captured_filing_evidence(ticker: str) -> None:
    with _lock:
        _captured.pop(ticker.upper(), None)


def consume_captured_filing_evidence(ticker: str) -> list[Evidence]:
    with _lock:
        records = _captured.pop(ticker.upper(), [])
    return list({item.id: item for item in records}.values())


def _latest_fact(concept_data: dict, curr_date: str) -> tuple[dict, str] | None:
    """Pick the most recent fact filed on or before ``curr_date``.

    Look-ahead safety: facts *filed* after ``curr_date`` did not exist at that
    time and are excluded, even when their period ended earlier. Amended and
    duplicated facts (same period reported in multiple filings) are resolved
    deterministically: for one period end, the latest filing date wins.
    """
    best: dict | None = None
    best_unit = ""
    for unit, facts in (concept_data.get("units") or {}).items():
        for fact in facts:
            if not fact.get("end") or not fact.get("filed"):
                continue
            if fact["filed"] > curr_date:
                continue
            if best is None or (fact["end"], fact["filed"]) > (best["end"], best["filed"]):
                best = fact
                best_unit = unit
    return (best, best_unit) if best else None


def _company_facts_section(ticker: str, cik: str, curr_date: str) -> str:
    """Render official companyfacts metrics and capture each as evidence.

    Fail-open: entities without companyfacts (funds, some foreign issuers)
    simply omit the section rather than degrading the filings report.
    """
    try:
        payload = _request(f"{SEC_DATA}/api/xbrl/companyfacts/CIK{cik}.json")
    except Exception:  # noqa: BLE001 — optional enrichment must not break filings
        return ""
    gaap = (payload.get("facts") or {}).get("us-gaap") or {}

    rows = []
    for metric, concepts in COMPANYFACTS_METRICS.items():
        for concept in concepts:
            if concept not in gaap:
                continue
            picked = _latest_fact(gaap[concept], curr_date)
            if picked is None:
                break
            fact, unit = picked
            accession = fact.get("accn", "")
            source_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{accession.replace('-', '')}"
            )
            period = f"{fact.get('fp', '')} {fact.get('fy', '')}".strip()
            evidence = Evidence(
                provider_id="sec",
                source_type="filing",
                title=f"{ticker} {metric}: {fact['val']:,} {unit} ({period})",
                source_url=source_url,
                publisher="SEC EDGAR",
                published_at=datetime.strptime(fact["filed"], "%Y-%m-%d"),
                summary=(
                    f"{metric} = {fact['val']:,} {unit} for period ending {fact['end']}"
                    f" ({period}, {fact.get('form', '?')}). XBRL concept us-gaap:"
                    f"{concept}; accession {accession}; filed {fact['filed']}."
                ),
                source_quality_score=0.98,
            )
            with _lock:
                _captured.setdefault(ticker.upper(), []).append(evidence)
            rows.append(
                f"| {metric} | {fact['val']:,} {unit} | {fact['end']} | {period} "
                f"| {fact.get('form', '?')} |"
            )
            break
    if not rows:
        return ""
    return (
        "\n\n### Official company facts (XBRL, as filed)\n\n"
        "| Metric | Value | Period end | Fiscal | Form |\n"
        "| --- | --- | --- | --- | --- |\n" + "\n".join(rows)
    )


def get_fundamentals(ticker: str, curr_date: str) -> str:
    cik = _cik(ticker)
    submissions = _request(f"{SEC_DATA}/submissions/CIK{cik}.json")
    recent = submissions.get("filings", {}).get("recent", {})
    rows = []
    for form, date, accession, document in zip(
        recent.get("form", []), recent.get("filingDate", []),
        recent.get("accessionNumber", []), recent.get("primaryDocument", []),
        strict=False,
    ):
        if form not in {"10-K", "10-Q", "8-K"} or date > curr_date:
            continue
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{document}"
        evidence = Evidence(
            provider_id="sec", source_type="filing", title=f"{ticker} {form} filed {date}",
            source_url=url, publisher="SEC EDGAR",
            published_at=datetime.strptime(date, "%Y-%m-%d"),
            summary=f"{form} filing accession {accession}.", source_quality_score=0.98,
        )
        with _lock:
            _captured.setdefault(ticker.upper(), []).append(evidence)
        rows.append(f"| {date} | {form} | {url} |")
        if len(rows) == 8:
            break
    facts_section = _company_facts_section(ticker, cik, curr_date)
    if not rows and not facts_section:
        return f"SEC: no filings for {ticker} on or before {curr_date}."
    name = submissions.get("name", ticker)
    filings_table = (
        "| Filing date | Form | Source |\n| --- | --- | --- |\n" + "\n".join(rows)
        if rows
        else f"No 10-K/10-Q/8-K filings on or before {curr_date}."
    )
    return f"## SEC filings: {name} ({ticker})\n\n{filings_table}{facts_section}"
