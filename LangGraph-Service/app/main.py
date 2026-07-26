"""
AthleteCare LangGraph Agent — assignment Service 4.

Endpoints:
  GET  /health
  GET  /
  POST /agent/run
       Input:  { "query": "...", "image_url": "..."? }
       Output: { "answer", "tools_used", "reasoning_steps" }
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

from app.agent import run_agent
from app.config import (
    AGENT_LLM_PROVIDER,
    IMAGE_ANALYSER_URL,
    OPENAI_MODEL,
    RAG_SERVICE_URL,
)
from app.llm import llm_available
from app.prompts import TOOL_DESCRIPTIONS_VERSION

app = FastAPI(
    title="AthleteCare LangGraph Agent",
    description="Service 4: multi-step clinical agent (RAG + Image Analyser tools)",
    version="1.0.0",
)


class AgentRunRequest(BaseModel):
    """Assignment input is `query`; `image_url` is an AthleteCare extension for imaging tools."""

    query: str = Field(..., min_length=3, description="Complex multi-step clinical question")
    image_url: HttpUrl | None = Field(
        default=None,
        description="Optional X-ray / clinical image URL for image_analyser",
    )


class AgentRunResponse(BaseModel):
    answer: str
    tools_used: list[str]
    reasoning_steps: list[str]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "langgraph-agent",
        "tool_descriptions_version": TOOL_DESCRIPTIONS_VERSION,
        "llm_provider": AGENT_LLM_PROVIDER,
        "llm_ready": llm_available() or AGENT_LLM_PROVIDER == "heuristic",
        "openai_model": OPENAI_MODEL if llm_available() else None,
        "rag_service_url": RAG_SERVICE_URL,
        "image_analyser_url": IMAGE_ANALYSER_URL,
    }


@app.get("/")
def root():
    return {
        "service": "AthleteCare LangGraph Agent",
        "endpoint": "POST /agent/run",
        "nodes": ["planner", "tool_execution", "synthesiser"],
        "tools": ["rag_service", "image_analyser"],
    }


@app.post("/agent/run", response_model=AgentRunResponse)
def agent_run(body: AgentRunRequest):
    query = body.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="query cannot be empty",
        )

    image_url = str(body.image_url) if body.image_url else None

    try:
        result = run_agent(query=query, image_url=image_url)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent failed: {exc}",
        ) from exc

    return AgentRunResponse(
        answer=result["answer"],
        tools_used=result["tools_used"],
        reasoning_steps=result["reasoning_steps"],
    )
