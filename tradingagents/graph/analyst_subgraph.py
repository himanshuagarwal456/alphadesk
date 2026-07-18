"""Per-analyst subgraphs for parallel fan-out execution.

The original graph ran the analysts serially on a single shared ``messages``
channel, inserting "Msg Clear" nodes between them so one analyst's tool-call
transcript did not leak into the next. That design is inherently sequential:
each analyst waits for the previous one even though they are independent (each
reads only the ticker and date).

Here, each analyst is compiled into its own small subgraph with an **isolated**
``messages`` channel (its tool-call loop lives entirely inside the subgraph),
and a thin *runner* invokes that subgraph and returns only the analyst's report
key to the parent graph. Because the runner never writes to the parent
``messages`` channel, the four runners can be fanned out from ``START`` and run
concurrently, then fan back in to the Bull Researcher — no shared-state
collision, no clear nodes.

Trade-off: the analyst's intra-loop tool-call messages no longer surface on the
parent graph's value stream, so the CLI's live "messages & tools" panel shows
analyst progress at report granularity (pending -> completed) rather than
streaming each tool call. Reports, status tracking, and saved output are
unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from tradingagents.agents.utils.agent_states import AgentState

from .analyst_execution import AnalystNodeSpec

# State keys the parent seeds into each analyst subgraph. Only read-only run
# inputs are forwarded; the subgraph's ``messages`` channel starts fresh and
# stays local, which is what makes parallel fan-out safe.
_FORWARDED_STATE_KEYS = (
    "company_of_interest",
    "trade_date",
    "asset_type",
    "instrument_context",
)


def _tools_or_end(state: AgentState) -> str:
    """Route an analyst turn: run tools if it asked for them, else finish.

    Mirrors the old ``ConditionalLogic.should_continue_*`` check but returns the
    subgraph-local ``tools`` node or ``END`` instead of parent node names, so a
    subgraph is self-contained. Analysts that never call tools (e.g. the
    Sentiment Analyst, which pre-fetches its data) simply fall straight to END.
    """
    messages = state["messages"]
    if not messages:
        return END
    last_message = messages[-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def build_analyst_subgraph(analyst_node: Callable, tool_node: Any):
    """Compile a single analyst + its tool loop into an isolated subgraph.

    Args:
        analyst_node: The analyst node function (e.g. from
            ``create_market_analyst``). Reads ``messages`` + run inputs, writes
            its report key and an assistant message.
        tool_node: The ``ToolNode`` holding this analyst's tools.

    Returns:
        A compiled LangGraph runnable with its own ``messages`` channel.
    """
    subgraph = StateGraph(AgentState)
    subgraph.add_node("agent", analyst_node)
    subgraph.add_node("tools", tool_node)

    subgraph.add_edge(START, "agent")
    subgraph.add_conditional_edges("agent", _tools_or_end, {"tools": "tools", END: END})
    subgraph.add_edge("tools", "agent")

    return subgraph.compile()


def make_analyst_runner(subgraph: Any, spec: AnalystNodeSpec) -> Callable:
    """Wrap a compiled analyst subgraph as a parent-graph node.

    The runner seeds the subgraph with a fresh ``messages`` list (so nothing
    from the parent or sibling analysts contaminates it) plus the read-only run
    inputs, then returns *only* the analyst's report key to the parent. Keeping
    the write surface to a single, analyst-specific key is what lets the parent
    fan these out in parallel without concurrent-write conflicts.
    """

    def analyst_runner(state: AgentState) -> dict:
        sub_state: dict[str, Any] = {
            "messages": [("human", state["company_of_interest"])],
        }
        for key in _FORWARDED_STATE_KEYS:
            if key in state:
                sub_state[key] = state[key]

        result = subgraph.invoke(sub_state)
        update = {spec.report_key: result.get(spec.report_key, "")}
        # Analysts with structured output also emit a canonical payload under
        # "<report_key>_struct"; forward it when present so the parent state
        # keeps the structured object (markdown stays presentation-only).
        struct_key = f"{spec.report_key}_struct"
        if result.get(struct_key) is not None:
            update[struct_key] = result[struct_key]
        return update

    return analyst_runner
