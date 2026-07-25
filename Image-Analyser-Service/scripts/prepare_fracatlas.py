"""
Prepare FracAtlas labels for AthleteCare condition head (head #2).

Maps:
  fractured=0 -> condition_score=1  (normal / no clear fracture)
  fractured=1 -> condition_score=5  (abnormal / fracture present)

Usage (from Image-Analyser-Service):
  python scripts/prepare_fracatlas.py --zip "path/to/fracatlas.zip"
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

SERVICE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ZIP = Path.home() / "Desktop" / "fracatlas.zip"


def prepare(zip_path: Path, out_dir: Path, max_normal: int | None, seed: int) -> None:
    if not zip_path.is_file():
        raise FileNotFoundError(f"Zip not found: {zip_path}")

    random.seed(seed)
    images_out = out_dir / "images"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    images_out.mkdir(parents=True, exist_ok=True)

    normal_rows: list[dict] = []
    fractured_rows: list[dict] = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("train.csv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
            for row in reader:
                filename = row["filename"].strip()
                fractured = int(row["fractured"])
                score = 5 if fractured == 1 else 1
                item = {
                    "filename": filename,
                    "condition_score": score,
                    "fractured": fractured,
                    "body_region_src": row.get("body_region", ""),
                }
                if fractured == 1:
                    fractured_rows.append(item)
                else:
                    normal_rows.append(item)

        if max_normal is not None and len(normal_rows) > max_normal:
            normal_rows = random.sample(normal_rows, max_normal)

        selected = fractured_rows + normal_rows
        print(
            f"Selected {len(selected)} images "
            f"({len(fractured_rows)} fractured ->5, {len(normal_rows)} normal ->1)"
        )

        members = set(zf.namelist())
        labels_path = out_dir / "labels.csv"
        written = 0
        missing = 0
        counts: Counter[int] = Counter()

        with labels_path.open("w", newline="", encoding="utf-8") as lf:
            writer = csv.DictWriter(
                lf,
                fieldnames=["filepath", "condition_score", "fractured", "body_region_src"],
            )
            writer.writeheader()

            for item in selected:
                member = f"images/{item['filename']}"
                if member not in members:
                    missing += 1
                    continue
                dest = images_out / item["filename"]
                with zf.open(member) as src, dest.open("wb") as dst:
                    shutil.copyfileobj(src, dst)

                rel = Path("images") / item["filename"]
                writer.writerow(
                    {
                        "filepath": rel.as_posix(),
                        "condition_score": item["condition_score"],
                        "fractured": item["fractured"],
                        "body_region_src": item["body_region_src"],
                    }
                )
                written += 1
                counts[item["condition_score"]] += 1
                if written % 200 == 0:
                    print(f"  extracted {written}...")

    print("=== Condition score counts ===")
    for score in (1, 2, 3, 4, 5):
        print(f"  {score}: {counts.get(score, 0)}")
    print(f"Wrote {written} images -> {images_out}")
    print(f"Labels -> {labels_path}")
    if missing:
        print(f"Missing images: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare FracAtlas for condition-head training")
    parser.add_argument("--zip", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--out", type=Path, default=SERVICE_ROOT / "data" / "fracatlas")
    parser.add_argument(
        "--max-normal",
        type=int,
        default=700,
        help="Cap normal (score=1) samples for class balance (None = keep all)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--all-normal",
        action="store_true",
        help="Keep all normal images (ignore --max-normal)",
    )
    args = parser.parse_args()
    max_normal = None if args.all_normal else args.max_normal
    prepare(args.zip, args.out, max_normal, args.seed)


if __name__ == "__main__":
    main()
