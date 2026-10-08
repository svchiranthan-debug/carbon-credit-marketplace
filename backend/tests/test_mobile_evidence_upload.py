import os
import io
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.plantation import Plantation

client = TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _get_auth_headers(email: str, role: str, name: str = "Test User"):
    client.post("/api/auth/register", json={
        "full_name": name,
        "email": email,
        "password": "Password123!",
        "role": role,
        "organization": "Test Collective"
    })
    res = client.post("/api/auth/login", json={
        "email": email,
        "password": "Password123!",
        "role": role
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_mobile_evidence_image_upload_and_cv_verification(db_session):
    """
    Validates that images captured from the mobile camera and sent via
    multipart/form-data to /api/plantations/{id}/image are correctly:
    1. Saved in backend /uploads storage.
    2. Linked to the plantation record.
    3. Processed by the deep learning CV verification model.
    """
    uid = uuid.uuid4().hex[:6]
    farmer_headers = _get_auth_headers(f"farmer_cam_{uid}@agri.test", "FARMER", "Mobile Farmer")

    # 1. Register plantation
    p_res = client.post("/api/plantations", json={
        "name": f"Mobile Ground Evidence Plot #{uid}",
        "farmer_name": "Mobile Farmer",
        "location": "Chikkamagaluru, Karnataka",
        "latitude": 13.3161,
        "longitude": 75.7720,
        "area_hectares": 2.0,
        "plantation_age_years": 3.5,
        "tree_count": 400,
        "tree_species": "Silver Oak, Coffee",
        "soil_soc_pct": 2.0,
        "plantation_type": "Agroforestry"
    }, headers=farmer_headers)
    assert p_res.status_code in [200, 201]
    plot_id = p_res.json()["id"]

    # 2. Upload captured photo as multipart/form-data
    sample_img = os.path.join(
        os.path.dirname(__file__), "..", "ml", "dataset", "train", "plantation", "plant_train_000.jpg"
    )
    if os.path.exists(sample_img):
        with open(sample_img, "rb") as f:
            img_bytes = f.read()
    else:
        img_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB"

    upload_res = client.post(
        f"/api/plantations/{plot_id}/image",
        files={"file": (f"evidence_{uid}.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=farmer_headers
    )
    assert upload_res.status_code == 200
    up_data = upload_res.json()
    assert "image_url" in up_data
    assert up_data["image_url"].startswith("/uploads/")

    # 3. Check database record
    db_session.expire_all()
    plot = db_session.query(Plantation).filter(Plantation.id == plot_id).first()
    assert plot is not None
    assert plot.image_url == up_data["image_url"]

    # 4. Trigger verification and verify CV engine evaluates the uploaded photo
    v_res = client.post(f"/api/plantations/{plot_id}/verify", headers=farmer_headers)
    assert v_res.status_code == 200
    v_data = v_res.json()
    assert v_data["cv_score"] is not None
    assert v_data["cv_score"] > 0
    assert v_data["decision"] in ["APPROVED", "REVIEW"]

def test_invalid_image_format_rejected(db_session):
    """
    Validates that invalid non-image formats are rejected with HTTP 400.
    """
    uid = uuid.uuid4().hex[:6]
    farmer_headers = _get_auth_headers(f"farmer_invalid_{uid}@agri.test", "FARMER")

    p_res = client.post("/api/plantations", json={
        "name": f"Invalid Evidence Plot #{uid}",
        "farmer_name": "Farmer",
        "location": "Shimoga, Karnataka",
        "latitude": 13.9299,
        "longitude": 75.5681,
        "area_hectares": 1.0,
        "plantation_age_years": 2.0,
        "tree_count": 150,
        "tree_species": "Teak",
        "soil_soc_pct": 1.5,
        "plantation_type": "Agroforestry"
    }, headers=farmer_headers)
    plot_id = p_res.json()["id"]

    bad_upload = client.post(
        f"/api/plantations/{plot_id}/image",
        files={"file": ("malicious.exe", io.BytesIO(b"MZ\x90\x00"), "application/x-msdownload")},
        headers=farmer_headers
    )
    assert bad_upload.status_code == 400
    assert "Invalid image format" in bad_upload.text

def test_mobile_verification_run_endpoint(db_session):
    """
    Validates mobile workflow calling:
    1. POST /api/plantations/{id}/evidence
    2. POST /api/verification/run
    """
    uid = uuid.uuid4().hex[:6]
    farmer_headers = _get_auth_headers(f"farmer_run_{uid}@agri.test", "FARMER", "Mobile Runner")

    p_res = client.post("/api/plantations", json={
        "name": f"Mobile Direct Run Plot #{uid}",
        "farmer_name": "Mobile Runner",
        "location": "Mandya, Karnataka",
        "latitude": 12.5218,
        "longitude": 76.8951,
        "area_hectares": 1.5,
        "plantation_age_years": 3.0,
        "tree_count": 300,
        "tree_species": "Silver Oak, Teak",
        "plantation_type": "Agroforestry"
    }, headers=farmer_headers)
    assert p_res.status_code in [200, 201]
    plot_id = p_res.json()["id"]

    # Test POST /api/plantations/{id}/evidence
    sample_img = os.path.join(
        os.path.dirname(__file__), "..", "ml", "dataset", "train", "plantation", "plant_train_000.jpg"
    )
    if os.path.exists(sample_img):
        with open(sample_img, "rb") as f:
            img_bytes = f.read()
    else:
        img_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB"

    ev_res = client.post(
        f"/api/plantations/{plot_id}/evidence",
        files={"file": (f"evidence_{uid}.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=farmer_headers
    )
    assert ev_res.status_code == 200
    img_path = ev_res.json()["image_url"]

    # Test POST /api/verification/run with payload
    run_res = client.post(
        "/api/verification/run",
        json={
            "plantation_id": plot_id,
            "ground_image_path": img_path,
            "soc_sample_pct": 1.75
        },
        headers=farmer_headers
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["plantation_id"] == plot_id
    assert run_data["soc_pct"] == 1.75
    assert run_data["decision"] in ["APPROVED", "REVIEW"]

