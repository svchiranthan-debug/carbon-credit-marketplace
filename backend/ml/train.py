import os
import json
import time
from datetime import datetime
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "dataset")
WEIGHTS_DIR = os.path.join(BASE_DIR, "weights")
os.makedirs(WEIGHTS_DIR, exist_ok=True)

MODEL_SAVE_PATH = os.path.join(WEIGHTS_DIR, "plantation_classifier_v1.pt")
METADATA_SAVE_PATH = os.path.join(WEIGHTS_DIR, "model_metadata.json")

# Hyperparameters
BATCH_SIZE = 16
NUM_EPOCHS = 8
LEARNING_RATE = 0.001
NUM_CLASSES = 3
CLASSES = ["non_plantation", "plantation", "unclear_evidence"]

def get_transforms():
    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.1, contrast=0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    return train_transform, val_transform

def build_model():
    print("Initializing lightweight MobileNetV3-Small architecture for MacBook Air M2...")
    try:
        # Load pre-trained weights if network allows
        weights = models.MobileNet_V3_Small_Weights.DEFAULT
        model = models.mobilenet_v3_small(weights=weights)
    except Exception:
        # Fallback to initialized MobileNetV3
        model = models.mobilenet_v3_small(weights=None)
        
    in_features = model.classifier[3].in_features
    # Replace final classification head with 3 classes
    model.classifier[3] = nn.Linear(in_features, NUM_CLASSES)
    return model

def train_model():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Using compute device: {device}")
    
    train_transform, val_transform = get_transforms()
    
    train_dataset = datasets.ImageFolder(os.path.join(DATA_DIR, "train"), transform=train_transform)
    val_dataset = datasets.ImageFolder(os.path.join(DATA_DIR, "val"), transform=val_transform)
    
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)
    
    print(f"Class mapping: {train_dataset.class_to_idx}")
    
    model = build_model().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    
    start_time = time.time()
    best_val_acc = 0.0
    history = []
    
    print(f"\n--- Starting Training ({NUM_EPOCHS} Epochs) ---")
    for epoch in range(1, NUM_EPOCHS + 1):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        
        for inputs, labels in train_loader:
            inputs, labels = inputs.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item() * inputs.size(0)
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
            
        train_loss = running_loss / total
        train_acc = (correct / total) * 100.0
        
        # Validation phase
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                val_loss += loss.item() * inputs.size(0)
                _, predicted = outputs.max(1)
                val_total += labels.size(0)
                val_correct += predicted.eq(labels).sum().item()
                
        val_loss = val_loss / val_total
        val_acc = (val_correct / val_total) * 100.0
        
        print(f"Epoch [{epoch:02d}/{NUM_EPOCHS:02d}] - "
              f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.1f}% | "
              f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.1f}%")
              
        history.append({
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "train_acc": round(train_acc, 2),
            "val_loss": round(val_loss, 4),
            "val_acc": round(val_acc, 2)
        })
        
        if val_acc >= best_val_acc:
            best_val_acc = val_acc
            # Save PyTorch checkpoint
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "class_to_idx": train_dataset.class_to_idx,
                "val_acc": val_acc
            }, MODEL_SAVE_PATH)

    training_duration_sec = round(time.time() - start_time, 2)
    print(f"\nTraining Complete in {training_duration_sec}s! Best Val Accuracy: {best_val_acc:.1f}%")
    print(f"Model saved to: {MODEL_SAVE_PATH}")
    
    metadata = {
        "model_name": "MobileNetV3-Small-Agroforestry",
        "model_version": "1.0.0",
        "architecture": "MobileNetV3-Small",
        "classes": list(train_dataset.class_to_idx.keys()),
        "class_to_idx": train_dataset.class_to_idx,
        "input_resolution": "224x224",
        "best_val_accuracy_pct": round(best_val_acc, 2),
        "epochs_trained": NUM_EPOCHS,
        "training_device": str(device),
        "trained_at": datetime.utcnow().isoformat(),
        "training_duration_seconds": training_duration_sec,
        "history": history
    }
    
    with open(METADATA_SAVE_PATH, "w") as f:
        json.dump(metadata, f, indent=2)
        
    print(f"Model metadata saved to: {METADATA_SAVE_PATH}")

if __name__ == "__main__":
    train_model()
