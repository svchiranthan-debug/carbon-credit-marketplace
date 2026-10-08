import os
import io
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.plantation import Plantation, PlantationStatus
from app.models.verification import Verification, VerificationDecision
from app.models.credit import Credit, CreditStatus
from app.models.user import User

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
        "organization": "Test Org"
    })
    res = client.post("/api/auth/login", json={
        "email": email,
        "password": "Password123!",
        "role": role
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_auditor_approval_auto_issues_available_credit_to_marketplace(db_session):
    """
    End-to-end regression test:
    Farmer plantation -> multimodal verification -> Auditor approves ->
    Carbon asset is automatically generated/issued -> status becomes AVAILABLE ->
    Asset is persisted in DB -> Buyer Marketplace API returns asset -> Buyer sees it.
    """
    uid = uuid.uuid4().hex[:6]
    farmer_email = f"farmer_flow_{uid}@agri.test"
    auditor_email = f"auditor_flow_{uid}@audit.test"
    buyer_email = f"buyer_flow_{uid}@corp.test"

    farmer_headers = _get_auth_headers(farmer_email, "FARMER", "Gowda Farmer")
    auditor_headers = _get_auth_headers(auditor_email, "AUDITOR", "Dr. Auditor")
    buyer_headers = _get_auth_headers(buyer_email, "BUYER", "Acme ESG Corp")

    # 1. Create plantation with full evidence
    p_res = client.post("/api/plantations", json={
        "name": f"Green Valley Canopy #{uid}",
        "farmer_name": "Gowda Farmer",
        "location": "Shimoga, Karnataka",
        "latitude": 13.9299,
        "longitude": 75.5681,
        "area_hectares": 3.0,
        "plantation_age_years": 5.0,
        "tree_count": 500,
        "tree_species": "Teak, Silver Oak",
        "soil_soc_pct": 2.1,
        "soil_depth_cm": 35.0,
        "soil_type": "Red Sandy Loam",
        "plantation_type": "Agroforestry",
        "sustainable_practice": "Drip Irrigation"
    }, headers=farmer_headers)
    assert p_res.status_code in [200, 201]
    plantation_id = p_res.json()["id"]

    # 2. Upload photo evidence
    sample_img = os.path.join(
        os.path.dirname(__file__), "..", "ml", "dataset", "train", "plantation", "plant_train_000.jpg"
    )
    if os.path.exists(sample_img):
        with open(sample_img, "rb") as f:
            img_bytes = f.read()
    else:
        img_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB"

    upload_res = client.post(
        f"/api/plantations/{plantation_id}/image",
        files={"file": ("field_canopy.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        headers=farmer_headers
    )
    assert upload_res.status_code == 200

    # 3. Run multi-modal verification
    v_res = client.post(f"/api/plantations/{plantation_id}/verify", headers=farmer_headers)
    assert v_res.status_code == 200
    v_data = v_res.json()
    verification_id = v_data["id"]

    # 4. Auditor reviews and approves
    dec_res = client.post(
        f"/api/admin/verifications/{verification_id}/decision",
        json={"decision": "APPROVED", "notes": "Auditor ground truth verified. High biomass confirmed."},
        headers=auditor_headers
    )
    assert dec_res.status_code == 200, f"Approval failed: {dec_res.text}"
    assert dec_res.json()["decision"] == "APPROVED"

    # 5. Verify direct database persistence
    db_session.expire_all()
    credit_row = db_session.query(Credit).filter(Credit.plantation_id == plantation_id).first()
    assert credit_row is not None, "BUG: CarbonAsset/Credit row was NOT created in DB after auditor approval!"
    assert credit_row.plantation_id == plantation_id
    assert credit_row.status == CreditStatus.AVAILABLE.value, f"Expected AVAILABLE, got {credit_row.status}"
    assert credit_row.carbon_quantity_tco2e > 0
    assert credit_row.is_retired == 0
    assert credit_row.blockchain_tx_hash is not None, "Blockchain registration reference missing!"

    # 6. Check Buyer Marketplace API visibility
    marketplace_res = client.get("/api/marketplace/credits", headers=buyer_headers)
    assert marketplace_res.status_code == 200
    marketplace_credits = marketplace_res.json()
    matched = [c for c in marketplace_credits if c["id"] == credit_row.id]
    assert len(matched) == 1, f"Credit {credit_row.id} not visible in Buyer Marketplace API!"
    assert matched[0]["status"] == "AVAILABLE"
    assert matched[0]["plantation_name"] == f"Green Valley Canopy #{uid}"
    assert matched[0]["carbon_quantity_tco2e"] == credit_row.carbon_quantity_tco2e


def test_boundary_only_incomplete_evidence_cannot_issue_asset(db_session):
    """
    Test that an incomplete / boundary-only plantation CANNOT be approved and
    cannot create an available carbon asset.
    """
    uid = uuid.uuid4().hex[:6]
    farmer_headers = _get_auth_headers(f"farmer_inc_{uid}@test.com", "FARMER")
    auditor_headers = _get_auth_headers(f"auditor_inc_{uid}@test.com", "AUDITOR")

    # Create plantation WITHOUT image and WITHOUT soil SOC
    p_res = client.post("/api/plantations", json={
        "name": f"Boundary Only Plot #{uid}",
        "farmer_name": "Incomplete Farmer",
        "location": "Hassan, Karnataka",
        "latitude": 13.0068,
        "longitude": 76.0996,
        "area_hectares": 1.5,
        "plantation_age_years": 3.0,
        "tree_count": 200,
        "tree_species": "Teak",
        "plantation_type": "Agroforestry",
        "soil_soc_pct": None  # Missing SOC
    }, headers=farmer_headers)
    assert p_res.status_code in [200, 201], f"Plantation creation failed: {p_res.text}"
    plot_id = p_res.json()["id"]

    # Trigger verification -> should flag missing evidence / REVIEW
    v_res = client.post(f"/api/plantations/{plot_id}/verify", headers=farmer_headers)
    assert v_res.status_code == 200
    v_data = v_res.json()
    assert v_data["decision"] in ["REVIEW", "REJECTED", "PENDING"]

    # Auditor attempts to approve incomplete plantation -> MUST BE BLOCKED (HTTP 400)
    dec_res = client.post(
        f"/api/admin/verifications/{v_data['id']}/decision",
        json={"decision": "APPROVED", "notes": "Premature attempt to approve incomplete evidence"},
        headers=auditor_headers
    )
    assert dec_res.status_code == 400, "Auditor should not be allowed to approve incomplete evidence!"

    # Ensure no credit row exists
    db_session.expire_all()
    credit_row = db_session.query(Credit).filter(Credit.plantation_id == plot_id).first()
    assert credit_row is None, "Incomplete evidence plantation must NOT have a CarbonAsset created!"


def test_rejected_verification_does_not_create_available_asset(db_session):
    """
    Test that auditor rejection does NOT generate an available carbon asset.
    """
    uid = uuid.uuid4().hex[:6]
    farmer_headers = _get_auth_headers(f"farmer_rej_{uid}@test.com", "FARMER")
    auditor_headers = _get_auth_headers(f"auditor_rej_{uid}@test.com", "AUDITOR")

    p_res = client.post("/api/plantations", json={
        "name": f"Rejected Plot #{uid}",
        "farmer_name": "Farmer Rej",
        "location": "Mysuru, Karnataka",
        "latitude": 12.2958,
        "longitude": 76.6394,
        "area_hectares": 2.0,
        "plantation_age_years": 2.0,
        "tree_count": 300,
        "tree_species": "Neem",
        "plantation_type": "Agroforestry",
        "soil_soc_pct": 1.5
    }, headers=farmer_headers)
    assert p_res.status_code in [200, 201], f"Creation failed: {p_res.text}"
    plot_id = p_res.json()["id"]

    v_res = client.post(f"/api/plantations/{plot_id}/verify", headers=farmer_headers)
    v_data = v_res.json()

    dec_res = client.post(
        f"/api/admin/verifications/{v_data['id']}/decision",
        json={"decision": "REJECTED", "notes": "Failed canopy density check."},
        headers=auditor_headers
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["decision"] == "REJECTED"

    db_session.expire_all()
    credit_row = db_session.query(Credit).filter(Credit.plantation_id == plot_id).first()
    assert credit_row is None, "Rejected plantation must not produce a carbon credit!"


def test_acquired_asset_disappears_from_available_and_retire_lifecycle(db_session):
    """
    Test:
    1. Acquired asset disappears from AVAILABLE marketplace.
    2. Acquired asset remains visible when status_filter=ALL.
    3. Asset can be retired.
    4. Retired asset cannot be purchased again.
    """
    uid = uuid.uuid4().hex[:6]
    farmer_headers = _get_auth_headers(f"farmer_acq_{uid}@agri.test", "FARMER")
    auditor_headers = _get_auth_headers(f"auditor_acq_{uid}@audit.test", "AUDITOR")
    buyer_headers = _get_auth_headers(f"buyer_acq_{uid}@corp.test", "BUYER")

    p_res = client.post("/api/plantations", json={
        "name": f"Plot To Acquire #{uid}",
        "farmer_name": "Farmer Acq",
        "location": "Belagavi, Karnataka",
        "latitude": 15.8497,
        "longitude": 74.4977,
        "area_hectares": 2.5,
        "plantation_age_years": 4.0,
        "tree_count": 400,
        "tree_species": "Silver Oak",
        "soil_soc_pct": 1.8,
        "plantation_type": "Agroforestry",
        "sustainable_practice": "Biochar Application"
    }, headers=farmer_headers)
    assert p_res.status_code in [200, 201], f"Creation failed: {p_res.text}"
    plot_id = p_res.json()["id"]

    # Upload photo
    upload_res = client.post(
        f"/api/plantations/{plot_id}/image",
        files={"file": ("field.jpg", io.BytesIO(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB"), "image/jpeg")},
        headers=farmer_headers
    )
    assert upload_res.status_code == 200

    v_res = client.post(f"/api/plantations/{plot_id}/verify", headers=farmer_headers)
    v_data = v_res.json()

    dec_res = client.post(
        f"/api/admin/verifications/{v_data['id']}/decision",
        json={"decision": "APPROVED", "notes": "Approved for acquisition test"},
        headers=auditor_headers
    )
    assert dec_res.status_code == 200, f"Decision failed: {dec_res.text}"

    db_session.expire_all()
    credit = db_session.query(Credit).filter(Credit.plantation_id == plot_id).first()
    assert credit is not None
    credit_id = credit.id

    # Confirm it is in AVAILABLE marketplace
    available_res = client.get("/api/marketplace/credits", headers=buyer_headers)
    assert any(c["id"] == credit_id for c in available_res.json())

    # Buyer acquires/purchases asset
    buy_res = client.post(f"/api/marketplace/credits/{credit_id}/purchase", headers=buyer_headers, json={})
    assert buy_res.status_code == 201

    # Acquired asset MUST disappear from AVAILABLE marketplace
    after_buy_res = client.get("/api/marketplace/credits", headers=buyer_headers)
    assert not any(c["id"] == credit_id for c in after_buy_res.json()), "Acquired asset still visible in AVAILABLE marketplace!"

    # Acquired asset MUST still be returned when status_filter=ALL
    all_res = client.get("/api/marketplace/credits?status_filter=ALL", headers=buyer_headers)
    assert any(c["id"] == credit_id for c in all_res.json())

    # Buyer retires asset
    retire_res = client.post(f"/api/marketplace/credits/{credit_id}/retire", headers=buyer_headers)
    assert retire_res.status_code == 200
    assert retire_res.json()["status"] == "RETIRED"

    # Retired asset CANNOT be purchased again
    re_purchase_res = client.post(f"/api/marketplace/credits/{credit_id}/purchase", headers=buyer_headers, json={})
    assert re_purchase_res.status_code == 400, "Retired asset should not be purchasable!"


def test_farmer_ownership_isolation(db_session):
    """
    Test that farmer ownership isolation remains intact:
    Farmer A sees their own credit in /marketplace/my-credits.
    Farmer B does NOT see Farmer A's credit.
    """
    uid = uuid.uuid4().hex[:6]
    farmer_a_headers = _get_auth_headers(f"farmer_a_{uid}@iso.test", "FARMER", "Farmer A")
    farmer_b_headers = _get_auth_headers(f"farmer_b_{uid}@iso.test", "FARMER", "Farmer B")
    auditor_headers = _get_auth_headers(f"auditor_iso_{uid}@audit.test", "AUDITOR")

    p_res = client.post("/api/plantations", json={
        "name": f"Farmer A Plot #{uid}",
        "farmer_name": "Farmer A",
        "location": "Udupi, Karnataka",
        "latitude": 13.3409,
        "longitude": 74.7421,
        "area_hectares": 2.0,
        "plantation_age_years": 4.0,
        "tree_count": 350,
        "tree_species": "Teak",
        "plantation_type": "Agroforestry",
        "soil_soc_pct": 2.0
    }, headers=farmer_a_headers)
    assert p_res.status_code in [200, 201], f"Creation failed: {p_res.text}"
    plot_id = p_res.json()["id"]

    client.post(
        f"/api/plantations/{plot_id}/image",
        files={"file": ("field.jpg", io.BytesIO(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB"), "image/jpeg")},
        headers=farmer_a_headers
    )

    v_res = client.post(f"/api/plantations/{plot_id}/verify", headers=farmer_a_headers)
    v_data = v_res.json()

    client.post(
        f"/api/admin/verifications/{v_data['id']}/decision",
        json={"decision": "APPROVED", "notes": "Approved for isolation test"},
        headers=auditor_headers
    )

    db_session.expire_all()
    credit = db_session.query(Credit).filter(Credit.plantation_id == plot_id).first()
    assert credit is not None

    # Farmer A checks my-credits -> should see it
    a_credits_res = client.get("/api/marketplace/my-credits", headers=farmer_a_headers)
    assert any(c["id"] == credit.id for c in a_credits_res.json())

    # Farmer B checks my-credits -> should NOT see it
    b_credits_res = client.get("/api/marketplace/my-credits", headers=farmer_b_headers)
    assert not any(c["id"] == credit.id for c in b_credits_res.json()), "Farmer B leaked Farmer A's credit!"
