import os
import torch
import torch.nn as nn
from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "dataset")
WEIGHTS_PATH = os.path.join(BASE_DIR, "weights", "plantation_classifier_v1.pt")
METADATA_PATH = os.path.join(BASE_DIR, "weights", "model_metadata.json")

def evaluate_model():
    print("--- Evaluating Plantation AI Vision Model ---")
    if not os.path.exists(WEIGHTS_PATH):
        raise FileNotFoundError(f"Model weights not found at {WEIGHTS_PATH}. Run train.py first.")
        
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Evaluation device: {device}")
    
    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    val_dataset = datasets.ImageFolder(os.path.join(DATA_DIR, "val"), transform=val_transform)
    val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)
    
    checkpoint = torch.save if False else torch.load(WEIGHTS_PATH, map_location=device)
    class_to_idx = checkpoint.get("class_to_idx", val_dataset.class_to_idx)
    idx_to_class = {v: k for k, v in class_to_idx.items()}
    
    model = models.mobilenet_v3_small(weights=None)
    in_features = model.classifier[3].in_features
    model.classifier[3] = nn.Linear(in_features, len(class_to_idx))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    
    y_true = []
    y_pred = []
    
    with torch.no_grad():
        for inputs, labels in val_loader:
            inputs = inputs.to(device)
            outputs = model(inputs)
            _, preds = outputs.max(1)
            y_true.extend(labels.tolist())
            y_pred.extend(preds.cpu().tolist())
            
    # Confusion matrix & metrics
    num_classes = len(class_to_idx)
    conf_matrix = [[0] * num_classes for _ in range(num_classes)]
    for t, p in zip(y_true, y_pred):
        conf_matrix[t][p] += 1
        
    total = len(y_true)
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = (correct / total) * 100.0
    
    print("\nConfusion Matrix (Rows: Actual, Cols: Predicted):")
    class_names = [idx_to_class[i] for i in range(num_classes)]
    header = f"{'Actual / Pred':<18}" + "".join([f"{name[:12]:>14}" for name in class_names])
    print(header)
    print("-" * len(header))
    for i, row in enumerate(conf_matrix):
        row_str = f"{class_names[i]:<18}" + "".join([f"{val:>14}" for val in row])
        print(row_str)
        
    print(f"\nOverall Validation Accuracy: {accuracy:.2f}% ({correct}/{total})")
    
    # Class-level precision & recall
    for i, name in enumerate(class_names):
        tp = conf_matrix[i][i]
        fp = sum(conf_matrix[r][i] for r in range(num_classes) if r != i)
        fn = sum(conf_matrix[i][c] for c in range(num_classes) if c != i)
        
        prec = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        print(f"Class '{name}': Precision = {prec:.1f}%, Recall = {rec:.1f}%, F1 = {f1:.1f}%")

if __name__ == "__main__":
    evaluate_model()
