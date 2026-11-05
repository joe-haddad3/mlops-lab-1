"""Check a processed Food-11 folder against the data contract.

usage: python src/food11/validate_data.py data/food11_processed_mini [--min-per-class 50] [--tau 0.05]

Exits with status 1 if any check fails, so it can gate a pipeline.
"""

import argparse
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image

CLASSES = [
    "Bread",
    "Dairy product",
    "Dessert",
    "Egg",
    "Fried food",
    "Meat",
    "Noodles-Pasta",
    "Rice",
    "Seafood",
    "Soup",
    "Vegetable-Fruit",
]
SPLITS = ["training", "validation", "evaluation"]
IMAGE_SIZE = (128, 128)


def list_images(root: Path) -> dict[str, dict[str, list[Path]]]:
    """{split: {class: [paths]}} for every class folder that exists."""
    out: dict[str, dict[str, list[Path]]] = {}
    for split in SPLITS:
        split_dir = root / split
        out[split] = {}
        if not split_dir.is_dir():
            continue
        for class_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
            out[split][class_dir.name] = sorted(class_dir.glob("*.jpg"))
    return out


def check_class_folders(images) -> list[str]:
    errors = []
    expected = set(CLASSES)
    for split in SPLITS:
        found = set(images[split])
        if found != expected:
            missing = sorted(expected - found)
            extra = sorted(found - expected)
            errors.append(f"{split}: missing={missing} extra={extra}")
    return errors


def check_images(images) -> list[str]:
    errors = []
    for classes in images.values():
        for paths in classes.values():
            for path in paths:
                try:
                    with Image.open(path) as img:
                        img.load()
                        if img.mode != "RGB" or img.size != IMAGE_SIZE:
                            errors.append(f"{path}: mode={img.mode} size={img.size}")
                except Exception as e:  # noqa: BLE001 - any failure to open is a contract violation
                    errors.append(f"{path}: cannot open ({e})")
    return errors


def check_min_per_class(images, min_per_class: int) -> list[str]:
    errors = []
    for split, classes in images.items():
        for name, paths in classes.items():
            if len(paths) < min_per_class:
                errors.append(f"{split}/{name}: {len(paths)} images < {min_per_class}")
    return errors


def check_no_leakage(images) -> list[str]:
    seen: dict[str, set[str]] = defaultdict(set)
    where: dict[str, list[Path]] = defaultdict(list)
    for split, classes in images.items():
        for paths in classes.values():
            for path in paths:
                digest = hashlib.md5(path.read_bytes()).hexdigest()
                seen[digest].add(split)
                where[digest].append(path)
    return [
        f"same content in {sorted(splits)}: {[str(p) for p in where[digest]]}"
        for digest, splits in seen.items()
        if len(splits) > 1
    ]


def class_shares(classes: dict[str, list[Path]]) -> dict[str, float]:
    total = sum(len(p) for p in classes.values()) or 1
    return {name: len(paths) / total for name, paths in classes.items()}


def check_distribution(images, tau: float) -> list[str]:
    train = class_shares(images["training"])
    val = class_shares(images["validation"])
    errors = []
    for name in CLASSES:
        diff = abs(train.get(name, 0.0) - val.get(name, 0.0))
        if diff > tau:
            errors.append(
                f"{name}: train share {train.get(name, 0.0):.3f} vs val {val.get(name, 0.0):.3f} (|diff|={diff:.3f} > {tau})"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--min-per-class", type=int, default=50)
    parser.add_argument("--tau", type=float, default=0.05)
    args = parser.parse_args()

    images = list_images(args.root)
    checks = [
        ("11 class folders per split", check_class_folders(images)),
        ("images open, RGB, 128x128", check_images(images)),
        (f"at least {args.min_per_class} images per class", check_min_per_class(images, args.min_per_class)),
        ("no image in two splits", check_no_leakage(images)),
        (f"train/val class shares within {args.tau}", check_distribution(images, args.tau)),
    ]

    n_images = sum(len(p) for c in images.values() for p in c.values())
    print(f"validating {args.root} ({n_images} images)")
    failed = False
    for name, errors in checks:
        print(f"{'PASS' if not errors else 'FAIL'}  {name}")
        for err in errors[:5]:
            print(f"      {err}")
        if len(errors) > 5:
            print(f"      ... and {len(errors) - 5} more")
        failed = failed or bool(errors)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
