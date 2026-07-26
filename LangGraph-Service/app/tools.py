"""HTTP tool clients for RAG-Service and Image-Analyser-Service."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import HTTP_TIMEOUT_SEC, IMAGE_ANALYSER_URL, RAG_SERVICE_URL

# Public names used in plan JSON / tools_used
TOOL_RAG = "rag_service"
TOOL_IMAGE = "image_analyser"


def call_rag_service(description: str) -> dict[str, Any]:
    """POST /query on RAG service."""
    url = f"{RAG_SERVICE_URL}/query"
    payload = {"description": description}
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SEC) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return {"ok": True, "tool": TOOL_RAG, "result": data}
    except Exception as exc:  # noqa: BLE001 — surface tool failure to synthesiser
        return {"ok": False, "tool": TOOL_RAG, "error": str(exc)}


def call_image_analyser(image_url: str) -> dict[str, Any]:
    """POST /analyse on Image Analyser service."""
    url = f"{IMAGE_ANALYSER_URL}/analyse"
    payload = {"image_url": image_url}
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SEC) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return {"ok": True, "tool": TOOL_IMAGE, "result": data}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "tool": TOOL_IMAGE, "error": str(exc)}
