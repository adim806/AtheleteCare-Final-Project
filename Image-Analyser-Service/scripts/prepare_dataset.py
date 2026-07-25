"""
Prepare UNIFESP X-ray data for AthleteCare Image Analyser training.

Reads archive.zip (or an extracted folder), maps body-part codes to soccer
regions + other, converts DICOM → PNG, writes data/labels.csv.

Usage (from Image-Analyser-Service, with venv active):
  python scripts/prepare_dataset.py --zip "path/to/archive.zip"
"""

from __future__ import annotations

import argparse
import csv
import io
import random
import shutil
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pydicom
from PIL import Image

# Allow running as `python scripts/prepare_dataset.py`
import sys

SERVICE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_ROOT))

from app.config import (  # noqa: E402
    BODY_REGION_CLASSES,
    DEFAULT_TRAIN_CONDITION_SCORE,
)

# UNIFESP Target integer → AthleteCare class
SOCCER_CODE_MAP: dict[str, str] = {
    "1": "ankle",
    "11": "knee",
    "6": "foot",
    "12": "lower_leg",
    "19": "thigh",
    "10": "hip",
}

OTHER_SAMPLE_SIZE = 70
DEFAULT_ZIP = Path.home() / "Desktop" / "archive.zip"


def _map_target(target: str) -> str | None:
    """
    Return class name, or None to skip (ambiguous multi soccer labels).
    """
    toks = target.strip().split()
    soccer = [SOCCER_CODE_MAP[t] for t in toks if t in SOCCER_CODE_MAP]
    unique_soccer = list(dict.fromkeys(soccer))
    if len(unique_soccer) == 1:
        return unique_soccer[0]
    if len(unique_soccer) == 0:
        return "other"
    return None  # two+ soccer regions


def _dicom_bytes_to_png(data: bytes) -> Image.Image:
    ds = pydicom.dcmread(io.BytesIO(data))
    arr = ds.pixel_array.astype(np.float32)
    # Window to 8-bit RGB
    arr -= arr.min()
    peak = arr.max()
    if peak > 0:
        arr = arr / peak
    arr = (arr * 255.0).clip(0, 255).astype(np.uint8)
    if arr.ndim == 2:
        return Image.fromarray(arr, mode="L").convert("RGB")
    if arr.ndim == 3 and arr.shape[-1] in (3, 4):
        return Image.fromarray(arr[..., :3], mode="RGB")
    # Fallback: take first channel/slice
    if arr.ndim == 3:
        return Image.fromarray(arr[0], mode="L").convert("RGB")
    raise ValueError(f"Unsupported DICOM array shape: {arr.shape}")


def _find_dcm_in_zip(zf: zipfile.ZipFile, sop_uid: str) -> str | None:
    """Return zip member path ending with this SOPInstanceUID .dcm if present."""
    suffix = f"{sop_uid}-c.dcm"
    # Also try without -c
    candidates = []
    for name in zf.namelist():
        if not name.lower().endswith(".dcm"):
            continue
        base = Path(name).name
        if sop_uid in base:
            candidates.append(name)
            if base.endswith(suffix) or base == f"{sop_uid}.dcm":
                return name
    return candidates[0] if candidates else None


def prepare(zip_path: Path, out_dir: Path, other_sample: int, seed: int) -> None:
    random.seed(seed)
    processed = out_dir / "processed"
    if processed.exists():
        shutil.rmtree(processed)
    processed.mkdir(parents=True, exist_ok=True)
    for cls in BODY_REGION_CLASSES:
        (processed / cls).mkdir(parents=True, exist_ok=True)

    if not zip_path.is_file():
        raise FileNotFoundError(f"Zip not found: {zip_path}")

    soccer_rows: list[tuple[str, str]] = []  # (sop, class)
    other_rows: list[tuple[str, str]] = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("train.csv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
            for row in reader:
                sop = row["SOPInstanceUID"].strip()
                label = _map_target(row["Target"])
                if label is None:
                    continue
                if label == "other":
                    other_rows.append((sop, label))
                else:
                    soccer_rows.append((sop, label))

        if len(other_rows) > other_sample:
            other_rows = random.sample(other_rows, other_sample)

        selected = soccer_rows + other_rows
        print(f"Selected {len(selected)} images ({len(soccer_rows)} soccer + {len(other_rows)} other)")

        # Index dcm paths once for speed
        print("Indexing DICOM members in zip...")
        sop_to_member: dict[str, str] = {}
        for name in zf.namelist():
            if not name.lower().endswith(".dcm"):
                continue
            if "train/" not in name.replace("\\", "/"):
                continue
            base = Path(name).name
            # filenames look like: <uid>-c.dcm
            uid = base.replace("-c.dcm", "").replace(".dcm", "")
            sop_to_member[uid] = name

        labels_path = out_dir / "labels.csv"
        written = 0
        missing = 0
        counts: Counter[str] = Counter()

        with labels_path.open("w", newline="", encoding="utf-8") as lf:
            writer = csv.DictWriter(
                lf, fieldnames=["filepath", "body_region", "condition_score"]
            )
            writer.writeheader()

            for sop, label in selected:
                member = sop_to_member.get(sop)
                if member is None:
                    missing += 1
                    continue
                try:
                    raw = zf.read(member)
                    img = _dicom_bytes_to_png(raw)
                except Exception as exc:  # noqa: BLE001
                    print(f"  skip {sop}: {exc}")
                    missing += 1
                    continue

                rel = Path("processed") / label / f"{sop}.png"
                dest = out_dir / rel
                img.save(dest, format="PNG")
                writer.writerow(
                    {
                        "filepath": rel.as_posix(),
                        "body_region": label,
                        "condition_score": DEFAULT_TRAIN_CONDITION_SCORE,
                    }
                )
                written += 1
                counts[label] += 1
                if written % 50 == 0:
                    print(f"  converted {written}...")

    print("=== Per-class counts ===")
    for cls in BODY_REGION_CLASSES:
        print(f"  {cls}: {counts.get(cls, 0)}")
    print(f"Wrote {written} PNGs -> {out_dir / 'processed'}")
    print(f"Labels -> {labels_path}")
    if missing:
        print(f"Missing/failed: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare UNIFESP dataset for training")
    parser.add_argument(
        "--zip",
        type=Path,
        default=DEFAULT_ZIP,
        help="Path to UNIFESP archive.zip",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=SERVICE_ROOT / "data",
        help="Output data directory",
    )
    parser.add_argument("--other-sample", type=int, default=OTHER_SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    prepare(args.zip, args.out, args.other_sample, args.seed)


if __name__ == "__main__":
    main()
