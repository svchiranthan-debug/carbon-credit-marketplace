"""
Computer-vision modality: ground photograph analysis.

Combines the MobileNetV3 classifier (which produces the CV score used in the
verification formula) with two descriptive image measurements computed directly from
the pixels: an image-quality indicator and a green-dominant pixel share. The descriptive
measurements are reported for transparency only; they do not change the CV score.

If no valid photo is provided or the model cannot run, every value is null and the
modality is marked unavailable. Nothing is defaulted.
"""
from typing import Any, Dict, Optional

from PIL import Image, ImageStat

from .ai_vision_service import AIVisionService


def _describe_image(image_path: str) -> Dict[str, Any]:
    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        width, height = rgb.size
        stat = ImageStat.Stat(rgb)
        mean_r, mean_g, mean_b = stat.mean[:3]
        std_g = stat.stddev[1]
        brightness = (mean_r + mean_g + mean_b) / 3.0
        resolution_component = min(100.0, (width * height) / (1280 * 720) * 80.0)
        exposure_penalty = max(0.0, abs(brightness - 128) - 40) * 0.4
        quality = max(0.0, min(100.0, resolution_component - exposure_penalty + std_g * 0.3))

        thumb = rgb.resize((100, 100))
        pixels = list(thumb.getdata())
        green = sum(1 for r, g, b in pixels if (2 * g - r - b) > 15 and g > r and g > b)
    return {
        "image_quality_score": round(quality, 1),
        "detected_canopy_pct": round(green / len(pixels) * 100.0, 1),
        "resolution": f"{width}x{height}",
    }


class CVService:

    @staticmethod
    def analyze_image(image_path: Optional[str] = None) -> Dict[str, Any]:
        ai = AIVisionService.verify_image(image_path)
        base = {
            "available": ai["available"],
            "reason": ai.get("reason"),
            "predicted_class": ai.get("predicted_class"),
            "prediction_label": ai.get("prediction_label"),
            "confidence_pct": ai.get("confidence_pct"),
            "class_probabilities": ai.get("class_probabilities", {}),
            "model_name": ai.get("model_name"),
            "model_version": ai.get("model_version"),
            "training_data": ai.get("training_data"),
        }
        if not ai["available"]:
            return {
                **base,
                "image_quality_score": None,
                "vegetation_detection_score": None,
                "cv_score": None,
                "cv_detection_status": "NOT PROVIDED" if not image_path else "NOT AVAILABLE",
                "detected_canopy_pct": None,
            }

        desc = _describe_image(image_path)
        return {
            **base,
            **desc,
            # Probability (%) the classifier assigns to the plantation class.
            "vegetation_detection_score": ai["class_probabilities"].get("plantation"),
            "cv_score": ai["cv_score"],
            "cv_detection_status": ai["cv_status"],
            "feature_evidence": ai.get("feature_evidence"),
            "methodology": "MobileNetV3-Small classifier (CV score) + descriptive pixel statistics",
        }
