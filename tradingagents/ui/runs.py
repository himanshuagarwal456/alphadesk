"""Load completed runs saved on disk into ``final_state``-shaped dicts.

``TradingAgentsGraph`` writes each run to
``<results_dir>/<ticker>/TradingAgentsStrategy_logs/full_states_log_<date>.json``.
This loader reads those back so the feed can be built from past runs with no
re-analysis, returning the latest run per ticker (most-recent first).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_saved_runs(results_dir: str | Path) -> list[dict[str, Any]]:
    """Return the latest saved ``final_state`` per ticker, most-recent first."""
    base = Path(results_dir).expanduser()
    if not base.exists():
        return []

    latest: dict[str, tuple[float, dict]] = {}
    for log in base.glob("*/TradingAgentsStrategy_logs/full_states_log_*.json"):
        try:
            data = json.loads(log.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        # The saved log names the trader field differently from the live state.
        if "trader_investment_plan" not in data and "trader_investment_decision" in data:
            data["trader_investment_plan"] = data["trader_investment_decision"]
        symbol = (data.get("company_of_interest") or "").upper()
        if not symbol:
            continue
        mtime = log.stat().st_mtime
        if symbol not in latest or mtime > latest[symbol][0]:
            latest[symbol] = (mtime, data)

    return [data for _, data in sorted(latest.values(), key=lambda x: -x[0])]
