"""Tests for the top-down Market View layer.

Schema rendering, deterministic persistence, and the builder's structured/
fallback paths — all with stubs, no LLM or network.
"""

from types import SimpleNamespace

import pytest

from tradingagents.market_view import (
    MarketRegime,
    MarketView,
    MarketViewBuilder,
    MarketViewStore,
    SizingBias,
    default_macro_context,
)


def _view(**overrides):
    base = {
        "as_of": "2026-01-15",
        "regime": MarketRegime.RISK_OFF,
        "sizing_bias": SizingBias.DEFENSIVE,
        "confidence": "high",
        "narrative": "Rates restrictive, curve inverted, VIX elevated.",
        "key_risks": ["Sticky inflation", "Earnings cuts"],
        "tailwinds": ["Resilient labor market"],
    }
    base.update(overrides)
    return MarketView(**base)


# --- schema / render ------------------------------------------------------

def test_render_contains_regime_and_sections():
    text = _view().render()
    assert "Risk-Off" in text
    assert "Defensive" in text
    assert "As of: 2026-01-15" in text
    assert "Key risks:" in text and "Sticky inflation" in text
    assert "Tailwinds:" in text and "Resilient labor market" in text


def test_render_omits_empty_sections():
    text = _view(key_risks=[], tailwinds=[]).render()
    assert "Key risks:" not in text
    assert "Tailwinds:" not in text


# --- store ----------------------------------------------------------------

def test_store_save_load_roundtrip(tmp_path):
    store = MarketViewStore(tmp_path)
    assert store.load() is None
    store.save(_view())
    loaded = store.load()
    assert loaded.regime is MarketRegime.RISK_OFF
    assert loaded.sizing_bias is SizingBias.DEFENSIVE


def test_store_snapshot_requires_as_of(tmp_path):
    store = MarketViewStore(tmp_path)
    with pytest.raises(ValueError):
        store.snapshot(_view(as_of=None))


def test_store_snapshots_are_dated_and_sorted(tmp_path):
    store = MarketViewStore(tmp_path)
    store.snapshot(_view(as_of="2026-01-16"))
    store.snapshot(_view(as_of="2026-01-14"))
    assert store.snapshot_dates() == ["2026-01-14", "2026-01-16"]
    assert store.load_snapshot("2026-01-14").as_of == "2026-01-14"
    assert store.load_snapshot("2026-02-01") is None


def test_store_dump_is_byte_stable(tmp_path):
    store = MarketViewStore(tmp_path)
    a = store._dump(_view())
    b = store._dump(_view())
    assert a == b


# --- builder --------------------------------------------------------------

class _StubStructured:
    def __init__(self, result):
        self._result = result
        self.prompts: list[str] = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self._result


class _StubLLM:
    def __init__(self, structured_result="__unset__", freetext="fallback narrative", support=True):
        self._structured_result = _view() if structured_result == "__unset__" else structured_result
        self._freetext = freetext
        self._support = support

    def with_structured_output(self, schema):
        if not self._support:
            raise NotImplementedError("no structured output")
        return _StubStructured(self._structured_result)

    def invoke(self, prompt):
        return SimpleNamespace(content=self._freetext)


def _builder(llm):
    return MarketViewBuilder(llm, config=None, gather_context=lambda td, cfg: f"ctx for {td}")


def test_builder_structured_success_sets_as_of():
    # model returns a view with as_of=None; the builder must stamp the run date
    view = _builder(_StubLLM(structured_result=_view(as_of=None))).build("2026-03-02")
    assert view.as_of == "2026-03-02"
    assert view.regime is MarketRegime.RISK_OFF


def test_builder_falls_back_when_structured_returns_none():
    view = _builder(_StubLLM(structured_result=None, freetext="neutral read")).build("2026-03-02")
    assert view.regime is MarketRegime.NEUTRAL
    assert view.confidence == "low"
    assert "neutral read" in view.narrative
    assert view.as_of == "2026-03-02"


def test_builder_falls_back_when_structured_unsupported():
    view = _builder(_StubLLM(support=False, freetext="plain text view")).build("2026-03-02")
    assert view.regime is MarketRegime.NEUTRAL
    assert "plain text view" in view.narrative


def test_builder_renders_to_market_view_string():
    view = _builder(_StubLLM()).build("2026-03-02")
    rendered = view.render()
    assert "Regime:" in rendered
    assert view.as_of == "2026-03-02"


# --- default context gatherer --------------------------------------------

def test_default_macro_context_assembles_sections(monkeypatch):
    import tradingagents.dataflows.interface as interface

    monkeypatch.setattr(
        interface, "route_to_vendor", lambda method, *a, **k: f"[{method}:{a[0]}]"
    )
    text = default_macro_context("2026-01-15", None, indicators=("cpi", "vix"))
    assert "### cpi" in text
    assert "### vix" in text
    assert "### Global macro headlines" in text
    assert "[get_macro_indicators:cpi]" in text


def test_default_macro_context_isolates_indicator_failure(monkeypatch):
    import tradingagents.dataflows.interface as interface

    def boom(method, *a, **k):
        if a and a[0] == "cpi":
            raise RuntimeError("fred down")
        return "ok"

    monkeypatch.setattr(interface, "route_to_vendor", boom)
    text = default_macro_context("2026-01-15", None, indicators=("cpi", "vix"))
    assert "unavailable: fred down" in text
    assert "### vix\nok" in text
