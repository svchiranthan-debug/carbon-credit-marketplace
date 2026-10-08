"""Task 11: end-to-end journey over real HTTP (uvicorn in a background thread).

Sequence: farmer registers → submits plantation (boundary only, PENDING) → submits photo,
soil and reported NDVI evidence → verification → REVIEW (reported NDVI) → auditor approves
→ credit issued and listed → buyer purchases → buyer retires → state persists.
All evidence values are SYNTHETIC TEST FIXTURES.
"""
import uuid

import requests

from app.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.credit import Credit
from app.models.transaction import Transaction
from conftest import TEST_NDVI, plantation_payload, synthetic_image_bytes


def _register(base, role):
    email = f"e2e_{role.lower()}_{uuid.uuid4().hex[:6]}@test.example"
    body = {"email": email, "password": "TestPass@123", "full_name": f"E2E {role}", "role": role}
    if role == "AUDITOR":  # auditors are created by an admin, then log in
        admin_tok = requests.post(f"{base}/auth/login", json={"email": "admin@agrocarbon.demo", "password": "Demo@123"}).json()["access_token"]
        r = requests.post(f"{base}/users", headers={"Authorization": f"Bearer {admin_tok}"}, json=body)
        assert r.status_code == 201, r.text
        r = requests.post(f"{base}/auth/login", json={"email": email, "password": "TestPass@123"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = requests.post(f"{base}/auth/register", json=body)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_full_journey_and_failure_cases(api_base):
    B = api_base
    farmer, buyer, auditor = _register(B, "FARMER"), _register(B, "BUYER"), _register(B, "AUDITOR")

    # 1-2. Create plantation and store it
    p = requests.post(f"{B}/plantations", headers=farmer, json=plantation_payload(name="E2E 1-acre areca")).json()
    assert p["status"] == "SUBMITTED"
    assert requests.get(f"{B}/plantations/{p['id']}", headers=farmer).json()["name"] == "E2E 1-acre areca"

    # Incomplete project → PENDING, no credit
    v0 = requests.post(f"{B}/plantations/{p['id']}/verify", headers=farmer).json()
    assert v0["decision"] == "PENDING" and v0["overall_score"] is None
    assert requests.post(f"{B}/plantations/{p['id']}/generate-credits", headers=farmer, json={}).status_code == 409

    # 3. Submit evidence
    up = requests.post(f"{B}/plantations/{p['id']}/image", headers=farmer,
                       files={"file": ("ground.jpg", synthetic_image_bytes("plantation", 17), "image/jpeg")})
    assert up.status_code == 200
    ev = requests.put(f"{B}/plantations/{p['id']}/evidence", headers=farmer,
                      json={"soil_soc_pct": 2.2, "soil_depth_cm": 30, "soil_type": "Red Soil", **TEST_NDVI})
    assert ev.status_code == 200

    # 4-5. Run verification → decision with reasons
    v1 = requests.post(f"{B}/plantations/{p['id']}/verify", headers=farmer).json()
    assert v1["overall_score"] is not None and v1["decision"] == "REVIEW"
    assert v1["decision_reasons"]

    # 6. Approve only when requirements are satisfied (auditor confirms reported NDVI)
    r = requests.post(f"{B}/admin/verifications/{v1['id']}/decision", headers=auditor,
                      json={"decision": "APPROVED", "notes": "E2E: reported NDVI cross-checked"})
    assert r.status_code == 200 and r.json()["decision"] == "APPROVED"

    # 7-8. Credit generated and listed
    listed = [c for c in requests.get(f"{B}/marketplace/credits").json() if c["plantation_id"] == p["id"]]
    assert len(listed) == 1
    credit = listed[0]
    assert credit["is_listed"] and credit["verification_decision"] == "APPROVED"

    # Failure: invalid quantity / insufficient balance / nonexistent
    assert requests.post(f"{B}/marketplace/credits/{credit['id']}/purchase", headers=buyer, json={"quantity_tco2e": -5}).status_code == 422
    assert requests.post(f"{B}/marketplace/credits/{credit['id']}/purchase", headers=buyer,
                         json={"quantity_tco2e": credit["carbon_quantity_tco2e"] * 10}).status_code == 422
    assert requests.post(f"{B}/marketplace/credits/NOPE/purchase", headers=buyer, json={}).status_code == 404
    assert requests.post(f"{B}/plantations/999999/verify", headers=farmer).status_code == 404

    # 9. Purchase and retire
    txn = requests.post(f"{B}/marketplace/credits/{credit['id']}/purchase", headers=buyer, json={})
    assert txn.status_code == 201, txn.text
    assert requests.post(f"{B}/marketplace/credits/{credit['id']}/purchase", headers=buyer, json={}).status_code in (400, 409)
    ret = requests.post(f"{B}/marketplace/credits/{credit['id']}/retire", headers=buyer)
    assert ret.status_code == 200

    # 10. State persisted in the database
    db = SessionLocal()
    try:
        row = db.get(Credit, credit["id"])
        assert row.status == "RETIRED" and row.is_retired == 1 and row.retired_at is not None
        assert db.query(Transaction).filter(Transaction.credit_id == credit["id"]).count() == 1
        actions = {a.action for a in db.query(AuditLog).filter(AuditLog.target_id.in_([credit["id"], txn.json()["id"], v1["id"]]))}
        assert {"CARBON_CREDIT_ISSUED", "CREDIT_PURCHASE_COMPLETED", "CREDIT_RETIRED", "AUDITOR_DECISION"} <= actions
    finally:
        db.close()


def test_failed_verification_and_duplicate_submission(api_base):
    B = api_base
    farmer = _register(B, "FARMER")
    payload = plantation_payload(soil_soc_pct=0.3, soil_type="Sandy",
                                 ndvi_reported_value=0.1, ndvi_reported_source="TEST FIXTURE (synthetic)",
                                 ndvi_reported_date="2026-09-01")
    files = {"file": ("bare.jpg", synthetic_image_bytes("non_plantation", 8), "image/jpeg")}
    payload["image_url"] = requests.post(f"{B}/plantations/upload-image", headers=farmer, files=files).json()["image_url"]
    p = requests.post(f"{B}/plantations", headers=farmer, json=payload)
    assert p.status_code == 201
    assert requests.post(f"{B}/plantations", headers=farmer, json=payload).status_code == 409
    v = requests.post(f"{B}/plantations/{p.json()['id']}/verify", headers=farmer).json()
    assert v["decision"] == "REJECTED"
    assert all(c["plantation_id"] != p.json()["id"] for c in requests.get(f"{B}/marketplace/credits", params={"status_filter": "ALL"}).json())


def test_backend_unavailable_is_a_connection_error():
    """Clients must surface this as an error (the web/mobile apps show 'Cannot reach the backend')."""
    try:
        requests.get("http://127.0.0.1:1/api/health", timeout=2)
        raised = False
    except requests.ConnectionError:
        raised = True
    assert raised
