"""
Stateful LangGraph agent — assignment Service 4.

Nodes:
  1. planner        — choose tools from descriptions
  2. tool_execution — invoke RAG and/or Image Analyser over HTTP
  3. synthesiser    — combine tool outputs into final answer
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.llm import plan_tools, synthesise_answer
from app.prompts import TOOL_DESCRIPTIONS_VERSION
from app.tools import TOOL_IMAGE, TOOL_RAG, call_image_analyser, call_rag_service


class AgentState(TypedDict):
    query: str
    image_url: str | None
    plan: list[str]
    plan_rationale: str
    tool_results: dict[str, Any]
    tools_used: list[str]
    reasoning_steps: list[str]
    answer: str


def _planner_node(state: AgentState) -> dict[str, Any]:
    query = state["query"]
    image_url = state.get("image_url")
    planned = plan_tools(query, image_url)
    tools = list(planned.get("tools") or [])
    rationale = str(planned.get("rationale") or "")

    step = (
        f"Planner ({TOOL_DESCRIPTIONS_VERSION}): selected tools={tools}. "
        f"Rationale: {rationale}"
    )
    steps = list(state.get("reasoning_steps") or [])
    steps.append(step)
    return {
        "plan": tools,
        "plan_rationale": rationale,
        "reasoning_steps": steps,
    }


def _tool_execution_node(state: AgentState) -> dict[str, Any]:
    query = state["query"]
    image_url = state.get("image_url")
    plan = list(state.get("plan") or [])
    results: dict[str, Any] = dict(state.get("tool_results") or {})
    used: list[str] = list(state.get("tools_used") or [])
    steps = list(state.get("reasoning_steps") or [])

    # Build RAG description from query; enrich with imaging if already run
    rag_description = query

    for tool_name in plan:
        if tool_name == TOOL_IMAGE:
            if not image_url:
                steps.append("Tool execution: skipped image_analyser (no image_url).")
                continue
            out = call_image_analyser(image_url)
            results[TOOL_IMAGE] = out
            if TOOL_IMAGE not in used:
                used.append(TOOL_IMAGE)
            if out.get("ok"):
                r = out["result"]
                steps.append(
                    "Tool execution: image_analyser -> "
                    f"body_region={r.get('body_region')}, "
                    f"condition_score={r.get('condition_score')}, "
                    f"confidence={r.get('confidence')}"
                )
                rag_description = (
                    f"{query} Imaging triage: body_region={r.get('body_region')}, "
                    f"condition_score={r.get('condition_score')}."
                )
            else:
                steps.append(f"Tool execution: image_analyser failed - {out.get('error')}")

        elif tool_name == TOOL_RAG:
            out = call_rag_service(rag_description)
            results[TOOL_RAG] = out
            if TOOL_RAG not in used:
                used.append(TOOL_RAG)
            if out.get("ok"):
                listings = (out.get("result") or {}).get("similar_listings") or []
                ids = [
                    str(x.get("id"))
                    for x in listings
                    if isinstance(x, dict) and x.get("id")
                ]
                steps.append(
                    "Tool execution: rag_service -> "
                    f"{len(listings)} listing(s); ids={ids or 'n/a'}"
                )
            else:
                steps.append(f"Tool execution: rag_service failed - {out.get('error')}")

        else:
            steps.append(f"Tool execution: unknown tool '{tool_name}' ignored.")

    return {
        "tool_results": results,
        "tools_used": used,
        "reasoning_steps": steps,
    }


def _synthesiser_node(state: AgentState) -> dict[str, Any]:
    steps = list(state.get("reasoning_steps") or [])
    answer = synthesise_answer(
        query=state["query"],
        image_url=state.get("image_url"),
        tools_used=list(state.get("tools_used") or []),
        tool_results=dict(state.get("tool_results") or {}),
        reasoning_steps=steps,
    )
    steps.append("Synthesiser: produced final answer from tool outputs.")
    return {"answer": answer, "reasoning_steps": steps}


def build_agent():
    """Compile planner → tool_execution → synthesiser graph."""
    graph = StateGraph(AgentState)
    graph.add_node("planner", _planner_node)
    graph.add_node("tool_execution", _tool_execution_node)
    graph.add_node("synthesiser", _synthesiser_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "tool_execution")
    graph.add_edge("tool_execution", "synthesiser")
    graph.add_edge("synthesiser", END)

    return graph.compile()


AGENT = build_agent()


def run_agent(query: str, image_url: str | None = None) -> dict[str, Any]:
    """Execute the graph and return assignment-shaped output fields."""
    initial: AgentState = {
        "query": query.strip(),
        "image_url": image_url.strip() if image_url else None,
        "plan": [],
        "plan_rationale": "",
        "tool_results": {},
        "tools_used": [],
        "reasoning_steps": [],
        "answer": "",
    }
    final = AGENT.invoke(initial)
    return {
        "answer": final.get("answer") or "",
        "tools_used": list(final.get("tools_used") or []),
        "reasoning_steps": list(final.get("reasoning_steps") or []),
    }
