"""
FastAPI Image Analyser — AthleteCare (assignment Service 2, medical domain).

Endpoints:
  GET  /health
  POST /analyse  { "image_url": "..." }
       → { "body_region", "condition_score", "confidence", "condition_confidence", "imaging_reliable" }
"""

from __future__ import annotations

import io
import logging
from contextlib import asynccontextmanager

import httpx
import torch
from fastapi import FastAPI, HTTPException, status
from PIL import Image
from pydantic import BaseModel, Field, HttpUrl

from app.config import (
    BODY_REGION_CLASSES,
    CONDITION_CLASS_TO_SCORE,
    CONDITION_CONFIDENCE_THRESHOLD,
    CONFIDENCE_THRESHOLD,
    MODEL_CHECKPOINT,
    REQUEST_TIMEOUT_SEC,
)
from app.image_validation import validate_clinical_image
from app.model import build_model, get_preprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("image_analyser")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = None
preprocess = None
checkpoint_loaded = False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global model, preprocess, checkpoint_loaded
    logger.info("Loading ResNet-50 dual-head model on %s ...", device)
    model, checkpoint_loaded = build_model(device, MODEL_CHECKPOINT)
    preprocess = get_preprocess()
    logger.info(
        "Model ready. checkpoint_loaded=%s confidence_threshold=%.2f body_regions=%s",
        checkpoint_loaded,
        CONFIDENCE_THRESHOLD,
        BODY_REGION_CLASSES,
    )
    yield


app = FastAPI(
    title="AthleteCare Image Analyser",
    description="Service 2 — body region + binary imaging abnormality proxy for clinical X-rays",
    lifespan=lifespan,
)


class AnalyseRequest(BaseModel):
    image_url: HttpUrl = Field(..., description="Public URL of the clinical / injury image")


class AnalyseResponse(BaseModel):
    body_region: str = Field(..., description="Predicted anatomical region")
    condition_score: int | None = Field(
        None,
        ge=1,
        le=5,
        description="Imaging abnormality proxy: 1=normal, 5=fracture-like; null if inconclusive",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Softmax confidence for body_region")
    condition_confidence: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Softmax confidence for condition (binary head); null if suppressed",
    )
    imaging_reliable: bool = Field(
        ...,
        description=(
            "True when region is localized (not other), both confidence thresholds pass, "
            "and condition_score is present"
        ),
    )


@app.get("/health")
def health():
    return {
        "status": "ok" if model is not None else "starting",
        "device": str(device),
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "condition_confidence_threshold": CONDITION_CONFIDENCE_THRESHOLD,
        "body_region_classes": BODY_REGION_CLASSES,
        "condition_head": "binary",
        "condition_scores": [1, 5],
        "checkpoint_loaded": checkpoint_loaded,
        "checkpoint_path": str(MODEL_CHECKPOINT),
    }


def _download_image(url: str) -> Image.Image:
    try:
        headers = {
            # Some CDNs (e.g. Wikimedia) reject requests with no / default bot UA.
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }
        with httpx.Client(
            timeout=REQUEST_TIMEOUT_SEC,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if content_type and not content_type.startswith("image/") and "octet-stream" not in content_type:
                logger.warning("Unexpected content-type=%s for %s", content_type, url)
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
            try:
                validate_clinical_image(image)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc
            return image
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to download image_url: {exc}",
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Downloaded bytes are not a valid image: {exc}",
        ) from exc


@torch.inference_mode()
def _predict(image: Image.Image) -> AnalyseResponse:
    assert model is not None and preprocess is not None
    batch = preprocess(image).unsqueeze(0).to(device)
    region_logits, condition_logits = model(batch)

    region_probs = torch.softmax(region_logits, dim=1)[0]
    region_confidence, region_idx = torch.max(region_probs, dim=0)
    region_confidence_value = float(region_confidence.item())
    body_region = BODY_REGION_CLASSES[int(region_idx.item())]
    region_uncertain = region_confidence_value < CONFIDENCE_THRESHOLD

    if region_uncertain:
        body_region = "other"

    condition_probs = torch.softmax(condition_logits, dim=1)[0]
    condition_confidence_tensor, condition_idx = torch.max(condition_probs, dim=0)
    condition_confidence_value = float(condition_confidence_tensor.item())
    condition_score = CONDITION_CLASS_TO_SCORE[int(condition_idx.item())]

    region_localized = body_region != "other"
    region_ok = not region_uncertain and region_localized
    condition_ok = condition_confidence_value >= CONDITION_CONFIDENCE_THRESHOLD
    imaging_reliable = region_ok and condition_ok

    if not imaging_reliable:
        condition_score = None
        condition_confidence_out = None
    else:
        condition_confidence_out = round(condition_confidence_value, 4)

    return AnalyseResponse(
        body_region=body_region,
        condition_score=condition_score,
        confidence=round(region_confidence_value, 4),
        condition_confidence=condition_confidence_out,
        imaging_reliable=imaging_reliable,
    )


@app.post("/analyse", response_model=AnalyseResponse)
def analyse(body: AnalyseRequest):
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is still loading.",
        )

    image = _download_image(str(body.image_url))
    result = _predict(image)
    logger.info(
        "analyse → body_region=%s condition_score=%s confidence=%.4f "
        "condition_confidence=%s imaging_reliable=%s",
        result.body_region,
        result.condition_score,
        result.confidence,
        result.condition_confidence,
        result.imaging_reliable,
    )
    return result
