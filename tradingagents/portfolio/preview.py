"""Soft CSV import preview with per-row validation for the portfolio product.

Unlike :func:`load_portfolio_from_csv`, preview never hard-fails on a single
bad data row: each row is classified as ok / skipped / error / cash so the
user can remap columns or fix cells before confirming the book.
"""

from __future__ import annotations

import csv
import io
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from .csv_loader import (
    _CASH_SYMBOLS,
    PortfolioCSVError,
    _clean_number,
    _infer_price_from_value,
    _norm_header,
    _resolve_columns,
)
from .schemas import Portfolio, Position


class RowStatus(str, Enum):
    OK = "ok"
    SKIPPED = "skipped"
    ERROR = "error"
    CASH = "cash"


class ImportRowResult(BaseModel):
    row_number: int = Field(ge=1, description="1-based data row number (header is row 0).")
    status: RowStatus
    symbol: str | None = None
    message: str = ""
    position: Position | None = None


class ImportPreview(BaseModel):
    """Dry-run import result shown before the user confirms a book."""

    headers: list[str]
    resolved_columns: dict[str, str]
    unmapped_headers: list[str]
    rows: list[ImportRowResult]
    portfolio: Portfolio | None = None
    ok_rows: int = 0
    error_rows: int = 0
    skipped_rows: int = 0
    cash_rows: int = 0
    row_success_rate: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="ok / (ok + error) among attempted position rows; skipped blanks excluded.",
    )
    fatal_error: str | None = None
    research_only: bool = True
    can_confirm: bool = False


def preview_portfolio_csv(
    path: str | Path | None = None,
    *,
    content: str | None = None,
    as_of: str | None = None,
    base_currency: str = "USD",
    cash: float | None = None,
    column_map: dict[str, str] | None = None,
) -> ImportPreview:
    """Parse a broker CSV into a preview with per-row diagnostics."""
    if (path is None) == (content is None):
        return ImportPreview(
            headers=[],
            resolved_columns={},
            unmapped_headers=[],
            rows=[],
            fatal_error="provide exactly one of 'path' or 'content'",
        )

    text = (
        Path(path).expanduser().read_text(encoding="utf-8-sig")
        if content is None
        else content
    )
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return ImportPreview(
            headers=[],
            resolved_columns={},
            unmapped_headers=[],
            rows=[],
            fatal_error="CSV has no header row",
        )

    headers = list(reader.fieldnames)
    try:
        columns = _resolve_columns(headers, column_map)
    except Exception as exc:  # pragma: no cover - resolver is pure
        return ImportPreview(
            headers=headers,
            resolved_columns={},
            unmapped_headers=headers,
            rows=[],
            fatal_error=str(exc),
        )

    mapped_headers = set(columns.values())
    unmapped = [h for h in headers if h not in mapped_headers]

    missing = [name for name in ("symbol", "quantity") if name not in columns]
    if missing:
        return ImportPreview(
            headers=headers,
            resolved_columns=columns,
            unmapped_headers=unmapped,
            rows=[],
            fatal_error=(
                f"could not find column(s) {missing} in headers {headers!r}. "
                "Pass column_map to map them explicitly, then preview again."
            ),
        )

    rows: list[ImportRowResult] = []
    positions: list[Position] = []
    detected_cash = 0.0
    found_cash_row = False

    for index, row in enumerate(reader, start=1):
        raw_symbol = (row.get(columns["symbol"]) or "").strip()
        if not raw_symbol:
            rows.append(
                ImportRowResult(
                    row_number=index,
                    status=RowStatus.SKIPPED,
                    message="blank symbol",
                )
            )
            continue

        if _norm_header(raw_symbol) in _CASH_SYMBOLS:
            try:
                mv = (
                    _clean_number(row.get(columns["market_value"]))
                    if "market_value" in columns
                    else None
                )
                if mv is None:
                    mv = _clean_number(row.get(columns["quantity"]))
            except PortfolioCSVError as exc:
                rows.append(
                    ImportRowResult(
                        row_number=index,
                        status=RowStatus.ERROR,
                        symbol=raw_symbol,
                        message=str(exc),
                    )
                )
                continue
            if mv is not None:
                detected_cash += mv
                found_cash_row = True
            rows.append(
                ImportRowResult(
                    row_number=index,
                    status=RowStatus.CASH,
                    symbol=raw_symbol.upper(),
                    message=f"folded into cash ({mv if mv is not None else 'unknown'})",
                )
            )
            continue

        try:
            quantity = _clean_number(row.get(columns["quantity"]))
            if quantity is None:
                rows.append(
                    ImportRowResult(
                        row_number=index,
                        status=RowStatus.SKIPPED,
                        symbol=raw_symbol.upper(),
                        message="missing quantity",
                    )
                )
                continue
            avg_cost = (
                _clean_number(row.get(columns["avg_cost"]))
                if "avg_cost" in columns
                else None
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
            position = Position(
                symbol=raw_symbol,
                quantity=quantity,
                avg_cost=avg_cost,
                current_price=current_price,
                asset_type=asset_type,
                currency=currency,
            )
        except (PortfolioCSVError, ValueError) as exc:
            rows.append(
                ImportRowResult(
                    row_number=index,
                    status=RowStatus.ERROR,
                    symbol=raw_symbol.upper() if raw_symbol else None,
                    message=str(exc),
                )
            )
            continue

        positions.append(position)
        price_note = (
            "price unknown (not zero)"
            if position.current_price is None
            else f"price={position.current_price}"
        )
        rows.append(
            ImportRowResult(
                row_number=index,
                status=RowStatus.OK,
                symbol=position.symbol,
                message=price_note,
                position=position,
            )
        )

    ok = sum(1 for r in rows if r.status is RowStatus.OK)
    err = sum(1 for r in rows if r.status is RowStatus.ERROR)
    skipped = sum(1 for r in rows if r.status is RowStatus.SKIPPED)
    cash_rows = sum(1 for r in rows if r.status is RowStatus.CASH)
    attempted = ok + err
    success_rate = (ok / attempted) if attempted else 0.0

    portfolio = None
    if positions or found_cash_row:
        resolved_cash = cash if cash is not None else (detected_cash if found_cash_row else 0.0)
        portfolio = Portfolio(
            as_of=as_of,
            base_currency=base_currency,
            cash=resolved_cash,
            positions=positions,
        )

    return ImportPreview(
        headers=headers,
        resolved_columns=columns,
        unmapped_headers=unmapped,
        rows=rows,
        portfolio=portfolio,
        ok_rows=ok,
        error_rows=err,
        skipped_rows=skipped,
        cash_rows=cash_rows,
        row_success_rate=success_rate,
        can_confirm=portfolio is not None and ok > 0 and err == 0,
        research_only=True,
    )
