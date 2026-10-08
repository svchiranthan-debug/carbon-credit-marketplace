"""
Builds the REAL-photo training set for the ground-photo classifier.

Source: Intel Image Classification dataset (real 150x150 scene photographs; originally from
the Analytics Vidhya / Intel Scene Classification challenge, redistributed on Kaggle). We read
it from a public GitHub mirror pinned to a fixed commit, so the build is reproducible:
    https://github.com/luangtatipsy/intel-image-classification  (MIT-licensed repository)

Class mapping (and its limits — be explicit about these in reports):
    plantation        <- "forest" photos (tree canopy / dense vegetation). There are NO areca,
                         coconut or other plantation photos in this dataset; "plantation" here
                         means "tree canopy present".
    non_plantation    <- "buildings", "street", "sea", "glacier" photos (man-made or
                         non-vegetated scenes), sampled evenly to match the plantation count.
    unclear_evidence  <- real photos from all six source classes, degraded the way bad field
                         photos are: heavy blur, motion blur, near-black, over-exposed, or mostly
                         covered by a finger/object. The degradation is synthetic; the
                         underlying photos are real.

Splits: train/val come from the source's seg_train (90/10, stratified, seeded); test comes
only from seg_test, which no training step ever sees.

    python ml/build_real_dataset.py                 # clone (sparse) + build into ml/dataset_real/
    python ml/build_real_dataset.py --source DIR    # use an existing checkout of the mirror
"""
import argparse
import os
import random
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

MIRROR_URL = "https://github.com/luangtatipsy/intel-image-classification"
MIRROR_COMMIT = "fbb021005ad6aa281444f784bc4c2187a52a6111"

ML_DIR = Path(__file__).resolve().parent
DEFAULT_OUT = ML_DIR / "dataset_real"
DEFAULT_CACHE = ML_DIR / ".cache" / "intel-image-classification"

NON_PLANTATION_SOURCES = ["buildings", "street", "sea", "glacier"]
ALL_SOURCES = ["buildings", "forest", "glacier", "mountain", "sea", "street"]
SEED = 20261008


def fetch_mirror(cache: Path) -> Path:
    if (cache / "datasets" / "seg_test").is_dir():
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", MIRROR_URL, str(cache)], check=True)
    subprocess.run(["git", "-C", str(cache), "sparse-checkout", "set", "datasets/seg_train", "datasets/seg_test"], check=True)
    subprocess.run(["git", "-C", str(cache), "checkout", MIRROR_COMMIT], check=True)
    return cache


def list_images(folder: Path):
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})


# ---------------------------------------------------------------- degradations (unclear_evidence)
def _motion_blur(img: Image.Image, rng: random.Random) -> Image.Image:
    arr = np.asarray(img).astype(np.float32)
    k = rng.randint(15, 27)
    horizontal = rng.random() < 0.5
    out = np.zeros_like(arr)
    for i in range(k):
        out += np.roll(arr, i - k // 2, axis=1 if horizontal else 0)
    return Image.fromarray(np.clip(out / k, 0, 255).astype(np.uint8))


def _occlude(img: Image.Image, rng: random.Random) -> Image.Image:
    img = img.copy()
    w, h = img.size
    draw = ImageDraw.Draw(img)
    colour = rng.choice([(40, 30, 28), (190, 140, 115), (120, 85, 70), (15, 15, 15)])
    cover = rng.uniform(0.65, 0.9)
    rx, ry = w * cover, h * cover
    cx, cy = rng.uniform(0, w), rng.uniform(0, h)
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=colour)
    return img.filter(ImageFilter.GaussianBlur(2))


def degrade(img: Image.Image, rng: random.Random) -> Image.Image:
    kind = rng.choice(["blur", "motion", "dark", "overexposed", "occluded"])
    if kind == "blur":
        return img.filter(ImageFilter.GaussianBlur(rng.uniform(5, 10)))
    if kind == "motion":
        return _motion_blur(img, rng)
    if kind == "dark":
        dark = ImageEnhance.Brightness(img).enhance(rng.uniform(0.03, 0.12))
        noise = np.random.default_rng(rng.randint(0, 2**31)).normal(0, 4, (img.size[1], img.size[0], 3))
        return Image.fromarray(np.clip(np.asarray(dark, dtype=np.float32) + noise, 0, 255).astype(np.uint8))
    if kind == "overexposed":
        return ImageEnhance.Brightness(img).enhance(rng.uniform(3.5, 6.0))
    return _occlude(img, rng)


# ---------------------------------------------------------------- build
def build(source_root: Path, out: Path) -> dict:
    rng = random.Random(SEED)
    if out.exists():
        shutil.rmtree(out)
    counts = {}

    def save(src: Path, split: str, cls: str, img: Image.Image = None):
        dst_dir = out / split / cls
        dst_dir.mkdir(parents=True, exist_ok=True)
        (img or Image.open(src).convert("RGB")).save(dst_dir / f"{src.parent.name}_{src.stem}.jpg", quality=92)
        counts[(split, cls)] = counts.get((split, cls), 0) + 1

    for source_split, splits in (("seg_train", ("train", "val")), ("seg_test", ("test",))):
        base = source_root / "datasets" / source_split
        pools = {c: list_images(base / c) for c in ALL_SOURCES}
        for c in pools:
            rng.shuffle(pools[c])

        forest = pools["forest"]
        n = len(forest)
        per_np = n // len(NON_PLANTATION_SOURCES)
        non_plant = [p for c in NON_PLANTATION_SOURCES for p in pools[c][:per_np]]
        # Unclear sources: images NOT used above, from every class (real photos, then degraded)
        leftovers = [p for c in ALL_SOURCES for p in (pools[c][per_np:] if c in NON_PLANTATION_SOURCES else
                                                       pools[c] if c == "mountain" else [])]
        rng.shuffle(leftovers)
        unclear = leftovers[:n]

        for cls, items in (("plantation", forest), ("non_plantation", non_plant), ("unclear_evidence", unclear)):
            items = list(items)
            rng.shuffle(items)
            if len(splits) == 2:
                cut = int(len(items) * 0.9)
                parts = {"train": items[:cut], "val": items[cut:]}
            else:
                parts = {"test": items}
            for split, part in parts.items():
                for p in part:
                    if cls == "unclear_evidence":
                        save(p, split, cls, degrade(Image.open(p).convert("RGB"), rng))
                    else:
                        save(p, split, cls)
    return {f"{s}/{c}": n for (s, c), n in sorted(counts.items())}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path, help="existing checkout of the mirror repository")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    src = args.source or fetch_mirror(DEFAULT_CACHE)
    for k, v in build(src, args.out).items():
        print(f"{k:32s} {v}")
