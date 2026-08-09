"""
Map Image Analyser body_region labels to RAG corpus metadata values.

Image model classes: ankle, knee, foot, lower_leg, thigh, hip, other
RAG frontmatter: hamstring, calf, knee, hip, ankle, general, ...
"""

from __future__ import annotations

# Image Analyser class → RAG metadata body_region values (may be multiple).
IMAGE_TO_RAG_BODY_REGIONS: dict[str, list[str]] = {
    "ankle": ["ankle"],
    "knee": ["knee"],
    "foot": ["ankle"],  # closest corpus match
    "lower_leg": ["calf", "hamstring"],
    "thigh": ["hamstring"],
    "hip": ["hip"],
    "other": [],
}


def rag_body_regions_for_image(body_region: str | None) -> list[str]:
    """Return RAG filter regions for an imaging body_region, or [] if unknown/other."""
    if not body_region:
        return []
    return list(IMAGE_TO_RAG_BODY_REGIONS.get(body_region.strip().lower(), []))
