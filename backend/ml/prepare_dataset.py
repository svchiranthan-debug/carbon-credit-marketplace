import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

DATASET_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DATASET_ROOT, "dataset")

CLASSES = ["plantation", "non_plantation", "unclear_evidence"]

def create_directory_structure():
    for split in ["train", "val"]:
        for cls_name in CLASSES:
            path = os.path.join(DATA_DIR, split, cls_name)
            os.makedirs(path, exist_ok=True)

def generate_plantation_image(seed: int, size=(256, 256)) -> Image.Image:
    """Generates foliage, leaves, tree trunks, and canopy texture."""
    np.random.seed(seed)
    # Green/brown palette
    base = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    # Forest floor / canopy variation
    green_channel = np.clip(np.random.normal(130, 30, (size[1], size[0])), 60, 220)
    red_channel = np.clip(green_channel * 0.45 + np.random.normal(20, 10, (size[1], size[0])), 20, 120)
    blue_channel = np.clip(green_channel * 0.35 + np.random.normal(15, 8, (size[1], size[0])), 15, 90)
    
    base[:, :, 0] = red_channel.astype(np.uint8)
    base[:, :, 1] = green_channel.astype(np.uint8)
    base[:, :, 2] = blue_channel.astype(np.uint8)
    
    img = Image.fromarray(base)
    draw = ImageDraw.Draw(img)
    # Add trunk/branch shapes
    for _ in range(5 + (seed % 6)):
        x0 = np.random.randint(0, size[0])
        y0 = np.random.randint(size[1] // 2, size[1])
        x1 = x0 + np.random.randint(-20, 20)
        y1 = np.random.randint(0, size[1] // 3)
        draw.line([x0, y0, x1, y1], fill=(70, 45, 25), width=np.random.randint(6, 16))
    
    # Add foliage clusters
    for _ in range(15 + (seed % 10)):
        cx = np.random.randint(0, size[0])
        cy = np.random.randint(0, size[1] * 2 // 3)
        r = np.random.randint(15, 45)
        g_val = np.random.randint(110, 220)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(int(g_val * 0.4), g_val, int(g_val * 0.25)))
        
    return img.filter(ImageFilter.GaussianBlur(1))

def generate_non_plantation_image(seed: int, size=(256, 256)) -> Image.Image:
    """Generates non-plantation scene (concrete, asphalt, brick walls, steel structures)."""
    np.random.seed(seed)
    base = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    
    # Concrete gray / asphalt dark / red brick
    scene_type = seed % 3
    if scene_type == 0:  # Concrete / Road gray
        gray = np.clip(np.random.normal(140, 15, (size[1], size[0])), 90, 200).astype(np.uint8)
        base[:, :, 0] = gray
        base[:, :, 1] = gray
        base[:, :, 2] = gray
    elif scene_type == 1:  # Red brick / building
        r = np.clip(np.random.normal(170, 20, (size[1], size[0])), 110, 230).astype(np.uint8)
        g = np.clip(r * 0.4, 30, 90).astype(np.uint8)
        b = np.clip(r * 0.35, 20, 80).astype(np.uint8)
        base[:, :, 0] = r
        base[:, :, 1] = g
        base[:, :, 2] = b
    else:  # Blue/metallic facade
        b = np.clip(np.random.normal(160, 20, (size[1], size[0])), 100, 220).astype(np.uint8)
        base[:, :, 0] = (b * 0.7).astype(np.uint8)
        base[:, :, 1] = (b * 0.75).astype(np.uint8)
        base[:, :, 2] = b
        
    img = Image.fromarray(base)
    draw = ImageDraw.Draw(img)
    # Add architectural grid / rectangular structures
    for i in range(0, size[0], 32):
        draw.line([i, 0, i, size[1]], fill=(50, 50, 55), width=2)
    for j in range(0, size[1], 24):
        draw.line([0, j, size[0], j], fill=(50, 50, 55), width=2)
        
    return img

def generate_unclear_evidence_image(seed: int, size=(256, 256)) -> Image.Image:
    """Generates blurry, dark, overexposed, or obstructed evidence."""
    np.random.seed(seed)
    case = seed % 3
    if case == 0:  # Pitch black / heavy underexposure
        base = np.random.randint(0, 18, (size[1], size[0], 3), dtype=np.uint8)
        return Image.fromarray(base)
    elif case == 1:  # Heavy white overexposure / washed out
        base = np.random.randint(235, 256, (size[1], size[0], 3), dtype=np.uint8)
        return Image.fromarray(base)
    else:  # Heavy motion blur / finger obscuring camera lens
        base = np.random.randint(80, 160, (size[1], size[0], 3), dtype=np.uint8)
        img = Image.fromarray(base)
        draw = ImageDraw.Draw(img)
        # Finger/thumb smudge
        draw.ellipse([20, 20, 240, 240], fill=(180, 80, 60))
        return img.filter(ImageFilter.GaussianBlur(18))

def build_dataset():
    create_directory_structure()
    print("Building ML Dataset for Multi-Modal Plantation Image Verification...")
    
    # Train set: 40 samples per class
    # Val set: 15 samples per class
    splits = {
        "train": 40,
        "val": 15
    }
    
    for split, count in splits.items():
        # 1. Plantation
        for i in range(count):
            seed = 1000 + (0 if split == "train" else 500) + i
            img = generate_plantation_image(seed)
            img.save(os.path.join(DATA_DIR, split, "plantation", f"plant_{split}_{i:03d}.jpg"))
            
        # 2. Non-Plantation
        for i in range(count):
            seed = 2000 + (0 if split == "train" else 500) + i
            img = generate_non_plantation_image(seed)
            img.save(os.path.join(DATA_DIR, split, "non_plantation", f"nonplant_{split}_{i:03d}.jpg"))
            
        # 3. Unclear Evidence
        for i in range(count):
            seed = 3000 + (0 if split == "train" else 500) + i
            img = generate_unclear_evidence_image(seed)
            img.save(os.path.join(DATA_DIR, split, "unclear_evidence", f"unclear_{split}_{i:03d}.jpg"))
            
    print(f"Dataset generated successfully in {DATA_DIR}")
    for split in ["train", "val"]:
        for c in CLASSES:
            p = os.path.join(DATA_DIR, split, c)
            print(f"  [{split}] {c}: {len(os.listdir(p))} images")

if __name__ == "__main__":
    build_dataset()
