"""Broker-CSV -> ``Portfolio`` loader.

Broker exports vary wildly in column naming (Fidelity, Schwab, IBKR, Robinhood,
Vanguard, ...), so this loader maps a set of known header aliases onto the
canonical :class:`~tradingagents.portfolio.schemas.Position` fields, and lets a
caller override or extend the mapping for an unusual export. Numeric cells are
cleaned of the usual broker decorations ($, commas, parentheses-for-negative,
trailing %) before parsing.

The loader is deterministic: the same CSV always yields the same ``Portfolio``
(positions are symbol-sorted by the schema), which matters for the
reproducibility/backtest requirements of the surrounding system.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from .schemas import Portfolio, Position

# Canonical field -> accepted header aliases (compared case-insensitively, with
# surrounding whitespace and non-alphanumerics collapsed). Extend via the
# ``column_map`` argument for a broker not covered here.
_DEFAULT_ALIASES: dict[str, tuple[str, ...]] = {
    "symbol": ("symbol", "ticker", "instrument", "security", "securitysymbol"),
    "quantity": ("quantity", "qty", "shares", "sharesheld", "position", "units"),
    "avg_cost": (
        "avgcost",
        "averagecost",
        "averagecostbasis",
        "costbasispershare",
        "avgprice",
        "averageprice",
        "purchaseprice",
        "unitcost",
    ),
    "current_price": (
        "lastprice",
        "currentprice",
        "price",
        "mark",
        "marketprice",
        "lasttradeprice",
        "closeprice",
    ),
    "market_value": ("marketvalue", "currentvalue", "value", "positionvalue", "mktval"),
    "asset_type": ("assettype", "type", "securitytype", "instrumenttype"),
    "currency": ("currency", "ccy", "curr"),
}

# Symbols that denote a cash/sweep row rather than a tradable position. Matched
# case-insensitively against the symbol cell. Money-market sweep tickers are
# broker-specific; the common ones are included so cash is not double-counted
# as an equity position.
_CASH_SYMBOLS = frozenset(
    {"cash", "cash&cashinvestments", "usd", "spaxx", "fdrxx", "swvxx", "vmfxx", "fzfxx"}
)


class PortfolioCSVError(ValueError):
    """Raised when a CSV cannot be interpreted as a portfolio export."""


def _norm_header(header: str) -> str:
    """Collapse a header to comparable form: lowercase, alphanumerics only."""
    return "".join(ch for ch in header.lower() if ch.isalnum())


def _clean_number(raw: str | None) -> float | None:
    """Parse a broker-formatted numeric cell to float, or None when blank.

    Handles ``$1,234.50``, ``(1,234.50)`` (accounting negative), trailing ``%``,
    and stray whitespace. Returns None for empty / dash / N/A cells so the
    schema can treat the value as unknown rather than zero.
    """
    if raw is None:
        return None
    text = raw.strip()
    if not text or text.upper() in {"N/A", "NA", "--", "-", ""}:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]

    text = text.replace(",", "").replace("$", "").replace("%", "").strip()
    if text.startswith("-"):
        negative = True
        text = text[1:]

    if not text:
        return None
    try:
        value = float(text)
    except ValueError as exc:
        raise PortfolioCSVError(f"could not parse numeric value from {raw!r}") from exc
    return -value if negative else value


def _resolve_columns(
    fieldnames: list[str], column_map: dict[str, str] | None
) -> dict[str, str]:
    """Map canonical field -> actual CSV header present in this file.

    ``column_map`` (canonical field -> exact header) takes precedence over the
    built-in aliases, so an unusual export can be handled without code changes.
    """
    normalized = {_norm_header(h): h for h in fieldnames}
    resolved: dict[str, str] = {}

    # Caller overrides first.
    if column_map:
        for field, header in column_map.items():
            key = _norm_header(header)
            if key in normalized:
                resolved[field] = normalized[key]

    for field, aliases in _DEFAULT_ALIASES.items():
        if field in resolved:
            continue
        for alias in aliases:
            if alias in normalized:
                resolved[field] = normalized[alias]
                break
    return resolved


def _infer_price_from_value(
    quantity: float, market_value: float | None
) -> float | None:
    """Derive a per-share price from market value when the export omits price."""
    if market_value is None or quantity == 0:
        return None
    return market_value / quantity


def load_portfolio_from_csv(
    path: str | Path | None = None,
    *,
    content: str | None = None,
    as_of: str | None = None,
    base_currency: str = "USD",
    cash: float | None = None,
    column_map: dict[str, str] | None = None,
) -> Portfolio:
    """Load a broker CSV export into a :class:`Portfolio`.

    Args:
        path: Path to the CSV file. Mutually exclusive with ``content``.
        content: Raw CSV text (useful for tests / piped input).
        as_of: Snapshot date (YYYY-MM-DD) the book reflects.
        base_currency: Reporting currency for cash and aggregate values.
        cash: Explicit cash balance. When None, a cash/sweep row in the CSV
            (matched by symbol) is used if present; otherwise cash is 0.
        column_map: Optional canonical-field -> exact-header overrides for a
            broker whose headers are not covered by the built-in aliases.

    Returns:
        A normalised, symbol-sorted ``Portfolio``.

    Raises:
        PortfolioCSVError: The file is empty, has no recognisable header, or a
            required column (symbol, quantity) cannot be located.
    """
    if (path is None) == (content is None):
        raise PortfolioCSVError("provide exactly one of 'path' or 'content'")

    text = (
        Path(path).expanduser().read_text(encoding="utf-8-sig")
        if content is None
        else content
    )

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise PortfolioCSVError("CSV has no header row")

    columns = _resolve_columns(list(reader.fieldnames), column_map)
    for required in ("symbol", "quantity"):
        if required not in columns:
            raise PortfolioCSVError(
                f"could not find a '{required}' column in headers {reader.fieldnames!r}. "
                f"Pass column_map={{'{required}': '<header>'}} to map it explicitly."
            )

    positions: list[Position] = []
    detected_cash = 0.0
    found_cash_row = False

    for row in reader:
        raw_symbol = (row.get(columns["symbol"]) or "").strip()
        if not raw_symbol:
            continue  # blank / separator / totals row

        # Cash / sweep row: fold into the cash balance rather than a position.
        if _norm_header(raw_symbol) in _CASH_SYMBOLS:
            mv = _clean_number(row.get(columns["market_value"])) if "market_value" in columns else None
            if mv is None and "quantity" in columns:
                mv = _clean_number(row.get(columns["quantity"]))
            if mv is not None:
                detected_cash += mv
                found_cash_row = True
            continue

        quantity = _clean_number(row.get(columns["quantity"]))
        if quantity is None:
            continue  # a row without a share count is not a position

        avg_cost = (
            _clean_number(row.get(columns["avg_cost"])) if "avg_cost" in columns else None
        )
        current_price = (
            _clean_number(row.get(columns["current_price"]))
            if "current_price" in columns
            else None
        )
        market_value = (
            _clean_number(row.get(columns["market_value"]))
            if "market_value" in columns
            else None
        )
        if current_price is None:
            current_price = _infer_price_from_value(quantity, market_value)

        asset_type = (
            (row.get(columns["asset_type"]) or "stock").strip().lower()
            if "asset_type" in columns
            else "stock"
        ) or "stock"
        currency = (
            (row.get(columns["currency"]) or base_currency).strip()
            if "currency" in columns
            else base_currency
        ) or base_currency

        positions.append(
            Position(
                symbol=raw_symbol,
                quantity=quantity,
                avg_cost=avg_cost,
                current_price=current_price,
                asset_type=asset_type,
                currency=currency,
            )
        )

    if not positions and not found_cash_row:
        raise PortfolioCSVError(
            "no positions parsed from CSV; check that the file has data rows and "
            "that symbol/quantity columns are populated"
        )

    resolved_cash = cash if cash is not None else (detected_cash if found_cash_row else 0.0)

    return Portfolio(
        as_of=as_of,
        base_currency=base_currency,
        cash=resolved_cash,
        positions=positions,
    )
