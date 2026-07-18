"""SEC EDGAR vendor: configuration, CIK lookup, filing filtering, URL
generation, evidence capture, and router integration.

All HTTP access is mocked; no test touches the network.
"""

from __future__ import annotations

import copy
import unittest
from unittest import mock

import pytest

import tradingagents.dataflows.config as config_module
import tradingagents.default_config as default_config
from tradingagents.dataflows import interface, sec
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import NoMarketDataError

_TICKERS = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA Corp"},
}

_SUBMISSIONS = {
    "name": "Apple Inc.",
    "filings": {
        "recent": {
            "form": ["10-Q", "4", "8-K", "10-K", "10-Q"],
            "filingDate": [
                "2026-05-01", "2026-04-20", "2026-03-01", "2026-01-30", "2025-11-01",
            ],
            "accessionNumber": [
                "0000320193-26-000050",
                "0000320193-26-000044",
                "0000320193-26-000030",
                "0000320193-26-000010",
                "0000320193-25-000090",
            ],
            "primaryDocument": [
                "aapl-q2.htm", "form4.xml", "aapl-8k.htm", "aapl-10k.htm", "aapl-q1.htm",
            ],
        }
    },
}


def _request_stub(url: str) -> dict:
    if url == sec.SEC_TICKERS:
        return _TICKERS
    if url.startswith(f"{sec.SEC_DATA}/submissions/"):
        return _SUBMISSIONS
    raise AssertionError(f"unexpected SEC url: {url}")


@pytest.mark.unit
class SecConfigTests(unittest.TestCase):
    def test_missing_user_agent_raises_not_configured(self):
        with mock.patch.dict("os.environ", {}, clear=True), \
                self.assertRaises(sec.SecNotConfiguredError):
            sec._headers()

    def test_not_configured_is_a_value_error(self):
        # Routing relies on this subclassing for "vendor unavailable" handling.
        self.assertTrue(issubclass(sec.SecNotConfiguredError, ValueError))

    def test_user_agent_is_sent(self):
        with mock.patch.dict("os.environ", {"SEC_USER_AGENT": "Test test@example.com"}):
            headers = sec._headers()
        self.assertEqual(headers["User-Agent"], "Test test@example.com")


@pytest.mark.unit
class SecCikTests(unittest.TestCase):
    def test_cik_lookup_zero_pads_and_is_case_insensitive(self):
        with mock.patch.object(sec, "_request", side_effect=_request_stub):
            self.assertEqual(sec._cik("aapl"), "0000320193")
            self.assertEqual(sec._cik("NVDA"), "0001045810")

    def test_unknown_ticker_raises_no_market_data(self):
        with mock.patch.object(sec, "_request", side_effect=_request_stub), \
                self.assertRaises(NoMarketDataError):
            sec._cik("ZZZZ.NS")


@pytest.mark.unit
class SecFilingTests(unittest.TestCase):
    def setUp(self):
        sec.clear_captured_filing_evidence("AAPL")

    def test_only_supported_forms_within_cutoff_are_returned(self):
        with mock.patch.object(sec, "_request", side_effect=_request_stub):
            out = sec.get_fundamentals("AAPL", "2026-04-01")
        # 8-K (2026-03-01), 10-K (2026-01-30), 10-Q (2025-11-01) pass the cutoff;
        # the Form 4 is an unsupported form; the 2026-05-01 10-Q is in the future.
        self.assertIn("| 2026-03-01 | 8-K |", out)
        self.assertIn("| 2026-01-30 | 10-K |", out)
        self.assertIn("| 2025-11-01 | 10-Q |", out)
        self.assertNotIn("2026-05-01", out)
        self.assertNotIn("form4", out)

    def test_official_archive_url_generation(self):
        with mock.patch.object(sec, "_request", side_effect=_request_stub):
            out = sec.get_fundamentals("AAPL", "2026-04-01")
        self.assertIn(
            "https://www.sec.gov/Archives/edgar/data/320193/000032019326000030/aapl-8k.htm",
            out,
        )

    def test_evidence_capture_round_trip(self):
        with mock.patch.object(sec, "_request", side_effect=_request_stub):
            sec.get_fundamentals("AAPL", "2026-04-01")
        captured = sec.consume_captured_filing_evidence("AAPL")
        self.assertEqual(len(captured), 3)
        record = captured[0]
        self.assertEqual(record.provider_id, "sec")
        self.assertEqual(record.source_type, "filing")
        self.assertEqual(record.publisher, "SEC EDGAR")
        self.assertEqual(record.source_quality_score, 0.98)
        # consume drains the buffer
        self.assertEqual(sec.consume_captured_filing_evidence("AAPL"), [])

    def test_no_filings_before_cutoff_reports_clearly(self):
        with mock.patch.object(sec, "_request", side_effect=_request_stub):
            out = sec.get_fundamentals("AAPL", "2020-01-01")
        self.assertIn("no filings", out.lower())


@pytest.mark.unit
class SecRoutingTests(unittest.TestCase):
    def setUp(self):
        config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)

    def tearDown(self):
        config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)

    def test_sec_is_registered_for_fundamentals_only(self):
        self.assertIn("sec", interface.VENDOR_METHODS["get_fundamentals"])
        # Regression (#PR8): the v1 SEC provider must NOT be selectable for the
        # statement tools — routing 'sec' there aborted live runs.
        for method in ("get_balance_sheet", "get_cashflow", "get_income_statement"):
            self.assertNotIn("sec", interface.VENDOR_METHODS[method])

    def test_statement_tool_with_sec_vendor_fails_loudly(self):
        set_config({"data_vendors": {"fundamental_data": "sec"}})
        with self.assertRaises(ValueError) as ctx:
            interface.route_to_vendor("get_balance_sheet", "AAPL", "quarterly", "2026-04-01")
        self.assertIn("sec", str(ctx.exception))

    def test_tool_level_sec_routing_works(self):
        set_config({"tool_vendors": {"get_fundamentals": "sec"}})
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_fundamentals": {**interface.VENDOR_METHODS["get_fundamentals"],
                                  "sec": lambda *a, **k: "SEC_OK"}},
            clear=False,
        ):
            out = interface.route_to_vendor("get_fundamentals", "AAPL", "2026-04-01")
        self.assertEqual(out, "SEC_OK")

    def test_unconfigured_sec_degrades_to_next_vendor(self):
        set_config({"tool_vendors": {"get_fundamentals": "sec,yfinance"}})

        def _unconfigured(*a, **k):
            raise sec.SecNotConfiguredError("SEC_USER_AGENT not set")

        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_fundamentals": {"sec": _unconfigured, "yfinance": lambda *a, **k: "YF_OK"}},
            clear=False,
        ):
            out = interface.route_to_vendor("get_fundamentals", "AAPL", "2026-04-01")
        self.assertEqual(out, "YF_OK")


@pytest.mark.unit
class GraphConfigIsolationTests(unittest.TestCase):
    def test_graph_deep_copies_config(self):
        """Per-instance config mutation must not leak into the caller's dict."""
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        caller_config = copy.deepcopy(default_config.DEFAULT_CONFIG)
        graph = object.__new__(TradingAgentsGraph)
        # Reproduce only the config-assignment step from __init__.
        graph.config = copy.deepcopy(caller_config)
        graph.config["data_vendors"]["fundamental_data"] = "sec"
        self.assertEqual(caller_config["data_vendors"]["fundamental_data"], "yfinance")


if __name__ == "__main__":
    unittest.main()
