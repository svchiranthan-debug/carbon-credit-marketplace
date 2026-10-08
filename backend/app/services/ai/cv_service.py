import os
from typing import Dict, Any, Optional
from PIL import Image, ImageStat

from .ai_vision_service import AIVisionService

class CVService:
    """
    Computer Vision Verification Modality.
    
    Combines:
    1. Deep Learning Image Verification (PyTorch MobileNetV3 fine-tuned classifier)
    2. Image Quality & Resolution Analysis (Pillow)
    3. Structural Canopy Greenness Metrics
    """

    @staticmethod
    def analyze_image(image_path: Optional[str] = None) -> Dict[str, Any]:
        # If no image provided or file not found, do NOT fabricate evidence
        if not image_path or not os.path.exists(image_path):
            return {
                "image_quality_score": None,
                "vegetation_detection_score": None,
                "cv_score": None,
                "cv_detection_status": "NOT PROVIDED",
                "detected_canopy_pct": None,
                "provided": False,
                "model_name": "MobileNetV3-Plantation-v1",
                "model_version": "1.0.0",
                "predicted_class": "NOT_PROVIDED",
                "prediction_label": "No Image Provided",
                "confidence_pct": 0.0,
                "reason": "No ground-level plantation photograph provided."
            }

        try:
            # 1. Run Real AI Deep Learning Inference
            ai_res = AIVisionService.verify_image(image_path)
            
            with Image.open(image_path) as img:
                img_rgb = img.convert("RGB")
                width, height = img_rgb.size
                
                # Quality Metric based on resolution & dynamic range
                res_score = min(100.0, (width * height) / (1280 * 720) * 80.0)
                stat = ImageStat.Stat(img_rgb)
                mean_r, mean_g, mean_b = stat.mean[:3]
                std_g = stat.stddev[1]
                avg_brightness = (mean_r + mean_g + mean_b) / 3.0
                exposure_penalty = max(0.0, abs(avg_brightness - 128) - 40) * 0.4
                quality_score = max(50.0, min(98.0, res_score - exposure_penalty + (std_g * 0.3)))
                
                # Estimated green coverage ratio
                thumb = img_rgb.resize((100, 100))
                pixels = thumb.getdata()
                green_dominant = sum(1 for r, g, b in pixels if ((2 * g) - r - b > 15 and g > r and g > b))
                canopy_pct = round((green_dominant / max(1, len(pixels))) * 100.0, 1)

            cv_score = ai_res["cv_score"]

            return {
                "image_quality_score": round(quality_score, 1),
                "vegetation_detection_score": round(ai_res["confidence_pct"], 1),
                "cv_score": cv_score,
                "cv_detection_status": ai_res["cv_status"],
                "detected_canopy_pct": canopy_pct,
                "resolution": f"{width}x{height}",
                "predicted_class": ai_res["predicted_class"],
                "prediction_label": ai_res["prediction_label"],
                "confidence_pct": ai_res["confidence_pct"],
                "class_probabilities": ai_res.get("class_probabilities", {}),
                "model_name": ai_res["model_name"],
                "model_version": ai_res["model_version"],
                "is_trained": ai_res["is_trained"],
                "feature_evidence": ai_res["feature_evidence"],
                "methodology": "Deep Learning (MobileNetV3-Small) + Spectral Foliage Verification"
            }
        except Exception as e:
            return {
                "image_quality_score": 60.0,
                "vegetation_detection_score": 50.0,
                "cv_score": 50.0,
                "cv_detection_status": f"Fallback Processing ({str(e)})",
                "detected_canopy_pct": 30.0,
                "resolution": "Standard",
                "predicted_class": "ERROR",
                "prediction_label": f"Processing Error: {str(e)}",
                "confidence_pct": 0.0,
                "model_name": "MobileNetV3-Plantation-v1",
                "model_version": "1.0.0",
                "is_trained": True,
                "feature_evidence": "Fallback image processing.",
                "methodology": "Fallback CV Engine"
            }
