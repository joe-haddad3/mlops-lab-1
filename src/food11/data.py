from pathlib import Path
from PIL import Image
import shutil

# Category index -> name, based on the lab's mapping
CATEGORIES = {
    0: "Bread",
    1: "Dairy product",
    2: "Dessert",
    3: "Egg",
    4: "Fried food",
    5: "Meat",
    6: "Noodles-Pasta",
    7: "Rice",
    8: "Seafood",
    9: "Soup",
    10: "Vegetable-Fruit",
}

RAW_DIR = Path("data/food11_raw")
PROCESSED_DIR = Path("data/food11_processed")
MINI_DIR = Path("data/food11_processed_mini")
SPLITS = ["training", "evaluation", "validation"]
TARGET_SIZE = (128, 128)
MINI_LIMIT = 100


def get_category_from_filename(filename: str) -> str:
    # Food-11 filenames look like "0_123.jpg" -> category index is before the underscore
    category_index = int(filename.split("_")[0])
    return CATEGORIES[category_index]


def process_split(split: str):
    split_dir = RAW_DIR / split
    if not split_dir.exists():
        print(f"Warning: {split_dir} does not exist, skipping")
        return

    mini_counts = {name: 0 for name in CATEGORIES.values()}

    for image_path in split_dir.iterdir():
        if not image_path.is_file():
            continue

        category = get_category_from_filename(image_path.name)

        # Resize and save to food11_processed
        out_dir = PROCESSED_DIR / split / category
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / image_path.name

        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img_resized = img.resize(TARGET_SIZE)
            img_resized.save(out_path)

        # Also save to food11_processed_mini, capped at MINI_LIMIT per category
        if mini_counts[category] < MINI_LIMIT:
            mini_out_dir = MINI_DIR / split / category
            mini_out_dir.mkdir(parents=True, exist_ok=True)
            mini_out_path = mini_out_dir / image_path.name
            shutil.copy(out_path, mini_out_path)
            mini_counts[category] += 1

    print(f"Finished processing split: {split}")


def main():
    for split in SPLITS:
        process_split(split)
    print("Done. Processed datasets are in data/food11_processed and data/food11_processed_mini")


if __name__ == "__main__":
    main()