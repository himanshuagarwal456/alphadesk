"""Tests for the portfolio-awareness integration layer.

Covers stance routing, prompt-context rendering, initial-state threading, and
the book runner. All pure/deterministic — no LLM or network calls — so they run
in the unit suite.
"""

from tradingagents.graph.propagation import Propagator
from tradingagents.portfolio import (
    Portfolio,
    Position,
    Stance,
    classify_stance,
    iter_book_targets,
    render_market_view,
    render_portfolio_context,
    run_book,
)


def _book():
    return Portfolio(
        as_of="2026-01-15",
        base_currency="USD",
        cash=10_000.0,
        positions=[
            Position(symbol="NVDA", quantity=100, avg_cost=100.0, current_price=150.0),
            Position(symbol="AAPL", quantity=50, avg_cost=200.0, current_price=180.0),
        ],
    )


# --- stance routing -------------------------------------------------------

def test_classify_stance_held_is_manage():
    assert classify_stance(_book(), "NVDA") is Stance.MANAGE
    assert classify_stance(_book(), "nvda") is Stance.MANAGE  # case-insensitive


def test_classify_stance_unheld_is_initiate():
    assert classify_stance(_book(), "TSLA") is Stance.INITIATE


def test_classify_stance_none_portfolio_is_initiate():
    assert classify_stance(None, "NVDA") is Stance.INITIATE


# --- context rendering ----------------------------------------------------

def test_render_context_empty_without_book_or_view():
    assert render_portfolio_context(None, "NVDA") == ""


def test_render_context_manage_mentions_position():
    text = render_portfolio_context(_book(), "NVDA")
    assert "MANAGE" in text
    assert "NVDA" in text
    assert "Average cost" in text
    assert "Current holdings" in text
    # concentration reported when priced
    assert "concentration" in text.lower()


def test_render_context_initiate_for_new_name():
    text = render_portfolio_context(_book(), "TSLA")
    assert "INITIATE" in text
    assert "Cash available" in text


def test_render_context_includes_market_view():
    text = render_portfolio_context(_book(), "TSLA", market_view="Risk-off; defensives favored.")
    assert "Market View" in text
    assert "Risk-off" in text


def test_render_market_view_blank_is_empty():
    assert render_market_view("   ") == ""
    assert "Market View" in render_market_view("bullish regime")


def test_render_context_unpriced_book_notes_unknown_exposure():
    book = Portfolio(positions=[Position(symbol="XYZ", quantity=10)])
    text = render_portfolio_context(book, "XYZ")
    assert "unknown" in text.lower()


# --- initial-state threading ---------------------------------------------

def test_create_initial_state_defaults_empty_portfolio_fields():
    state = Propagator().create_initial_state("NVDA", "2026-01-15")
    assert state["portfolio_context"] == ""
    assert state["position_stance"] == ""
    assert state["market_view"] == ""


def test_create_initial_state_threads_portfolio_fields():
    state = Propagator().create_initial_state(
        "NVDA",
        "2026-01-15",
        portfolio_context="## Portfolio Context\nheld",
        position_stance="manage",
        market_view="risk-on",
    )
    assert state["position_stance"] == "manage"
    assert "held" in state["portfolio_context"]
    assert state["market_view"] == "risk-on"


# --- book runner ----------------------------------------------------------

def test_iter_book_targets_holdings_first_then_candidates():
    targets = iter_book_targets(_book(), watchlist=["TSLA", "MSFT"])
    symbols = [t.symbol for t in targets]
    # held names (sorted) come before candidates (sorted)
    assert symbols == ["AAPL", "NVDA", "MSFT", "TSLA"]
    stances = {t.symbol: t.stance for t in targets}
    assert stances["AAPL"] is Stance.MANAGE
    assert stances["NVDA"] is Stance.MANAGE
    assert stances["TSLA"] is Stance.INITIATE
    assert stances["MSFT"] is Stance.INITIATE


def test_iter_book_targets_dedupes_held_and_watchlist():
    targets = iter_book_targets(_book(), watchlist=["nvda", "TSLA"])
    nvda = [t for t in targets if t.symbol == "NVDA"]
    assert len(nvda) == 1
    assert nvda[0].stance is Stance.MANAGE


def test_iter_book_targets_none_portfolio_all_initiate():
    targets = iter_book_targets(None, watchlist=["TSLA", "MSFT"])
    assert [t.symbol for t in targets] == ["MSFT", "TSLA"]
    assert all(t.stance is Stance.INITIATE for t in targets)


class _StubGraph:
    def __init__(self, fail_on=None):
        self.calls = []
        self._fail_on = fail_on or set()

    def propagate(self, company_name, trade_date, asset_type="stock", portfolio=None, market_view=""):
        self.calls.append(
            {"symbol": company_name, "portfolio": portfolio, "market_view": market_view}
        )
        if company_name in self._fail_on:
            raise RuntimeError("boom")
        return ({"company_of_interest": company_name}, f"BUY {company_name}")


def test_run_book_runs_each_target_with_portfolio():
    book = _book()
    graph = _StubGraph()
    results = run_book(graph, "2026-01-15", book, watchlist=["TSLA"], market_view="mv")

    assert set(results) == {"AAPL", "NVDA", "TSLA"}
    assert results["NVDA"]["stance"] == "manage"
    assert results["TSLA"]["stance"] == "initiate"
    assert results["TSLA"]["decision"] == "BUY TSLA"
    # portfolio + market view forwarded to every call
    assert all(c["portfolio"] is book for c in graph.calls)
    assert all(c["market_view"] == "mv" for c in graph.calls)


def test_run_book_isolates_per_name_failure():
    graph = _StubGraph(fail_on={"NVDA"})
    results = run_book(graph, "2026-01-15", _book())
    assert "error" in results["NVDA"]
    assert "decision" in results["AAPL"]
