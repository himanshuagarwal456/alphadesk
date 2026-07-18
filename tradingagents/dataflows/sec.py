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
    if not rows:
        return f"SEC: no filings for {ticker} on or before {curr_date}."
    name = submissions.get("name", ticker)
    return f"## SEC filings: {name} ({ticker})\n\n| Filing date | Form | Source |\n| --- | --- | --- |\n" + "\n".join(rows)
