import os
import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.ai.satellite_client import SatelliteClient
from app.services.ai.ndvi_service import NDVIService
from app.services.ai.ai_vision_service import AIVisionService
from app.services.ai.cv_service import CVService
from app.services.risk_engine import RiskEngine
from app.models.plantation import Plantation

client = TestClient(app)

# -------------------------------------------------------------
# 1. SATELLITE / NDVI MODALITY TESTS
# -------------------------------------------------------------
def test_satellite_bounding_box_and_calculation():
    # Centroid bounding box
    bbox = SatelliteClient.get_bounding_box(12.52, 76.89)
    assert len(bbox) == 4
    assert bbox[0] < bbox[2]
    assert bbox[1] < bbox[3]

    # Full NDVI analysis
    res = NDVIService.analyze_ndvi(
        latitude=12.52,
        longitude=76.89,
        area_hectares=2.5,
        tree_count=500,
        plantation_age_years=4.0
    )
    assert "mean_ndvi" in res
    assert "min_ndvi" in res
    assert "max_ndvi" in res
    assert "vegetation_coverage_pct" in res
    assert "is_real_satellite" in res
    assert res["provenance_type"] in ["REAL SATELLITE DATA", "DEMO/PROTOTYPE DATA"]
    assert "band_breakdown" in res
    assert res["ndvi_score"] > 0

def test_satellite_fallback_labeling():
    fallback = SatelliteClient._generate_prototype_fallback(
        12.0, 76.0, [75.9, 11.9, 76.1, 12.1], "API Offline Test"
    )
    assert fallback["is_real_satellite"] is False
    assert fallback["provenance_type"] == "DEMO/PROTOTYPE DATA"
    assert "SIMULATION" in fallback["data_source"]

# -------------------------------------------------------------
# 2. AI VISION MODALITY TESTS
# -------------------------------------------------------------
def test_ai_vision_model_inference():
    model = AIVisionService.load_model()
    assert model is not None

    sample_plant = os.path.join(
        os.path.dirname(__file__), "..", "ml", "dataset", "val", "plantation", "plant_val_000.jpg"
    )
    sample_nonplant = os.path.join(
        os.path.dirname(__file__), "..", "ml", "dataset", "val", "non_plantation", "nonplant_val_000.jpg"
    )

    if os.path.exists(sample_plant):
        res_plant = AIVisionService.verify_image(sample_plant)
        assert res_plant["predicted_class"] == "plantation"
        assert res_plant["confidence_pct"] >= 70.0
        assert res_plant["cv_score"] >= 75.0

    if os.path.exists(sample_nonplant):
        res_nonplant = AIVisionService.verify_image(sample_nonplant)
        assert res_nonplant["predicted_class"] == "non_plantation"
        assert res_nonplant["cv_score"] < 40.0

# -------------------------------------------------------------
# 3. RISK & FRAUD DETECTION ENGINE TESTS
# -------------------------------------------------------------
def test_risk_engine_scoring_and_escalation():
    # Low Risk
    p_good = Plantation(
        id=201, farmer_id=1, name="Clean Farm", area_hectares=2.0, tree_count=500,
        soil_soc_pct=1.8, soil_type="Loam", latitude=12.5, longitude=76.8
    )
    r_low = RiskEngine.evaluate_risk(
        p_good,
        {"mean_ndvi": 0.72, "ndvi_score": 82.0},
        {"predicted_class": "plantation", "confidence_pct": 95.0, "cv_score": 92.0},
        {"soc_pct": 1.8, "soc_score": 75.0}
    )
    assert r_low["risk_level"] == "LOW"
    assert r_low["risk_score"] <= 30
    assert r_low["requires_auditor_review"] is False

    # High Risk
    p_bad = Plantation(
        id=202, farmer_id=1, name="Fraud Claim", area_hectares=1.0, tree_count=300,
        soil_soc_pct=1.2, soil_type="Loam", latitude=13.0, longitude=77.5
    )
    r_high = RiskEngine.evaluate_risk(
        p_bad,
        {"mean_ndvi": 0.75, "ndvi_score": 85.0},
        {"predicted_class": "non_plantation", "confidence_pct": 99.0, "cv_score": 15.0},
        {"soc_pct": 1.2, "soc_score": 60.0}
    )
    assert r_high["risk_level"] == "HIGH"
    assert r_high["risk_score"] >= 61
    assert r_high["requires_auditor_review"] is True

# -------------------------------------------------------------
# 4. FULL END-TO-END LIFECYCLE VIA FASTAPI
# -------------------------------------------------------------
def test_full_lifecycle_end_to_end():
    # 1. Farmer Registration & Login
    f_email = f"farmer_e2e_{os.getpid()}@carbon.test"
    reg_res = client.post("/api/auth/register", json={
        "full_name": "Ramesh Gowda",
        "email": f_email,
        "password": "Password@123",
        "role": "FARMER"
    })
    assert reg_res.status_code in [200, 201]

    login_res = client.post("/api/auth/login", json={
        "email": f_email,
        "password": "Password@123",
        "role": "FARMER"
    })
    assert login_res.status_code == 200
    farmer_token = login_res.json()["access_token"]
    farmer_headers = {"Authorization": f"Bearer {farmer_token}"}

    # 2. Register Plantation with GPS Boundary & SOC
    create_p_res = client.post("/api/plantations", json={
        "name": "Mandya High-Canopy Agroforest",
        "farmer_name": "Ramesh Gowda",
        "location": "Mandya, Karnataka",
        "latitude": 12.5218,
        "longitude": 76.8951,
        "area_hectares": 2.5,
        "plantation_age_years": 4.0,
        "tree_count": 600,
        "tree_species": "Teak, Silver Oak",
        "soil_soc_pct": 1.95,
        "soil_depth_cm": 40.0,
        "soil_type": "Red Sandy Loam",
        "plantation_type": "Agroforestry",
        "sustainable_practice": "Drip Irrigation"
    }, headers=farmer_headers)
    assert create_p_res.status_code in [200, 201]
    plot_id = create_p_res.json()["id"]

    # 3. Upload Ground Photographic Evidence
    sample_img_path = os.path.join(
        os.path.dirname(__file__), "..", "ml", "dataset", "train", "plantation", "plant_train_000.jpg"
    )
    with open(sample_img_path, "rb") as f:
        img_bytes = f.read()

    upload_res = client.post(
        f"/api/plantations/{plot_id}/image",
        files={"file": ("plantation_field.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=farmer_headers
    )
    assert upload_res.status_code == 200

    # 4. Trigger Multi-Modal Verification
    ver_res = client.post(f"/api/plantations/{plot_id}/verify", headers=farmer_headers)
    assert ver_res.status_code == 200
    v_data = ver_res.json()
    assert v_data["overall_score"] is not None
    assert v_data["decision"] in ["APPROVED", "REVIEW"]
    assert "is_real_satellite" in v_data
    assert "ai_model_name" in v_data
    assert "risk_score" in v_data
    assert "risk_level" in v_data

    # 5. Auditor Reviews and Approves
    a_email = f"auditor_e2e_{os.getpid()}@carbon.test"
    client.post("/api/auth/register", json={
        "full_name": "Lead Auditor",
        "email": a_email,
        "password": "Password@123",
        "role": "AUDITOR"
    })
    a_login = client.post("/api/auth/login", json={
        "email": a_email,
        "password": "Password@123",
        "role": "AUDITOR"
    })
    auditor_token = a_login.json()["access_token"]
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}

    queue_res = client.get("/api/admin/verifications", headers=auditor_headers)
    assert queue_res.status_code == 200

    dec_res = client.post(
        f"/api/admin/verifications/{v_data['id']}/decision",
        json={"decision": "APPROVED", "notes": "Audited via Multi-Modal E2E Test Suite"},
        headers=auditor_headers
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["decision"] == "APPROVED"

    # 6. Carbon Asset Issuance with IPCC Biomass Sequestration
    est_res = client.post(f"/api/plantations/{plot_id}/carbon-estimate", headers=farmer_headers)
    assert est_res.status_code == 200
    assert est_res.json()["estimated_carbon_tco2e"] > 0

    issue_res = client.post(
        f"/api/plantations/{plot_id}/generate-credits",
        json={"price_per_tco2e": 1500.0},
        headers=farmer_headers
    )
    assert issue_res.status_code in [200, 201]
    credit_id = issue_res.json()["id"]

    # 7. Marketplace Listing
    market_res = client.get("/api/marketplace/credits")
    assert market_res.status_code == 200
    active_ids = [c["id"] for c in market_res.json()]
    assert credit_id in active_ids

    # 8. Buyer Registration & Acquisition via Escrow
    b_email = f"buyer_e2e_{os.getpid()}@carbon.test"
    client.post("/api/auth/register", json={
        "full_name": "Tata Steel ESG Desk",
        "email": b_email,
        "password": "Password@123",
        "role": "BUYER"
    })
    b_login = client.post("/api/auth/login", json={
        "email": b_email,
        "password": "Password@123",
        "role": "BUYER"
    })
    buyer_token = b_login.json()["access_token"]
    buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

    buy_res = client.post(
        f"/api/marketplace/credits/{credit_id}/purchase",
        json={"payment_method": "ESCROW_INR"},
        headers=buyer_headers
    )
    assert buy_res.status_code in [200, 201]

    # 9. Irrevocable Offset Retirement
    retire_res = client.post(
        f"/api/marketplace/credits/{credit_id}/retire",
        json={"retirement_beneficiary": "FY2026 Scope-1 Offset Compliance"},
        headers=buyer_headers
    )
    assert retire_res.status_code == 200
    assert retire_res.json()["status"] == "RETIRED"
