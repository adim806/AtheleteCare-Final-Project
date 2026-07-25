"""
Build a joint training table: same rows carry body_region + condition_score.

Sources:
  - UNIFESP (data/labels.csv): region known; condition unknown (ignored in loss)
  - FracAtlas (data/fracatlas/labels.csv): condition 1/5 + region remapped into
    AthleteCare classes

FracAtlas body_region_src remap:
  hip      -> hip
  leg      -> lower_leg
  hand     -> other
  shoulder -> other

Usage:
  python scripts/prepare_joint_dataset.py
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent.parent

FRACATLAS_REGION_MAP = {
    "hip": "hip",
    "leg": "lower_leg",
    "hand": "other",
    "shoulder": "other",
}


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def prepare(data_root: Path, out_csv: Path) -> None:
    unifesp_csv = data_root / "labels.csv"
    frac_csv = data_root / "fracatlas" / "labels.csv"
    if not unifesp_csv.is_file():
        raise FileNotFoundError(f"Missing {unifesp_csv}. Run prepare_dataset.py first.")
    if not frac_csv.is_file():
        raise FileNotFoundError(f"Missing {frac_csv}. Run prepare_fracatlas.py first.")

    rows: list[dict] = []

    for r in _read_csv(unifesp_csv):
        rows.append(
            {
                "filepath": r["filepath"],
                "body_region": r["body_region"],
                "condition_score": "",  # unknown — ignored in joint loss
                "condition_known": "0",
                "source": "unifesp",
            }
        )

    for r in _read_csv(frac_csv):
        src = (r.get("body_region_src") or "").strip().lower()
        region = FRACATLAS_REGION_MAP.get(src, "other")
        rows.append(
            {
                "filepath": f"fracatlas/{r['filepath']}",
                "body_region": region,
                "condition_score": r["condition_score"],
                "condition_known": "1",
                "source": "fracatlas",
            }
        )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "filepath",
                "body_region",
                "condition_score",
                "condition_known",
                "source",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    region_counts = Counter(r["body_region"] for r in rows)
    source_counts = Counter(r["source"] for r in rows)
    cond_counts = Counter(
        r["condition_score"] for r in rows if r["condition_known"] == "1"
    )

    print(f"Wrote {len(rows)} joint rows -> {out_csv}")
    print("=== By source ===")
    for k, v in sorted(source_counts.items()):
        print(f"  {k}: {v}")
    print("=== By body_region ===")
    for k, v in sorted(region_counts.items()):
        print(f"  {k}: {v}")
    print("=== Condition (FracAtlas only) ===")
    for k, v in sorted(cond_counts.items()):
        print(f"  score {k}: {v}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare joint UNIFESP+FracAtlas labels")
    parser.add_argument("--data", type=Path, default=SERVICE_ROOT / "data")
    parser.add_argument(
        "--out",
        type=Path,
        default=SERVICE_ROOT / "data" / "joint" / "labels.csv",
    )
    args = parser.parse_args()
    prepare(args.data, args.out)


if __name__ == "__main__":
    main()
