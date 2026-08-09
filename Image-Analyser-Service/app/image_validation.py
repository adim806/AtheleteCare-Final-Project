"""Heuristic checks that downloaded images look like clinical radiographs."""

from __future__ import annotations

import os

import numpy as np
from PIL import Image

MIN_IMAGE_WIDTH = int(os.getenv("MIN_IMAGE_WIDTH", "64"))
MIN_IMAGE_HEIGHT = int(os.getenv("MIN_IMAGE_HEIGHT", "64"))
# Mean |R-G|, |G-B|, |R-B| above this → likely a colour photo, not an X-ray.
MAX_CHANNEL_DIFF = float(os.getenv("MAX_CHANNEL_DIFF", "28.0"))


def validate_clinical_image(image: Image.Image) -> None:
    """
    Raise ValueError if the image fails basic radiograph heuristics.

    X-rays are nearly grayscale; colour photos and icons are rejected early.
    """
    width, height = image.size
    if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
        raise ValueError(
            f"Image too small ({width}x{height}); minimum {MIN_IMAGE_WIDTH}x{MIN_IMAGE_HEIGHT}."
        )

    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    if rgb.size == 0:
        raise ValueError("Empty image.")

    # Subsample large images for speed.
    step = max(1, int(np.sqrt(rgb.shape[0] * rgb.shape[1] / 250_000)))
    sample = rgb[::step, ::step, :]
    channel_diff = float(
        max(
            np.mean(np.abs(sample[:, :, 0] - sample[:, :, 1])),
            np.mean(np.abs(sample[:, :, 1] - sample[:, :, 2])),
            np.mean(np.abs(sample[:, :, 0] - sample[:, :, 2])),
        )
    )
    if channel_diff > MAX_CHANNEL_DIFF:
        raise ValueError(
            "Image appears to be a colour photograph, not a clinical X-ray radiograph."
        )
