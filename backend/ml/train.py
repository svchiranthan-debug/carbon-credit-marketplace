"""
Trains the ground-photo classifier (MobileNetV3-Small, 3 classes) on REAL photographs.

    python ml/build_real_dataset.py      # once: builds ml/dataset_real/{train,val,test}
    python ml/train.py                   # trains, keeps the best epoch on val, evaluates on test

Outputs
    ml/weights/plantation_classifier_v2.pt   checkpoint (model_state_dict + class_to_idx)
    ml/weights/model_metadata.json           training settings, per-epoch history, test metrics
    ml/reports/evaluation_v2.md              human-readable evaluation report

The test split (from the source dataset's own test set) is used exactly once, after training.
Input contract (must match app/services/ai/ai_vision_service.py): RGB, resize 224x224,
ImageNet mean/std normalisation.
"""
import argparse
import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms

ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "dataset_real"
WEIGHTS_DIR = ML_DIR / "weights"
REPORTS_DIR = ML_DIR / "reports"
MODEL_PATH = WEIGHTS_DIR / "plantation_classifier_v2.pt"
METADATA_PATH = WEIGHTS_DIR / "model_metadata.json"
INIT_CHECKPOINT = WEIGHTS_DIR / "plantation_classifier_v1.pt"

CLASSES = ["non_plantation", "plantation", "unclear_evidence"]
MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
SEED = 20261008


def transforms_for(train: bool):
    if train:
        return transforms.Compose([
            transforms.RandomResizedCrop(224, scale=(0.6, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.2),
            transforms.ToTensor(),
            transforms.Normalize(MEAN, STD),
        ])
    return transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(), transforms.Normalize(MEAN, STD)])


def build_model(init_from: Path = None):
    model = models.mobilenet_v3_small(weights=None)
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(CLASSES))
    init_note = "random initialisation"
    if init_from and init_from.exists():
        ckpt = torch.load(init_from, map_location="cpu")
        model.load_state_dict(ckpt["model_state_dict"])
        init_note = f"initialised from {init_from.name} (previous project checkpoint)"
    return model, init_note


@torch.no_grad()
def predict(model, loader):
    model.eval()
    ys, ps = [], []
    for x, y in loader:
        ps.append(model(x).argmax(1))
        ys.append(y)
    return torch.cat(ys).numpy(), torch.cat(ps).numpy()


def metrics(y_true, y_pred, n_classes):
    cm = np.zeros((n_classes, n_classes), dtype=int)
    for t, p in zip(y_true, y_pred):
        cm[t, p] += 1
    per_class = {}
    for i in range(n_classes):
        tp = cm[i, i]
        prec = tp / cm[:, i].sum() if cm[:, i].sum() else 0.0
        rec = tp / cm[i, :].sum() if cm[i, :].sum() else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_class[CLASSES[i]] = {"precision": round(float(prec), 4), "recall": round(float(rec), 4),
                                 "f1": round(float(f1), 4), "support": int(cm[i, :].sum())}
    acc = float(np.trace(cm) / cm.sum())
    macro_f1 = float(np.mean([v["f1"] for v in per_class.values()]))
    return {"accuracy": round(acc, 4), "macro_f1": round(macro_f1, 4), "per_class": per_class,
            "confusion_matrix": {"labels": CLASSES, "rows_true_cols_pred": cm.tolist()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--from-scratch", action="store_true", help="do not initialise from the v1 checkpoint")
    args = ap.parse_args()

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.set_num_threads(max(1, os.cpu_count() or 1))

    train_ds = datasets.ImageFolder(DATA_DIR / "train", transform=transforms_for(True))
    val_ds = datasets.ImageFolder(DATA_DIR / "val", transform=transforms_for(False))
    test_ds = datasets.ImageFolder(DATA_DIR / "test", transform=transforms_for(False))
    assert train_ds.classes == CLASSES, train_ds.classes
    loaders = {
        "train": DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=1),
        "val": DataLoader(val_ds, batch_size=64, num_workers=1),
        "test": DataLoader(test_ds, batch_size=64, num_workers=1),
    }

    model, init_note = build_model(None if args.from_scratch else INIT_CHECKPOINT)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)

    history, best_val, best_state = [], -1.0, None
    t0 = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        loss_sum, correct, seen = 0.0, 0, 0
        for x, y in loaders["train"]:
            optimizer.zero_grad()
            out = model(x)
            loss = criterion(out, y)
            loss.backward()
            optimizer.step()
            loss_sum += loss.item() * y.size(0)
            correct += (out.argmax(1) == y).sum().item()
            seen += y.size(0)
        scheduler.step()
        yv, pv = predict(model, loaders["val"])
        val_acc = float((yv == pv).mean())
        history.append({"epoch": epoch, "train_loss": round(loss_sum / seen, 4),
                        "train_acc": round(correct / seen, 4), "val_acc": round(val_acc, 4),
                        "elapsed_s": round(time.time() - t0, 1)})
        print(json.dumps(history[-1]), flush=True)
        if val_acc > best_val:
            best_val, best_state = val_acc, {k: v.clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    yt, pt = predict(model, loaders["test"])
    test = metrics(yt, pt, len(CLASSES))
    print("TEST", json.dumps(test), flush=True)

    WEIGHTS_DIR.mkdir(exist_ok=True)
    torch.save({"model_state_dict": model.state_dict(), "class_to_idx": train_ds.class_to_idx}, MODEL_PATH)

    meta = {
        "model_name": "MobileNetV3-Small-Plantation",
        "model_version": "2.0.0",
        "architecture": "MobileNetV3-Small",
        "classes": CLASSES,
        "class_to_idx": train_ds.class_to_idx,
        "input_resolution": "224x224",
        "preprocessing": "RGB, resize to 224x224, ToTensor, ImageNet mean/std normalisation",
        "training_data": (
            "Real photographs from the Intel Image Classification dataset (GitHub mirror "
            "luangtatipsy/intel-image-classification @ fbb0210). plantation = 'forest' photos; "
            "non_plantation = 'buildings', 'street', 'sea', 'glacier'; unclear_evidence = real photos "
            "with synthetic blur/darkness/over-exposure/occlusion. See ml/build_real_dataset.py."
        ),
        "validation_note": (
            "Test metrics are on the source dataset's held-out test split (real photos, never used in "
            "training). The dataset contains no areca/coconut/agroforestry plantation photos, so "
            "accuracy on real plantation field photos has NOT been measured."
        ),
        "initialisation": init_note,
        "split_sizes": {"train": len(train_ds), "val": len(val_ds), "test": len(test_ds)},
        "hyperparameters": {"epochs": args.epochs, "batch_size": args.batch_size, "lr": args.lr,
                            "optimizer": "AdamW(wd=1e-4)", "schedule": "cosine", "label_smoothing": 0.05,
                            "augmentation": "RandomResizedCrop(0.6-1.0), HFlip, ColorJitter"},
        "best_val_accuracy": round(best_val, 4),
        "test_metrics": test,
        "history": history,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "training_device": "cpu",
        "seed": SEED,
    }
    METADATA_PATH.write_text(json.dumps(meta, indent=2))
    write_report(meta)
    print(f"Saved {MODEL_PATH} and {METADATA_PATH}")


def write_report(meta):
    REPORTS_DIR.mkdir(exist_ok=True)
    t = meta["test_metrics"]
    rows = "\n".join(
        f"| {c} | {v['precision']:.3f} | {v['recall']:.3f} | {v['f1']:.3f} | {v['support']} |"
        for c, v in t["per_class"].items()
    )
    cm = t["confusion_matrix"]["rows_true_cols_pred"]
    cm_rows = "\n".join(f"| **{CLASSES[i]}** | " + " | ".join(str(x) for x in r) + " |" for i, r in enumerate(cm))
    hist = "\n".join(f"| {h['epoch']} | {h['train_loss']} | {h['train_acc']:.3f} | {h['val_acc']:.3f} |" for h in meta["history"])
    (REPORTS_DIR / "evaluation_v2.md").write_text(f"""# Ground-photo classifier v2 — evaluation

Model: {meta['model_name']} {meta['model_version']} ({meta['architecture']}), {meta['initialisation']}.
Trained {meta['trained_at']} on CPU. Split sizes: {meta['split_sizes']}.

## Data
{meta['training_data']}

## Held-out test set (real photos, never seen in training)

Accuracy **{t['accuracy']:.3f}**, macro F1 **{t['macro_f1']:.3f}**.

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
{rows}

Confusion matrix (rows = true, columns = predicted):

| | {' | '.join(CLASSES)} |
|---|---|---|---|
{cm_rows}

## Training history

| Epoch | Train loss | Train acc | Val acc |
|---|---|---|---|
{hist}

## Limits — read before quoting these numbers
- {meta['validation_note']}
- "unclear_evidence" examples are real photos degraded synthetically; real bad field photos may look different.
- Some source labels are noisy (for example, a few "glacier" photos show green slopes).
""")


if __name__ == "__main__":
    main()
