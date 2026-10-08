import os
import pytest
from app.services.ai.ai_vision_service import AIVisionService
from app.services.ai.cv_service import CVService

def test_ai_vision_model_loading():
    model = AIVisionService.load_model()
    assert model is not None
    assert AIVisionService._class_to_idx is not None
    assert "plantation" in AIVisionService._class_to_idx

def test_ai_vision_missing_image_handling():
    res = AIVisionService.verify_image(None)
    assert res["is_provided"] is False
    assert res["predicted_class"] == "NO EVIDENCE SUBMITTED"
    assert res["confidence_pct"] == 0.0

def test_ai_vision_inference_on_plantation_sample():
    sample_path = os.path.join(
        os.path.dirname(__file__), "..", "ml", "dataset", "val", "plantation", "plant_val_000.jpg"
    )
    if os.path.exists(sample_path):
        res = AIVisionService.verify_image(sample_path)
        assert res["is_provided"] is True
        assert res["predicted_class"] == "plantation"
        assert res["confidence_pct"] >= 80.0
        assert res["model_name"] == "MobileNetV3-Plantation-v1"
        assert res["model_version"] == "1.0.0"

def test_ai_vision_inference_on_non_plantation_sample():
    sample_path = os.path.join(
        os.path.dirname(__file__), "..", "ml", "dataset", "val", "non_plantation", "nonplant_val_000.jpg"
    )
    if os.path.exists(sample_path):
        res = AIVisionService.verify_image(sample_path)
        assert res["is_provided"] is True
        assert res["predicted_class"] == "non_plantation"
        assert res["cv_score"] < 45.0

def test_cv_service_wrapper_integration():
    sample_path = os.path.join(
        os.path.dirname(__file__), "..", "ml", "dataset", "val", "plantation", "plant_val_001.jpg"
    )
    if os.path.exists(sample_path):
        res = CVService.analyze_image(sample_path)
        assert "image_quality_score" in res
        assert "cv_score" in res
        assert "predicted_class" in res
        assert res["predicted_class"] == "plantation"
        assert "confidence_pct" in res
        assert res["confidence_pct"] > 50.0
