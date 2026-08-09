"""LLM helpers for planner + synthesiser (OpenAI API or heuristic fallback)."""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import (
    AGENT_LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
)
from app.prompts import PLANNER_SYSTEM, SYNTHESISER_SYSTEM
from app.tools import TOOL_IMAGE, TOOL_RAG


def _openai_chat(system: str, user: str) -> str:
    from openai import OpenAI

    kwargs: dict[str, Any] = {"api_key": OPENAI_API_KEY}
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    client = OpenAI(**kwargs)
    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = completion.choices[0].message.content or ""
    return content.strip()


def llm_available() -> bool:
    if AGENT_LLM_PROVIDER == "heuristic":
        return False
    return bool(OPENAI_API_KEY)


def plan_tools(query: str, image_url: str | None) -> dict[str, Any]:
    """
    Return {"tools": [...], "rationale": "..."}.
    Uses OpenAI when configured; otherwise heuristic planner.
    """
    if llm_available():
        user = (
            f"Complex question:\n{query}\n\n"
            f"image_url provided: {bool(image_url)}\n"
            f"image_url: {image_url or 'none'}\n"
        )
        raw = _openai_chat(PLANNER_SYSTEM, user)
        parsed = _extract_json(raw)
        if parsed and isinstance(parsed.get("tools"), list):
            tools = [t for t in parsed["tools"] if t in (TOOL_IMAGE, TOOL_RAG)]
            if not image_url:
                tools = [t for t in tools if t != TOOL_IMAGE]
            if not tools:
                tools = [TOOL_RAG]
            return {
                "tools": tools,
                "rationale": str(parsed.get("rationale") or "LLM planner"),
            }

    return _heuristic_plan(query, image_url)


def synthesise_answer(
    query: str,
    image_url: str | None,
    tools_used: list[str],
    tool_results: dict[str, Any],
    reasoning_steps: list[str],
) -> str:
    if llm_available():
        user = (
            f"Question:\n{query}\n\n"
            f"image_url: {image_url or 'none'}\n\n"
            f"tools_used: {tools_used}\n\n"
            f"reasoning_steps:\n- " + "\n- ".join(reasoning_steps) + "\n\n"
            f"tool_results JSON:\n{json.dumps(tool_results, ensure_ascii=False, indent=2)}\n"
        )
        return _openai_chat(SYNTHESISER_SYSTEM, user)

    return _heuristic_synthesis(query, tools_used, tool_results)


def _heuristic_plan(query: str, image_url: str | None) -> dict[str, Any]:
    q = query.lower()
    tools: list[str] = []
    needs_image = bool(image_url) and any(
        k in q
        for k in (
            "image",
            "x-ray",
            "xray",
            "radiograph",
            "imaging",
            "region",
            "condition_score",
            "fracture",
            "severity",
            "hip",
            "knee",
            "ankle",
            "foot",
        )
    )
    if image_url and (needs_image or "protocol" in q or "rtp" in q or "case" in q or len(q) > 40):
        tools.append(TOOL_IMAGE)
    elif image_url and needs_image:
        tools.append(TOOL_IMAGE)

    image_only = bool(image_url) and any(
        k in q for k in ("only image", "just the x-ray", "imaging only", "region only")
    )
    if not image_only:
        tools.append(TOOL_RAG)
    elif not tools:
        tools.append(TOOL_RAG)

    seen: set[str] = set()
    ordered: list[str] = []
    for t in tools:
        if t not in seen:
            seen.add(t)
            ordered.append(t)

    rationale = (
        "Heuristic planner: "
        + ("include image_analyser (URL present); " if TOOL_IMAGE in ordered else "")
        + ("include rag_service for club evidence." if TOOL_RAG in ordered else "")
    )
    return {"tools": ordered, "rationale": rationale}


def _heuristic_synthesis(
    query: str,
    tools_used: list[str],
    tool_results: dict[str, Any],
) -> str:
    parts: list[str] = [f"Answer to: {query}", ""]

    img = tool_results.get(TOOL_IMAGE)
    if img:
        if img.get("ok"):
            r = img["result"]
            parts.append(
                "Imaging triage: "
                f"body_region={r.get('body_region')}, "
                f"condition_score={r.get('condition_score')}, "
                f"confidence={r.get('confidence')}, "
                f"imaging_reliable={r.get('imaging_reliable')}."
            )
        else:
            parts.append(f"Imaging triage unavailable: {img.get('error')}")

    rag = tool_results.get(TOOL_RAG)
    if rag:
        if rag.get("ok"):
            result = rag["result"]
            insight = result.get("insight") or ""
            listings = result.get("similar_listings") or []
            ids = [str(x.get("id")) for x in listings if isinstance(x, dict) and x.get("id")]
            parts.append("")
            parts.append("Club knowledge:")
            if insight:
                parts.append(insight)
            if ids:
                parts.append("Retrieved IDs: " + ", ".join(ids))
        else:
            parts.append(f"RAG unavailable: {rag.get('error')}")

    parts.append("")
    parts.append(f"Tools used: {', '.join(tools_used) or 'none'}.")
    parts.append(
        "Note: synthesis used heuristic mode (set OPENAI_API_KEY + AGENT_LLM_PROVIDER=openai for LLM synthesis)."
    )
    return "\n".join(parts)


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
