"""Prepare the Food-11 dataset.

Reads data/food11_raw/{training,evaluation,validation}/<class>_<index>.jpg,
resizes each image to 128x128 and writes it into a folder named after its
category. Also builds a "mini" copy with at most 100 images per category.
"""

from pathlib import Path

from PIL import Image

RAW_DIR = Path("data/food11_raw")
PROCESSED_DIR = Path("data/food11_processed")
MINI_DIR = Path("data/food11_processed_mini")

SPLITS = ["training", "evaluation", "validation"]
MINI_PER_CATEGORY = 100

# The number prefixing each raw filename is the category index.
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


def category_from_filename(filename: str) -> str:
    """'3_120.jpg' -> 'Egg'"""
    index = int(Path(filename).name.split("_")[0])
    return CLASSES[index - 1]


def resize_image(img: Image.Image, size: int = 128) -> Image.Image:
    """Returns an RGB image of size x size."""
    return img.convert("RGB").resize((size, size))


def process_split(split: str) -> None:
    src_dir = RAW_DIR / split
    counts = {category: 0 for category in CLASSES}

    for src_path in sorted(src_dir.glob("*.jpg")):
        category = category_from_filename(src_path.name)

        with Image.open(src_path) as image:
            resized = resize_image(image)

            out_dir = PROCESSED_DIR / split / category
            out_dir.mkdir(parents=True, exist_ok=True)
            resized.save(out_dir / src_path.name)

            if counts[category] < MINI_PER_CATEGORY:
                mini_dir = MINI_DIR / split / category
                mini_dir.mkdir(parents=True, exist_ok=True)
                resized.save(mini_dir / src_path.name)

        counts[category] += 1

    print(f"{split}: {sum(counts.values())} images")


def main() -> None:
    for split in SPLITS:
        process_split(split)


if __name__ == "__main__":
    main()
