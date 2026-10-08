import os
import logging
from typing import Dict, Any, Optional
from PIL import Image
import torch
import torch.nn as nn
from torchvision import transforms, models

from ...config import settings

logger = logging.getLogger(__name__)

class AIVisionService:
    """
    Production AI Image Verification Service.
    
    Runs deep learning inference on farmer ground plantation photography using a
    fine-tuned MobileNetV3-Small neural network.
    
    Outputs:
      - Predicted Class ('Plantation', 'Non-Plantation', 'Unclear / Poor Evidence')
      - Confidence Score (0.0% to 100.0%)
      - Class probability distribution
      - Model metadata and provenance
    """
    
    _model = None
    _device = None
    _class_to_idx = None
    _idx_to_class = None
    
    CLASS_DISPLAY_NAMES = {
        "plantation": "Plantation / Agroforestry",
        "non_plantation": "Non-Plantation (Urban/Barren/Manmade)",
        "unclear_evidence": "Unclear / Poor Evidence (Blur/Dark/Obstructed)"
    }
    
    TRANSFORM = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    @classmethod
    def load_model(cls):
        """Loads and caches the fine-tuned PyTorch model into memory."""
        if cls._model is not None:
            return cls._model
            
        cls._device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        weights_path = settings.ML_MODEL_PATH
        
        if not os.path.exists(weights_path):
            logger.warning(f"ML model weights not found at {weights_path}. Model must be trained.")
            return None
            
        try:
            checkpoint = torch.load(weights_path, map_location=cls._device)
            cls._class_to_idx = checkpoint.get("class_to_idx", {
                "non_plantation": 0,
                "plantation": 1,
                "unclear_evidence": 2
            })
            cls._idx_to_class = {v: k for k, v in cls._class_to_idx.items()}
            
            model = models.mobilenet_v3_small(weights=None)
            in_features = model.classifier[3].in_features
            model.classifier[3] = nn.Linear(in_features, len(cls._class_to_idx))
            model.load_state_dict(checkpoint["model_state_dict"])
            model.to(cls._device)
            model.eval()
            
            cls._model = model
            logger.info(f"AI Vision Model loaded successfully on {cls._device}")
            return cls._model
        except Exception as e:
            logger.error(f"Failed to load AI vision weights: {e}")
            return None

    @classmethod
    def verify_image(cls, image_path: Optional[str]) -> Dict[str, Any]:
        """
        Executes real AI inference on the submitted plantation ground evidence image.
        """
        if not image_path or not os.path.exists(image_path):
            return {
                "is_provided": False,
                "predicted_class": "NO EVIDENCE SUBMITTED",
                "prediction_label": "No Image Provided",
                "confidence_pct": 0.0,
                "class_probabilities": {},
                "model_name": "MobileNetV3-Plantation-v1",
                "model_version": "1.0.0",
                "is_trained": True,
                "feature_evidence": "Ground photograph not uploaded by farmer.",
                "cv_score": 0.0,
                "cv_status": "NOT PROVIDED"
            }

        model = cls.load_model()
        if model is None:
            # Honest notification: model weights missing
            return {
                "is_provided": True,
                "predicted_class": "MODEL_UNAVAILABLE",
                "prediction_label": "Model Weights Missing",
                "confidence_pct": 0.0,
                "class_probabilities": {},
                "model_name": "MobileNetV3-Plantation-v1",
                "model_version": "1.0.0",
                "is_trained": False,
                "feature_evidence": "Neural network model weights file not found on server.",
                "cv_score": 50.0,
                "cv_status": "ML Model Offline"
            }

        try:
            with Image.open(image_path) as pil_img:
                img_rgb = pil_img.convert("RGB")
                tensor = cls.TRANSFORM(img_rgb).unsqueeze(0).to(cls._device)
                
                with torch.no_grad():
                    logits = model(tensor)
                    probs = torch.softmax(logits, dim=1).squeeze(0)
                    
                top_prob, top_idx = probs.max(0)
                pred_key = cls._idx_to_class[top_idx.item()]
                confidence = round(top_prob.item() * 100.0, 1)
                
                prob_dict = {
                    cls._idx_to_class[i]: round(probs[i].item() * 100.0, 1)
                    for i in range(len(cls._idx_to_class))
                }
                
                prediction_label = cls.CLASS_DISPLAY_NAMES.get(pred_key, pred_key)
                
                # Derive CV score for verification formula:
                # If Plantation: score scales with confidence (75 - 98)
                # If Non-Plantation or Unclear: score drops drastically (10 - 40)
                if pred_key == "plantation":
                    cv_score = round(70.0 + (confidence / 100.0) * 28.0, 1)
                    cv_status = f"Plantation Canopy Confirmed ({confidence}% Confidence)"
                    feature_notes = "Deep learning feature extractor identified characteristic agroforestry canopy structure and foliage texture."
                elif pred_key == "non_plantation":
                    cv_score = round(max(10.0, 40.0 - (confidence / 100.0) * 25.0), 1)
                    cv_status = f"Non-Plantation Evidence Detected ({confidence}% Confidence)"
                    feature_notes = "Classifier identified urban, architectural, or barren non-vegetative surfaces."
                else:
                    cv_score = round(max(15.0, 35.0 - (confidence / 100.0) * 15.0), 1)
                    cv_status = f"Poor/Unclear Image Evidence ({confidence}% Confidence)"
                    feature_notes = "Classifier detected severe motion blur, obstruction, or extreme exposure preventing feature extraction."

                return {
                    "is_provided": True,
                    "predicted_class": pred_key,
                    "prediction_label": prediction_label,
                    "confidence_pct": confidence,
                    "class_probabilities": prob_dict,
                    "model_name": "MobileNetV3-Plantation-v1",
                    "model_version": "1.0.0",
                    "is_trained": True,
                    "feature_evidence": feature_notes,
                    "cv_score": cv_score,
                    "cv_status": cv_status
                }
        except Exception as e:
            logger.error(f"Inference error on {image_path}: {e}")
            return {
                "is_provided": True,
                "predicted_class": "ERROR",
                "prediction_label": f"Inference Error: {str(e)}",
                "confidence_pct": 0.0,
                "class_probabilities": {},
                "model_name": "MobileNetV3-Plantation-v1",
                "model_version": "1.0.0",
                "is_trained": True,
                "feature_evidence": f"Failed to process image format: {str(e)}",
                "cv_score": 30.0,
                "cv_status": "Processing Error"
            }
