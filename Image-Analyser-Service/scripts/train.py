"""
Train AthleteCare Image Analyser dual-head ResNet-50 (assignment Service 2).

Recommended (joint):
  python scripts/prepare_joint_dataset.py
  python scripts/train.py --phase joint

Legacy two-phase:
  python scripts/train.py --phase both
  python scripts/train.py --phase region
  python scripts/train.py --phase condition
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from tqdm import tqdm

SERVICE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_ROOT))

from app.config import (  # noqa: E402
    BODY_REGION_CLASSES,
    NUM_CONDITION_CLASSES,
    condition_class_from_row,
)
from app.model import ImageAnalyserModel, get_preprocess  # noqa: E402


class RegionDataset(Dataset):
    def __init__(
        self,
        rows: list[dict],
        data_root: Path,
        class_to_idx: dict[str, int],
        transform,
    ) -> None:
        self.rows = rows
        self.data_root = data_root
        self.class_to_idx = class_to_idx
        self.transform = transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        image = Image.open(self.data_root / row["filepath"]).convert("RGB")
        x = self.transform(image)
        region = self.class_to_idx[row["body_region"]]
        return x, region


class ConditionDataset(Dataset):
    def __init__(self, rows: list[dict], data_root: Path, transform) -> None:
        self.rows = rows
        self.data_root = data_root
        self.transform = transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        image = Image.open(self.data_root / row["filepath"]).convert("RGB")
        x = self.transform(image)
        condition = condition_class_from_row(row)
        return x, condition


class JointDataset(Dataset):
    """Rows with region always; condition may be unknown (ignore_index=-100)."""

    IGNORE_CONDITION = -100

    def __init__(
        self,
        rows: list[dict],
        data_root: Path,
        class_to_idx: dict[str, int],
        transform,
    ) -> None:
        self.rows = rows
        self.data_root = data_root
        self.class_to_idx = class_to_idx
        self.transform = transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        image = Image.open(self.data_root / row["filepath"]).convert("RGB")
        x = self.transform(image)
        region = self.class_to_idx[row["body_region"]]
        if row.get("condition_known") == "1" and row.get("condition_score"):
            condition = condition_class_from_row(row)
        else:
            condition = self.IGNORE_CONDITION
        return x, region, condition


def load_rows(labels_csv: Path) -> list[dict]:
    with labels_csv.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _make_transforms():
    eval_tf = get_preprocess()
    train_tf = transforms.Compose(
        [
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(10),
            transforms.ColorJitter(brightness=0.15, contrast=0.15),
            eval_tf,
        ]
    )
    return train_tf, eval_tf


def _stratified_split(rows: list[dict], key: str, seed: int):
    y = [r[key] for r in rows]
    train_rows, temp_rows = train_test_split(
        rows, test_size=0.30, random_state=seed, stratify=y
    )
    y_temp = [r[key] for r in temp_rows]
    val_rows, test_rows = train_test_split(
        temp_rows, test_size=0.50, random_state=seed, stratify=y_temp
    )
    return train_rows, val_rows, test_rows


def _region_class_weights(
    rows: list[dict],
    class_to_idx: dict[str, int],
    device: torch.device,
) -> torch.Tensor:
    """Inverse-frequency weights for region CrossEntropy (mean weight = 1)."""
    counts = torch.zeros(len(class_to_idx), dtype=torch.float32)
    for row in rows:
        counts[class_to_idx[row["body_region"]]] += 1.0
    weights = counts.sum() / (len(counts) * counts.clamp(min=1.0))
    return weights.to(device)


def _condition_class_weights(rows: list[dict], device: torch.device) -> torch.Tensor:
    """Inverse-frequency weights for binary condition head (FracAtlas-labelled rows)."""
    counts = torch.zeros(NUM_CONDITION_CLASSES, dtype=torch.float32)
    for row in rows:
        if row.get("condition_known") == "1" and row.get("condition_score"):
            counts[condition_class_from_row(row)] += 1.0
    if counts.sum() == 0:
        return torch.ones(NUM_CONDITION_CLASSES, device=device)
    weights = counts.sum() / (len(counts) * counts.clamp(min=1.0))
    return weights.to(device)


def _log_class_distribution(rows: list[dict], label: str) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        region = row["body_region"]
        counts[region] = counts.get(region, 0) + 1
    parts = ", ".join(f"{k}={v}" for k, v in sorted(counts.items(), key=lambda x: -x[1]))
    print(f"[joint] {label} region counts: {parts}")


@torch.inference_mode()
def region_accuracy(model: nn.Module, loader: DataLoader, device: torch.device) -> float:
    model.eval()
    correct = total = 0
    for x, region in loader:
        x = x.to(device)
        region = region.to(device)
        logits, _ = model(x)
        correct += (logits.argmax(dim=1) == region).sum().item()
        total += region.size(0)
    return correct / total if total else 0.0


@torch.inference_mode()
def condition_accuracy(model: nn.Module, loader: DataLoader, device: torch.device) -> float:
    model.eval()
    correct = total = 0
    for x, condition in loader:
        x = x.to(device)
        condition = condition.to(device)
        _, logits = model(x)
        correct += (logits.argmax(dim=1) == condition).sum().item()
        total += condition.size(0)
    return correct / total if total else 0.0


@torch.inference_mode()
def joint_metrics(
    model: nn.Module, loader: DataLoader, device: torch.device
) -> tuple[float, float, float]:
    """Return (region_acc, condition_acc_on_known, both_correct_on_known)."""
    model.eval()
    region_correct = region_total = 0
    cond_correct = cond_total = 0
    both_correct = both_total = 0
    for x, region, condition in loader:
        x = x.to(device)
        region = region.to(device)
        condition = condition.to(device)
        region_logits, condition_logits = model(x)
        region_pred = region_logits.argmax(dim=1)
        cond_pred = condition_logits.argmax(dim=1)

        region_correct += (region_pred == region).sum().item()
        region_total += region.size(0)

        known = condition != JointDataset.IGNORE_CONDITION
        if known.any():
            cond_correct += (cond_pred[known] == condition[known]).sum().item()
            cond_total += int(known.sum().item())
            both = (region_pred[known] == region[known]) & (cond_pred[known] == condition[known])
            both_correct += int(both.sum().item())
            both_total += int(known.sum().item())

    region_acc = region_correct / region_total if region_total else 0.0
    cond_acc = cond_correct / cond_total if cond_total else 0.0
    both_acc = both_correct / both_total if both_total else 0.0
    return region_acc, cond_acc, both_acc


def _load_or_init_model(device: torch.device, init_checkpoint: Path | None) -> ImageAnalyserModel:
    model = ImageAnalyserModel()
    if init_checkpoint is not None and init_checkpoint.is_file():
        ckpt = torch.load(init_checkpoint, map_location="cpu", weights_only=False)
        state = ckpt["model_state_dict"] if isinstance(ckpt, dict) and "model_state_dict" in ckpt else ckpt
        model.load_state_dict(state, strict=True)
        print(f"Loaded init checkpoint: {init_checkpoint}")
    model.to(device)
    for p in model.backbone.parameters():
        p.requires_grad = False
    return model


def train_region(
    data_dir: Path,
    epochs: int,
    batch_size: int,
    lr: float,
    seed: int,
    patience: int,
    init_checkpoint: Path | None,
    ckpt_path: Path,
) -> dict:
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[region] Device: {device}")

    labels_csv = data_dir / "labels.csv"
    if not labels_csv.is_file():
        raise FileNotFoundError(f"Missing {labels_csv}. Run scripts/prepare_dataset.py first.")

    rows = load_rows(labels_csv)
    class_to_idx = {c: i for i, c in enumerate(BODY_REGION_CLASSES)}
    train_rows, val_rows, test_rows = _stratified_split(rows, "body_region", seed)
    print(f"[region] Split train={len(train_rows)} val={len(val_rows)} test={len(test_rows)}")

    train_tf, eval_tf = _make_transforms()
    train_loader = DataLoader(
        RegionDataset(train_rows, data_dir, class_to_idx, train_tf),
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
    )
    val_loader = DataLoader(
        RegionDataset(val_rows, data_dir, class_to_idx, eval_tf),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )
    test_loader = DataLoader(
        RegionDataset(test_rows, data_dir, class_to_idx, eval_tf),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )

    model = _load_or_init_model(device, init_checkpoint)
    for p in model.region_head.parameters():
        p.requires_grad = True
    for p in model.condition_head.parameters():
        p.requires_grad = False

    optimizer = torch.optim.Adam(
        [p for p in model.parameters() if p.requires_grad], lr=lr
    )
    criterion = nn.CrossEntropyLoss()

    best_val = -1.0
    best_state = None
    wait = 0

    for epoch in range(1, epochs + 1):
        model.train()
        model.backbone.eval()
        running = 0.0
        n = 0
        for x, region in tqdm(train_loader, desc=f"region {epoch}/{epochs}"):
            x = x.to(device)
            region = region.to(device)
            optimizer.zero_grad(set_to_none=True)
            region_logits, _ = model(x)
            loss = criterion(region_logits, region)
            loss.backward()
            optimizer.step()
            running += loss.item() * x.size(0)
            n += x.size(0)

        val_acc = region_accuracy(model, val_loader, device)
        print(
            f"[region] Epoch {epoch}: train_loss={running / max(n, 1):.4f} "
            f"val_region_acc={val_acc:.3f}"
        )
        if val_acc > best_val:
            best_val = val_acc
            wait = 0
            best_state = {
                "model_state_dict": {
                    k: v.detach().cpu().clone() for k, v in model.state_dict().items()
                },
                "body_region_classes": BODY_REGION_CLASSES,
                "num_condition_classes": NUM_CONDITION_CLASSES,
                "val_region_accuracy": best_val,
                "condition_label_map": {"normal": 1, "fractured": 5},
                "condition_head": "binary",
            }
        else:
            wait += 1
            if wait >= patience:
                print("[region] Early stopping")
                break

    if best_state is None:
        raise RuntimeError("Region training produced no checkpoint")

    model.load_state_dict(best_state["model_state_dict"])
    test_acc = region_accuracy(model, test_loader, device)
    best_state["test_region_accuracy"] = test_acc
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, ckpt_path)
    print(f"[region] Saved -> {ckpt_path}")
    print(f"[region] Best val={best_val:.3f} test={test_acc:.3f}")
    return best_state


def train_condition(
    data_dir: Path,
    epochs: int,
    batch_size: int,
    lr: float,
    seed: int,
    patience: int,
    init_checkpoint: Path,
    ckpt_path: Path,
) -> dict:
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[condition] Device: {device}")

    labels_csv = data_dir / "labels.csv"
    if not labels_csv.is_file():
        raise FileNotFoundError(
            f"Missing {labels_csv}. Run scripts/prepare_fracatlas.py first."
        )
    if not init_checkpoint.is_file():
        raise FileNotFoundError(
            f"Missing region checkpoint {init_checkpoint}. Run --phase region first."
        )

    rows = load_rows(labels_csv)
    for row in rows:
        row["_condition_class"] = str(condition_class_from_row(row))
    train_rows, val_rows, test_rows = _stratified_split(rows, "_condition_class", seed)
    print(
        f"[condition] Split train={len(train_rows)} val={len(val_rows)} test={len(test_rows)}"
    )

    train_tf, eval_tf = _make_transforms()
    train_loader = DataLoader(
        ConditionDataset(train_rows, data_dir, train_tf),
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
    )
    val_loader = DataLoader(
        ConditionDataset(val_rows, data_dir, eval_tf),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )
    test_loader = DataLoader(
        ConditionDataset(test_rows, data_dir, eval_tf),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )

    model = _load_or_init_model(device, init_checkpoint)
    for p in model.region_head.parameters():
        p.requires_grad = False
    for p in model.condition_head.parameters():
        p.requires_grad = True

    optimizer = torch.optim.Adam(
        [p for p in model.parameters() if p.requires_grad], lr=lr
    )
    criterion = nn.CrossEntropyLoss()

    best_val = -1.0
    best_state = None
    wait = 0
    base_meta = torch.load(init_checkpoint, map_location="cpu", weights_only=False)
    if not isinstance(base_meta, dict):
        base_meta = {}

    for epoch in range(1, epochs + 1):
        model.train()
        model.backbone.eval()
        running = 0.0
        n = 0
        for x, condition in tqdm(train_loader, desc=f"condition {epoch}/{epochs}"):
            x = x.to(device)
            condition = condition.to(device)
            optimizer.zero_grad(set_to_none=True)
            _, condition_logits = model(x)
            loss = criterion(condition_logits, condition)
            loss.backward()
            optimizer.step()
            running += loss.item() * x.size(0)
            n += x.size(0)

        val_acc = condition_accuracy(model, val_loader, device)
        print(
            f"[condition] Epoch {epoch}: train_loss={running / max(n, 1):.4f} "
            f"val_condition_acc={val_acc:.3f}"
        )
        if val_acc > best_val:
            best_val = val_acc
            wait = 0
            best_state = {
                "model_state_dict": {
                    k: v.detach().cpu().clone() for k, v in model.state_dict().items()
                },
                "body_region_classes": BODY_REGION_CLASSES,
                "num_condition_classes": NUM_CONDITION_CLASSES,
                "val_region_accuracy": base_meta.get("val_region_accuracy"),
                "test_region_accuracy": base_meta.get("test_region_accuracy"),
                "val_condition_accuracy": best_val,
                "condition_label_map": {"normal": 1, "fractured": 5},
                "condition_head": "binary",
                "condition_source": "FracAtlas binary: class 0->1, class 1->5",
            }
        else:
            wait += 1
            if wait >= patience:
                print("[condition] Early stopping")
                break

    if best_state is None:
        raise RuntimeError("Condition training produced no checkpoint")

    model.load_state_dict(best_state["model_state_dict"])
    test_acc = condition_accuracy(model, test_loader, device)
    best_state["test_condition_accuracy"] = test_acc
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, ckpt_path)
    print(f"[condition] Saved -> {ckpt_path}")
    print(f"[condition] Best val={best_val:.3f} test={test_acc:.3f}")
    return best_state


def train_joint(
    data_root: Path,
    labels_csv: Path,
    epochs: int,
    batch_size: int,
    lr: float,
    seed: int,
    patience: int,
    init_checkpoint: Path | None,
    ckpt_path: Path,
    condition_loss_weight: float,
    use_region_class_weights: bool,
    use_condition_class_weights: bool,
) -> dict:
    """
    Train both heads on the combined table.
    Region loss on every sample; condition loss only when condition_known=1.
    """
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[joint] Device: {device}")

    if not labels_csv.is_file():
        raise FileNotFoundError(
            f"Missing {labels_csv}. Run scripts/prepare_joint_dataset.py first."
        )

    rows = load_rows(labels_csv)
    class_to_idx = {c: i for i, c in enumerate(BODY_REGION_CLASSES)}
    train_rows, val_rows, test_rows = _stratified_split(rows, "body_region", seed)
    print(
        f"[joint] Split train={len(train_rows)} val={len(val_rows)} test={len(test_rows)}"
    )
    _log_class_distribution(train_rows, "train")

    train_tf, eval_tf = _make_transforms()
    train_loader = DataLoader(
        JointDataset(train_rows, data_root, class_to_idx, train_tf),
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
    )
    val_loader = DataLoader(
        JointDataset(val_rows, data_root, class_to_idx, eval_tf),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )
    test_loader = DataLoader(
        JointDataset(test_rows, data_root, class_to_idx, eval_tf),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )

    model = _load_or_init_model(device, init_checkpoint)
    for p in model.region_head.parameters():
        p.requires_grad = True
    for p in model.condition_head.parameters():
        p.requires_grad = True

    optimizer = torch.optim.Adam(
        [p for p in model.parameters() if p.requires_grad], lr=lr
    )
    if use_region_class_weights:
        region_weights = _region_class_weights(train_rows, class_to_idx, device)
        region_criterion = nn.CrossEntropyLoss(weight=region_weights)
        print(f"[joint] Region class weights: {region_weights.tolist()}")
    else:
        region_weights = None
        region_criterion = nn.CrossEntropyLoss()
    if use_condition_class_weights:
        condition_weights = _condition_class_weights(train_rows, device)
        condition_criterion = nn.CrossEntropyLoss(
            weight=condition_weights,
            ignore_index=JointDataset.IGNORE_CONDITION,
        )
        print(f"[joint] Condition class weights: {condition_weights.tolist()}")
    else:
        condition_weights = None
        condition_criterion = nn.CrossEntropyLoss(ignore_index=JointDataset.IGNORE_CONDITION)

    print(f"[joint] condition_loss_weight={condition_loss_weight}")

    best_score = -1.0
    best_state = None
    wait = 0

    for epoch in range(1, epochs + 1):
        model.train()
        model.backbone.eval()
        running = 0.0
        n = 0
        for x, region, condition in tqdm(train_loader, desc=f"joint {epoch}/{epochs}"):
            x = x.to(device)
            region = region.to(device)
            condition = condition.to(device)
            optimizer.zero_grad(set_to_none=True)
            region_logits, condition_logits = model(x)
            loss_region = region_criterion(region_logits, region)
            known = (condition != JointDataset.IGNORE_CONDITION).any()
            if known:
                loss_condition = condition_criterion(condition_logits, condition)
                loss = loss_region + condition_loss_weight * loss_condition
            else:
                loss = loss_region
            loss.backward()
            optimizer.step()
            running += loss.item() * x.size(0)
            n += x.size(0)

        val_region, val_cond, val_both = joint_metrics(model, val_loader, device)
        # Optimize for joint correctness on samples that have both labels.
        score = 0.5 * val_region + 0.5 * val_both
        print(
            f"[joint] Epoch {epoch}: loss={running / max(n, 1):.4f} "
            f"val_region={val_region:.3f} val_cond={val_cond:.3f} "
            f"val_both_known={val_both:.3f}"
        )
        if score > best_score:
            best_score = score
            wait = 0
            best_state = {
                "model_state_dict": {
                    k: v.detach().cpu().clone() for k, v in model.state_dict().items()
                },
                "body_region_classes": BODY_REGION_CLASSES,
                "num_condition_classes": NUM_CONDITION_CLASSES,
                "val_region_accuracy": val_region,
                "val_condition_accuracy": val_cond,
                "val_both_known_accuracy": val_both,
                "condition_label_map": {"normal": 1, "fractured": 5},
                "condition_head": "binary",
                "condition_source": "FracAtlas binary: class 0->1, class 1->5 (joint)",
                "training": "joint UNIFESP+FracAtlas",
                "condition_loss_weight": condition_loss_weight,
                "region_class_weights": (
                    region_weights.detach().cpu().tolist() if region_weights is not None else None
                ),
                "condition_class_weights": (
                    condition_weights.detach().cpu().tolist()
                    if condition_weights is not None
                    else None
                ),
                "fracatlas_region_map": {
                    "hip": "hip",
                    "leg": "lower_leg",
                    "hand": "other",
                    "shoulder": "other",
                },
            }
        else:
            wait += 1
            if wait >= patience:
                print("[joint] Early stopping")
                break

    if best_state is None:
        raise RuntimeError("Joint training produced no checkpoint")

    model.load_state_dict(best_state["model_state_dict"])
    test_region, test_cond, test_both = joint_metrics(model, test_loader, device)
    best_state["test_region_accuracy"] = test_region
    best_state["test_condition_accuracy"] = test_cond
    best_state["test_both_known_accuracy"] = test_both
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, ckpt_path)
    print(f"[joint] Saved -> {ckpt_path}")
    print(
        f"[joint] Test region={test_region:.3f} cond={test_cond:.3f} "
        f"both_known={test_both:.3f}"
    )
    return best_state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=["joint", "region", "condition", "both"],
        default="joint",
        help="joint = recommended dual-head training on combined labels",
    )
    parser.add_argument("--region-data", type=Path, default=SERVICE_ROOT / "data")
    parser.add_argument(
        "--condition-data", type=Path, default=SERVICE_ROOT / "data" / "fracatlas"
    )
    parser.add_argument("--joint-data", type=Path, default=SERVICE_ROOT / "data")
    parser.add_argument(
        "--joint-labels",
        type=Path,
        default=SERVICE_ROOT / "data" / "joint" / "labels.csv",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=SERVICE_ROOT / "checkpoints" / "model.pth",
    )
    parser.add_argument("--epochs-region", type=int, default=15)
    parser.add_argument("--epochs-condition", type=int, default=12)
    parser.add_argument("--epochs-joint", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument(
        "--condition-loss-weight",
        type=float,
        default=1.5,
        help="Weight for condition loss in --phase joint (default 1.5)",
    )
    parser.add_argument(
        "--no-region-class-weights",
        action="store_true",
        help="Disable inverse-frequency class weights for region head",
    )
    parser.add_argument(
        "--no-condition-class-weights",
        action="store_true",
        help="Disable inverse-frequency class weights for condition head",
    )
    parser.add_argument(
        "--skip-region-if-checkpoint",
        action="store_true",
        help="In --phase both, skip region training if checkpoint already exists",
    )
    parser.add_argument(
        "--pretrain-region",
        action="store_true",
        help="With --phase joint: train region head on UNIFESP first, then joint from that checkpoint",
    )
    args = parser.parse_args()

    if args.phase == "joint":
        init_checkpoint: Path | None = None
        if args.pretrain_region:
            region_ckpt = args.checkpoint.with_name(f"{args.checkpoint.stem}.region{args.checkpoint.suffix}")
            train_region(
                args.region_data,
                args.epochs_region,
                args.batch_size,
                args.lr,
                args.seed,
                args.patience,
                None,
                region_ckpt,
            )
            init_checkpoint = region_ckpt
        train_joint(
            args.joint_data,
            args.joint_labels,
            args.epochs_joint,
            args.batch_size,
            args.lr,
            args.seed,
            args.patience,
            init_checkpoint,
            args.checkpoint,
            args.condition_loss_weight,
            use_region_class_weights=not args.no_region_class_weights,
            use_condition_class_weights=not args.no_condition_class_weights,
        )
        return

    if args.phase in ("region", "both"):
        if args.phase == "both" and args.skip_region_if_checkpoint and args.checkpoint.is_file():
            print(f"[region] Skipping - using existing {args.checkpoint}")
        else:
            train_region(
                args.region_data,
                args.epochs_region,
                args.batch_size,
                args.lr,
                args.seed,
                args.patience,
                None,
                args.checkpoint,
            )

    if args.phase in ("condition", "both"):
        train_condition(
            args.condition_data,
            args.epochs_condition,
            args.batch_size,
            args.lr,
            args.seed,
            args.patience,
            args.checkpoint,
            args.checkpoint,
        )


if __name__ == "__main__":
    main()
