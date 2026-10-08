"""
Evaluates a checkpoint on the held-out REAL test split (ml/dataset_real/test).

    python ml/build_real_dataset.py                       # once
    python ml/evaluate.py                                 # evaluates weights/plantation_classifier_v2.pt
    python ml/evaluate.py --weights weights/plantation_classifier_v1.pt   # compare the old model
"""
import argparse
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from torchvision import datasets

from train import CLASSES, DATA_DIR, build_model, metrics, predict, transforms_for

ML_DIR = Path(__file__).resolve().parent

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default=str(ML_DIR / "weights" / "plantation_classifier_v2.pt"))
    args = ap.parse_args()
    model, _ = build_model(None)
    model.load_state_dict(torch.load(args.weights, map_location="cpu")["model_state_dict"])
    ds = datasets.ImageFolder(DATA_DIR / "test", transform=transforms_for(False))
    assert ds.classes == CLASSES
    y, p = predict(model, DataLoader(ds, batch_size=64))
    print(json.dumps(metrics(y, p, len(CLASSES)), indent=2))
