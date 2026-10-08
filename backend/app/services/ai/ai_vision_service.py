"""
Ground-photo classifier (MobileNetV3-Small, 3 classes).

Model contract (must match ml/train.py):
  input   : one RGB image, resized to 224x224, ImageNet mean/std normalisation
  output  : softmax over {non_plantation, plantation, unclear_evidence}

Weights (v2): trained on real photographs (Intel Image Classification; see
ml/build_real_dataset.py) and evaluated on a held-out real test set (accuracy 0.984, see
ml/reports/evaluation_v2.md). LIMITATION: that dataset has no areca/coconut/agroforestry
plantation photos ("plantation" was learned from forest photos), so accuracy on real
plantation field photos has not been measured.

Failure policy: if the model is missing, the image is invalid, or inference fails, this
service returns ``available=False`` with a reason and null scores. It never substitutes a
default score.
"""
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

from PIL import Image, UnidentifiedImageError

from ...config import settings

logger = logging.getLogger(__name__)

EXPECTED_CLASSES = ("non_plantation", "plantation", "unclear_evidence")
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "TIFF", "MPO"}
MIN_IMAGE_SIDE_PX = 64
MAX_IMAGE_PIXELS = 50_000_000
INPUT_SIZE = (224, 224)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def validate_image_file(image_path: Optional[str]) -> Tuple[bool, str, Dict[str, Any]]:
    """Checks that a file is a decodable photo the model can accept. Returns (ok, reason, info)."""
    if not image_path:
        return False, "No ground photograph provided.", {}
    if not os.path.isfile(image_path):
        return False, "Ground photograph file not found on server.", {}
    size = os.path.getsize(image_path)
    if size == 0:
        return False, "Ground photograph file is empty.", {}
    if size > settings.MAX_UPLOAD_BYTES:
        return False, f"Ground photograph exceeds {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.", {}
    try:
        with Image.open(image_path) as img:
            img.verify()
        with Image.open(image_path) as img:
            fmt = img.format
            width, height = img.size
            img.convert("RGB").load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        return False, f"Ground photograph could not be decoded ({exc.__class__.__name__}).", {}
    if fmt not in ALLOWED_IMAGE_FORMATS:
        return False, f"Unsupported image format '{fmt}'.", {}
    if min(width, height) < MIN_IMAGE_SIDE_PX:
        return False, f"Ground photograph is too small ({width}x{height}); minimum side is {MIN_IMAGE_SIDE_PX}px.", {}
    if width * height > MAX_IMAGE_PIXELS:
        return False, f"Ground photograph is too large ({width}x{height}).", {}
    return True, "", {"format": fmt, "width": width, "height": height, "bytes": size}


def _load_metadata() -> Dict[str, Any]:
    try:
        with open(settings.ML_METADATA_PATH, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


class AIVisionService:
    _model = None
    _device = None
    _idx_to_class: Optional[Dict[int, str]] = None
    _load_error: Optional[str] = None
    _metadata: Dict[str, Any] = {}

    CLASS_DISPLAY_NAMES = {
        "plantation": "Plantation / Agroforestry",
        "non_plantation": "Non-Plantation (Urban/Barren/Man-made)",
        "unclear_evidence": "Unclear / Poor Evidence (Blur/Dark/Obstructed)",
    }

    @classmethod
    def model_info(cls) -> Dict[str, Any]:
        meta = cls._metadata or _load_metadata()
        return {
            "model_name": meta.get("model_name", "MobileNetV3-Small-Agroforestry"),
            "model_version": meta.get("model_version", "unknown"),
            "training_data": meta.get(
                "training_data",
                "See ml/weights/model_metadata.json",
            ),
        }

    @classmethod
    def load_model(cls):
        if cls._model is not None:
            return cls._model
        cls._load_error = None
        cls._metadata = _load_metadata()

        try:
            import torch
            import torch.nn as nn
            from torchvision import models
        except ImportError as exc:
            cls._load_error = f"PyTorch/torchvision not installed ({exc})."
            return None

        if not os.path.exists(settings.ML_MODEL_PATH):
            cls._load_error = f"Model weights not found at {settings.ML_MODEL_PATH}."
            return None

        try:
            cls._device = torch.device("cpu")
            checkpoint = torch.load(settings.ML_MODEL_PATH, map_location=cls._device)
            class_to_idx = checkpoint.get("class_to_idx")
            if not class_to_idx or set(class_to_idx) != set(EXPECTED_CLASSES):
                cls._load_error = f"Checkpoint classes {class_to_idx} do not match expected {EXPECTED_CLASSES}."
                return None
            meta_classes = cls._metadata.get("class_to_idx")
            if meta_classes and meta_classes != class_to_idx:
                cls._load_error = "Checkpoint class mapping disagrees with model_metadata.json."
                return None

            model = models.mobilenet_v3_small(weights=None)
            model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(class_to_idx))
            model.load_state_dict(checkpoint["model_state_dict"])
            model.to(cls._device)
            model.eval()

            cls._idx_to_class = {v: k for k, v in class_to_idx.items()}
            cls._model = model
            return model
        except Exception as exc:  # corrupt checkpoint, shape mismatch, etc.
            cls._load_error = f"Failed to load model weights ({exc.__class__.__name__}: {exc})."
            logger.error(cls._load_error)
            return None

    @staticmethod
    def _unavailable(reason: str, **extra: Any) -> Dict[str, Any]:
        return {
            "available": False,
            "reason": reason,
            "predicted_class": None,
            "prediction_label": None,
            "confidence_pct": None,
            "class_probabilities": {},
            "cv_score": None,
            "cv_status": "NOT AVAILABLE",
            **AIVisionService.model_info(),
            **extra,
        }

    @staticmethod
    def score_from_prediction(pred_key: str, confidence: float) -> Tuple[float, str, str]:
        """Deterministic, documented mapping from (class, confidence%) to the 0-100 CV score."""
        if pred_key == "plantation":
            return (
                round(70.0 + (confidence / 100.0) * 28.0, 1),
                f"Plantation canopy detected ({confidence}% confidence)",
                "Classifier assigned the highest probability to the plantation/agroforestry class.",
            )
        if pred_key == "non_plantation":
            return (
                round(max(10.0, 40.0 - (confidence / 100.0) * 25.0), 1),
                f"Non-plantation scene detected ({confidence}% confidence)",
                "Classifier assigned the highest probability to urban/barren/man-made surfaces.",
            )
        return (
            round(max(15.0, 35.0 - (confidence / 100.0) * 15.0), 1),
            f"Unclear / poor image evidence ({confidence}% confidence)",
            "Classifier judged the photo too blurred, dark or obstructed to assess.",
        )

    @classmethod
    def verify_image(cls, image_path: Optional[str]) -> Dict[str, Any]:
        ok, reason, info = validate_image_file(image_path)
        if not ok:
            return cls._unavailable(reason)

        model = cls.load_model()
        if model is None:
            return cls._unavailable(f"ML model unavailable: {cls._load_error}")

        try:
            import torch
            from torchvision import transforms

            transform = transforms.Compose([
                transforms.Resize(INPUT_SIZE),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ])
            with Image.open(image_path) as pil_img:
                tensor = transform(pil_img.convert("RGB")).unsqueeze(0).to(cls._device)
            if tuple(tensor.shape) != (1, 3, *INPUT_SIZE):
                return cls._unavailable(f"Unexpected model input shape {tuple(tensor.shape)}.")

            with torch.no_grad():
                probs = torch.softmax(model(tensor), dim=1).squeeze(0)
            if not torch.isfinite(probs).all():
                return cls._unavailable("Model produced non-finite probabilities.")

            top_prob, top_idx = probs.max(0)
            pred_key = cls._idx_to_class[int(top_idx.item())]
            confidence = round(float(top_prob.item()) * 100.0, 1)
            prob_dict = {cls._idx_to_class[i]: round(float(probs[i].item()) * 100.0, 1) for i in range(len(probs))}
            cv_score, cv_status, notes = cls.score_from_prediction(pred_key, confidence)

            return {
                "available": True,
                "reason": None,
                "predicted_class": pred_key,
                "prediction_label": cls.CLASS_DISPLAY_NAMES.get(pred_key, pred_key),
                "confidence_pct": confidence,
                "class_probabilities": prob_dict,
                "cv_score": cv_score,
                "cv_status": cv_status,
                "feature_evidence": notes,
                "image_info": info,
                **cls.model_info(),
            }
        except Exception as exc:
            logger.error("Inference error on %s: %s", image_path, exc)
            return cls._unavailable(f"Inference failed ({exc.__class__.__name__}).")
