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

# Condition score 1–5 (assignment second head).
# Region head trains on UNIFESP; condition head on FracAtlas proxy:
#   fractured=0 -> 1 (normal), fractured=1 -> 5 (abnormal).
NUM_CONDITION_SCORES = 5
DEFAULT_TRAIN_CONDITION_SCORE = 3  # used only by UNIFESP prepare (region labels)

# Below this softmax confidence, return body_region="other" (uncertain).
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.45"))

REQUEST_TIMEOUT_SEC = float(os.getenv("REQUEST_TIMEOUT_SEC", "30"))

# Checkpoint path (relative to service root unless absolute).
_DEFAULT_CKPT = SERVICE_ROOT / "checkpoints" / "model.pth"
MODEL_CHECKPOINT = Path(os.getenv("MODEL_CHECKPOINT", str(_DEFAULT_CKPT)))
