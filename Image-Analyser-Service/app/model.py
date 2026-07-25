"""
ResNet-50 dual-head model — AthleteCare Image Analyser (Service 2).

Architecture matches the assignment (frozen backbone + class head + 1–5 score
head). Labels: soccer body regions + other; severity head kept for assignment.
"""

from __future__ import annotations

import logging
from pathlib import Path

import torch
import torch.nn as nn
from torchvision.models import ResNet50_Weights, resnet50

from app.config import BODY_REGION_CLASSES, MODEL_CHECKPOINT, NUM_CONDITION_SCORES

logger = logging.getLogger("image_analyser")


class ImageAnalyserModel(nn.Module):
    """Frozen ResNet-50 backbone + body-region classifier + severity head."""

    def __init__(self) -> None:
        super().__init__()
        weights = ResNet50_Weights.IMAGENET1K_V2
        backbone = resnet50(weights=weights)
        feature_dim = backbone.fc.in_features
        backbone.fc = nn.Identity()
        self.backbone = backbone

        for param in self.backbone.parameters():
            param.requires_grad = False

        self.region_head = nn.Linear(feature_dim, len(BODY_REGION_CLASSES))
        self.condition_head = nn.Linear(feature_dim, NUM_CONDITION_SCORES)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.backbone(x)
        region_logits = self.region_head(features)
        condition_logits = self.condition_head(features)
        return region_logits, condition_logits


def build_model(
    device: torch.device,
    checkpoint_path: Path | None = None,
) -> tuple[ImageAnalyserModel, bool]:
    """
    Build model and optionally load a trained checkpoint.

    Returns (model, checkpoint_loaded).
    """
    model = ImageAnalyserModel()
    path = checkpoint_path if checkpoint_path is not None else MODEL_CHECKPOINT
    loaded = False

    if path.is_file():
        try:
            ckpt = torch.load(path, map_location="cpu", weights_only=False)
            state = ckpt["model_state_dict"] if isinstance(ckpt, dict) and "model_state_dict" in ckpt else ckpt
            if isinstance(ckpt, dict) and "body_region_classes" in ckpt:
                saved = list(ckpt["body_region_classes"])
                if saved != BODY_REGION_CLASSES:
                    logger.warning(
                        "Checkpoint classes %s differ from config %s — loading weights anyway",
                        saved,
                        BODY_REGION_CLASSES,
                    )
            model.load_state_dict(state, strict=True)
            loaded = True
            metrics = []
            if isinstance(ckpt, dict):
                if "test_region_accuracy" in ckpt:
                    metrics.append(f"test_acc={ckpt['test_region_accuracy']:.3f}")
                if "val_region_accuracy" in ckpt:
                    metrics.append(f"val_acc={ckpt['val_region_accuracy']:.3f}")
            logger.info("Loaded checkpoint %s %s", path, " ".join(metrics))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load checkpoint %s: %s — using untrained heads", path, exc)
    else:
        logger.warning("No checkpoint at %s — using untrained heads (run scripts/train.py)", path)

    model.eval()
    model.to(device)
    return model, loaded


def get_preprocess():
    """Official ImageNet preprocess pipeline bundled with ResNet50 weights."""
    return ResNet50_Weights.IMAGENET1K_V2.transforms()
