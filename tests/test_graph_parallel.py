"""Analyst layer parallelization: fan-out/fan-in wiring and compilation.

These are structure tests — they build the graph with mock LLMs and real
(empty-tool) ToolNodes and assert the topology, without running any LLM. A live
multi-agent run still needs provider keys and is exercised separately.
"""

from unittest.mock import MagicMock

import pytest
from langchain_core.tools import tool
from langgraph.graph import START
from langgraph.prebuilt import ToolNode

from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.setup import GraphSetup

ALL_ANALYSTS = ("market", "social", "news", "fundamentals")
ANALYST_NODES = {
    "market": "Market Analyst",
    "social": "Sentiment Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}


@tool
def _noop_tool(query: str) -> str:
    """A stand-in tool so ToolNode construction is valid in tests."""
    return query


def _build_setup() -> GraphSetup:
    tool_nodes = {key: ToolNode([_noop_tool]) for key in ALL_ANALYSTS}
    return GraphSetup(
        quick_thinking_llm=MagicMock(),
        deep_thinking_llm=MagicMock(),
        tool_nodes=tool_nodes,
        conditional_logic=ConditionalLogic(),
    )


@pytest.mark.unit
class TestAnalystParallelization:
    def test_all_analysts_fan_out_from_start(self):
        workflow = _build_setup().setup_graph(ALL_ANALYSTS)
        for key in ALL_ANALYSTS:
            assert (START, ANALYST_NODES[key]) in workflow.edges

    def test_all_analysts_fan_in_to_bull_researcher(self):
        workflow = _build_setup().setup_graph(ALL_ANALYSTS)
        for key in ALL_ANALYSTS:
            assert (ANALYST_NODES[key], "Bull Researcher") in workflow.edges

    def test_no_serial_analyst_chain(self):
        # No analyst should edge directly into another analyst anymore.
        workflow = _build_setup().setup_graph(ALL_ANALYSTS)
        analyst_node_names = set(ANALYST_NODES.values())
        for src, dst in workflow.edges:
            if src in analyst_node_names:
                assert dst == "Bull Researcher"

    def test_clear_and_tool_nodes_removed_from_parent(self):
        workflow = _build_setup().setup_graph(ALL_ANALYSTS)
        for node_name in workflow.nodes:
            assert not node_name.startswith("Msg Clear")
            assert not node_name.startswith("tools_")

    def test_graph_compiles(self):
        workflow = _build_setup().setup_graph(ALL_ANALYSTS)
        compiled = workflow.compile()
        assert compiled is not None

    def test_subset_of_analysts(self):
        workflow = _build_setup().setup_graph(("market", "news"))
        assert (START, "Market Analyst") in workflow.edges
        assert (START, "News Analyst") in workflow.edges
        assert "Sentiment Analyst" not in workflow.nodes
        assert (START, "Fundamentals Analyst") not in workflow.edges
