"""Configuration for the AthleteCare Image Analyser (Service 2, medical domain)."""

from __future__ import annotations

import os
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent.parent

# Soccer-relevant body regions + other (UNIFESP remap). Order is class index order.
BODY_REGION_CLASSES: list[str] = [
    "ankle",
    "knee",
    "foot",
    "lower_leg",
    "thigh",
    "hip",
    "other",
]

# Binary condition head: 0=normal, 1=fracture-like (FracAtlas proxy).
# API maps class index → condition_score 1 (normal) or 5 (fracture-like).
NUM_CONDITION_CLASSES = 2
CONDITION_CLASS_TO_SCORE: dict[int, int] = {0: 1, 1: 5}


def condition_class_from_row(row: dict) -> int:
    """Map FracAtlas/joint CSV row to binary class 0=normal, 1=fracture-like."""
    fractured = row.get("fractured")
    if fractured not in (None, ""):
        return int(fractured)
    score = int(row["condition_score"])
    return 0 if score <= 1 else 1


DEFAULT_TRAIN_CONDITION_SCORE = 3  # used only by UNIFESP prepare (region labels)

# Below this softmax confidence, return body_region="other" (uncertain).
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.45"))

# Below this, condition_score is suppressed (null) — imaging abnormality inconclusive.
CONDITION_CONFIDENCE_THRESHOLD = float(os.getenv("CONDITION_CONFIDENCE_THRESHOLD", "0.65"))

REQUEST_TIMEOUT_SEC = float(os.getenv("REQUEST_TIMEOUT_SEC", "30"))

# Checkpoint path (relative to service root unless absolute).
_DEFAULT_CKPT = SERVICE_ROOT / "checkpoints" / "model.pth"
MODEL_CHECKPOINT = Path(os.getenv("MODEL_CHECKPOINT", str(_DEFAULT_CKPT)))
