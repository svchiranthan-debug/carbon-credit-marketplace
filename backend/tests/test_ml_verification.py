"""Task 4: ML ground-photo classifier — model contract, input validation, failure handling.

Every test here runs the REAL model (marker below). Accuracy checks use the held-out real
test photos built by ml/build_real_dataset.py and are skipped if that folder is absent.
Synthetic images are used only for input-format checks.
"""
import io
import json
import os

import pytest
from PIL import Image

from app.config import settings
from app.services.ai.ai_vision_service import AIVisionService, EXPECTED_CLASSES, validate_image_file
from app.services.ai.cv_service import CVService
from conftest import synthetic_image_bytes

pytestmark = pytest.mark.real_model
REAL_TEST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml", "dataset_real", "test")


@pytest.fixture
def tmpimg(tmp_path):
    def make(data: bytes, name="img.jpg"):
        p = tmp_path / name
        p.write_bytes(data)
        return str(p)
    return make


def test_model_loads_and_matches_metadata():
    assert AIVisionService.load_model() is not None, AIVisionService._load_error
    assert set(AIVisionService._idx_to_class.values()) == set(EXPECTED_CLASSES)
    meta = json.load(open(settings.ML_METADATA_PATH))
    assert meta["class_to_idx"] == {v: k for k, v in AIVisionService._idx_to_class.items()}
    assert "real photographs" in meta["training_data"].lower()
    assert "not been measured" in meta["validation_note"].lower(), "metadata must state the plantation-photo gap"
    assert meta["test_metrics"]["accuracy"] > 0.9


@pytest.mark.skipif(not os.path.isdir(REAL_TEST_DIR), reason="run ml/build_real_dataset.py to enable")
def test_inference_on_held_out_real_photos():
    correct = total = 0
    for cls in EXPECTED_CLASSES:
        files = sorted(os.listdir(os.path.join(REAL_TEST_DIR, cls)))[:25]
        for name in files:
            res = AIVisionService.verify_image(os.path.join(REAL_TEST_DIR, cls, name))
            assert res["available"] and abs(sum(res["class_probabilities"].values()) - 100.0) < 0.5
            correct += res["predicted_class"] == cls
            total += 1
    assert correct / total >= 0.9, f"{correct}/{total}"


def test_inference_output_contract(tmpimg):
    res = AIVisionService.verify_image(tmpimg(synthetic_image_bytes("plantation", 11)))
    assert res["available"] and res["predicted_class"] in EXPECTED_CLASSES
    assert 0 <= res["confidence_pct"] <= 100 and res["cv_score"] is not None
    assert res["model_version"] == "2.0.0"


def test_score_mapping_is_deterministic():
    assert AIVisionService.score_from_prediction("plantation", 100.0)[0] == 98.0
    assert AIVisionService.score_from_prediction("plantation", 0.0)[0] == 70.0
    assert AIVisionService.score_from_prediction("non_plantation", 100.0)[0] == 15.0
    assert AIVisionService.score_from_prediction("unclear_evidence", 100.0)[0] == 20.0


@pytest.mark.parametrize("data,expect", [
    (b"", "empty"),
    (b"this is not an image", "could not be decoded"),
])
def test_invalid_files_rejected(tmpimg, data, expect):
    ok, reason, _ = validate_image_file(tmpimg(data))
    assert not ok and expect in reason
    res = CVService.analyze_image(tmpimg(data, "x.jpg"))
    assert res["available"] is False and res["cv_score"] is None and res["image_quality_score"] is None


def test_too_small_and_missing_images(tmpimg):
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), (0, 128, 0)).save(buf, "PNG")
    ok, reason, _ = validate_image_file(tmpimg(buf.getvalue(), "tiny.png"))
    assert not ok and "too small" in reason
    ok, reason, _ = validate_image_file("/definitely/missing.jpg")
    assert not ok
    res = CVService.analyze_image(None)
    assert res["cv_score"] is None and res["cv_detection_status"] == "NOT PROVIDED"


def test_grayscale_and_rgba_inputs_are_converted(tmpimg):
    for mode in ("L", "RGBA"):
        buf = io.BytesIO()
        Image.open(io.BytesIO(synthetic_image_bytes("plantation", 4))).convert(mode).save(buf, "PNG")
        res = AIVisionService.verify_image(tmpimg(buf.getvalue(), f"m_{mode}.png"))
        assert res["available"], res["reason"]


def test_missing_model_returns_unavailable_not_default(tmpimg, monkeypatch):
    monkeypatch.setattr(AIVisionService, "_model", None)
    monkeypatch.setattr(settings, "ML_MODEL_PATH", "/nonexistent/model.pt")
    res = AIVisionService.verify_image(tmpimg(synthetic_image_bytes("plantation", 2)))
    assert res["available"] is False
    assert res["cv_score"] is None and res["confidence_pct"] is None
    assert "Model weights not found" in res["reason"]
    monkeypatch.setattr(AIVisionService, "_model", None)  # force reload with real path afterwards
