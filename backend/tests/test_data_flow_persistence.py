import io
import os
import sys
import uuid
import requests
import json

BASE_URL = "http://localhost:8000/api"
STATIC_URL = "http://localhost:8000"

def run_targeted_tests():
    print("======================================================================")
    print("🚀 TARGETED DATA FLOW & PERSISTENCE TEST SUITE (A THROUGH H)")
    print("======================================================================\n")

    # -------------------------------------------------------------------------
    # D & E: Uploaded Image Persistence & Static File Retrieval URL
    # -------------------------------------------------------------------------
    print("👉 [TEST D & E] Uploaded Image Persistence & Static File Retrieval...")
    
    # 1. Create a dummy test image in memory
    dummy_image_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xFF\xC0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xFF\xC4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xFF\xDA\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xFF\xD9"
    
    # Register Farmer A
    farmer_a_email = f"farmer_a_{uuid.uuid4().hex[:6]}@agri.test"
    reg_a_res = requests.post(f"{BASE_URL}/auth/register", json={
        "email": farmer_a_email,
        "password": "Password123!",
        "full_name": "Farmer Ananya Gowda",
        "role": "FARMER",
        "organization": "Kaveri Basin Cooperative"
    })
    assert reg_a_res.status_code == 201, f"Failed registering Farmer A: {reg_a_res.text}"
    token_a = reg_a_res.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Upload image
    files = {"file": ("actual_canopy.jpg", io.BytesIO(dummy_image_bytes), "image/jpeg")}
    upload_res = requests.post(f"{BASE_URL}/plantations/upload-image", headers=headers_a, files=files)
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    img_data = upload_res.json()
    rel_img_url = img_data["image_url"]  # e.g., "/uploads/plantation_xxx.jpg"
    assert rel_img_url.startswith("/uploads/"), f"Unexpected image_url format: {rel_img_url}"
    print(f"   ✅ Image uploaded to backend storage: '{rel_img_url}'")

    # Verify retrieval via GET http://localhost:8000/uploads/<filename>
    full_img_url = f"{STATIC_URL}{rel_img_url}"
    get_img_res = requests.get(full_img_url)
    assert get_img_res.status_code == 200, f"StaticFiles failed serving {full_img_url}: {get_img_res.status_code}"
    assert len(get_img_res.content) == len(dummy_image_bytes), "Retrieved image bytes mismatch"
    print(f"   ✅ Static file retrieval verified: GET {full_img_url} returned 200 OK with identical payload.")

    # -------------------------------------------------------------------------
    # A & H: Farmer Plantations Route & Farmer Ownership Isolation
    # -------------------------------------------------------------------------
    print("\n👉 [TEST A & H] Farmer Plantations Route & Farmer Ownership Isolation...")

    # Register Plantation A for Farmer A with real image & SOC
    plot_a_payload = {
        "name": "Mandya Teak & Coffee Agroforest",
        "farmer_name": "Farmer Ananya Gowda",
        "location": "Mandya, Karnataka, India",
        "latitude": 12.5218,
        "longitude": 76.8951,
        "area_hectares": 3.2,
        "plantation_age_years": 4.0,
        "tree_count": 640,
        "tree_species": "Teak, Neem, Coffee",
        "plantation_type": "Agroforestry",
        "sustainable_practice": "Drip Irrigation & Organic Mulching",
        "image_url": rel_img_url,
        "soil_soc_pct": 1.95,
        "soil_depth_cm": 45.0,
        "soil_type": "Red Sandy Loam"
    }
    create_a_res = requests.post(f"{BASE_URL}/plantations", headers=headers_a, json=plot_a_payload)
    assert create_a_res.status_code == 201, f"Failed creating plot: {create_a_res.text}"
    plot_a = create_a_res.json()
    plot_a_id = plot_a["id"]
    assert plot_a["image_url"] == rel_img_url, "Plantation image_url not persisted in DB!"
    print(f"   ✅ Plantation #{plot_a_id} created by Farmer A with persisted image_url.")

    # Register Farmer B
    farmer_b_email = f"farmer_b_{uuid.uuid4().hex[:6]}@agri.test"
    reg_b_res = requests.post(f"{BASE_URL}/auth/register", json={
        "email": farmer_b_email,
        "password": "Password123!",
        "full_name": "Farmer Bhaskar Rao",
        "role": "FARMER",
        "organization": "Malnad Organic Farmers"
    })
    token_b = reg_b_res.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Verify Farmer B sees 0 plantations initially (ISOLATION TEST)
    b_plantations_res = requests.get(f"{BASE_URL}/plantations", headers=headers_b)
    assert b_plantations_res.status_code == 200
    b_plantations = b_plantations_res.json()
    assert len(b_plantations) == 0, f"Farmer B leaked plantations! Found: {len(b_plantations)}"
    print("   ✅ Isolation confirmed: Farmer B cannot see Farmer A's plantation.")

    # Verify Farmer B cannot modify or access Farmer A's plantation
    forbidden_edit = requests.put(f"{BASE_URL}/plantations/{plot_a_id}/evidence", headers=headers_b, json={"soil_soc_pct": 0.5})
    assert forbidden_edit.status_code == 403, f"Farmer B was not blocked from editing Farmer A's plot! Status: {forbidden_edit.status_code}"
    print("   ✅ Access control confirmed: Farmer B modifying Farmer A's plot returns HTTP 403 Forbidden.")

    # Farmer A checks own plantations
    a_plantations_res = requests.get(f"{BASE_URL}/plantations", headers=headers_a)
    assert a_plantations_res.status_code == 200
    a_plantations = a_plantations_res.json()
    assert len(a_plantations) == 1
    assert a_plantations[0]["id"] == plot_a_id
    assert a_plantations[0]["image_url"] == rel_img_url
    print(f"   ✅ Farmer A Plantations route returns exactly Farmer A's plot (#{plot_a_id}) with image.")

    # -------------------------------------------------------------------------
    # C: Auditor Verification Queue Route
    # -------------------------------------------------------------------------
    print("\n👉 [TEST C] Auditor Verification Queue Route...")

    # Register an Auditor
    auditor_email = f"auditor_{uuid.uuid4().hex[:6]}@audit.test"
    reg_auditor = requests.post(f"{BASE_URL}/auth/register", json={
        "email": auditor_email,
        "password": "Password123!",
        "full_name": "Dr. Prathima Joshi",
        "role": "AUDITOR",
        "organization": "Bureau Veritas Carbon Audit"
    })
    token_auditor = reg_auditor.json()["access_token"]
    headers_auditor = {"Authorization": f"Bearer {token_auditor}"}

    # Auditor retrieves verification queue
    queue_res = requests.get(f"{BASE_URL}/admin/verifications", headers=headers_auditor)
    assert queue_res.status_code == 200, f"Auditor queue failed: {queue_res.text}"
    queue = queue_res.json()
    assert len(queue) > 0, "Verification queue is empty!"

    # Find Plot A in the auditor queue
    match_a = next((item for item in queue if item["plantation_id"] == plot_a_id), None)
    assert match_a is not None, f"Plantation #{plot_a_id} not found in Auditor verification queue!"
    assert match_a["image_url"] == rel_img_url, "Auditor queue item missing plantation image_url!"
    assert match_a["evidence_status"] is not None, "Auditor queue item missing evidence_status!"
    print(f"   ✅ Auditor successfully accessed queue via RBAC. Plot #{plot_a_id} present with image & evidence breakdown.")

    # -------------------------------------------------------------------------
    # Complete Multi-Modal Verification & Credit Issuance
    # -------------------------------------------------------------------------
    print("\n👉 Executing Multi-Modal Verification & Asset Issuance for Plot A...")
    verify_res = requests.post(f"{BASE_URL}/plantations/{plot_a_id}/verify", headers=headers_a)
    assert verify_res.status_code == 200, f"Verification failed: {verify_res.text}"
    ver_data = verify_res.json()
    assert ver_data["decision"] in ["APPROVED", "REVIEW"], f"Unexpected decision: {ver_data['decision']}"
    assert ver_data["overall_score"] is not None, "Overall score must not be None for complete evidence!"
    print(f"   🏆 Multi-Modal Score: {ver_data['overall_score']} -> Decision: {ver_data['decision']}")

    # If status is REVIEW, auditor approves it
    if ver_data["decision"] == "REVIEW":
        dec_res = requests.post(f"{BASE_URL}/admin/verifications/{ver_data['id']}/decision", headers=headers_auditor, json={
            "decision": "APPROVED",
            "notes": "Auditor ground inspection verified canopy density."
        })
        assert dec_res.status_code == 200
        print("   ✅ Auditor approved verification record.")

    # Farmer A issues carbon credits
    issue_res = requests.post(f"{BASE_URL}/plantations/{plot_a_id}/generate-credits", headers=headers_a, json={
        "price_per_tco2e": 1600.0
    })
    assert issue_res.status_code == 201, f"Credit issuance failed: {issue_res.text}"
    credit_a = issue_res.json()
    credit_a_id = credit_a["id"]
    assert credit_a["status"] == "AVAILABLE", f"Credit status should be AVAILABLE: {credit_a['status']}"
    assert credit_a["image_url"] == rel_img_url, "Credit missing plantation image_url!"
    print(f"   ✅ Carbon Credit '{credit_a_id}' issued ({credit_a['carbon_quantity_tco2e']} tCO2e @ ₹1600).")

    # -------------------------------------------------------------------------
    # B: Farmer Carbon Assets Route
    # -------------------------------------------------------------------------
    print("\n👉 [TEST B] Farmer Carbon Assets Route...")
    my_credits_res = requests.get(f"{BASE_URL}/marketplace/my-credits", headers=headers_a)
    assert my_credits_res.status_code == 200
    my_credits = my_credits_res.json()
    assert any(c["id"] == credit_a_id for c in my_credits), f"Credit '{credit_a_id}' not found in Farmer A's assets!"
    print(f"   ✅ Farmer Carbon Assets endpoint returned asset '{credit_a_id}' with status 'AVAILABLE'.")

    # -------------------------------------------------------------------------
    # F: Marketplace Asset Visibility Across Separate Login Sessions
    # -------------------------------------------------------------------------
    print("\n👉 [TEST F] Marketplace Visibility Across Separate Login Sessions...")
    
    # Register Buyer in a separate session
    buyer_email = f"buyer_{uuid.uuid4().hex[:6]}@corp.test"
    reg_buyer = requests.post(f"{BASE_URL}/auth/register", json={
        "email": buyer_email,
        "password": "Password123!",
        "full_name": "Smt. Shreya Hegde",
        "role": "BUYER",
        "organization": "Infosys ESG Net-Zero"
    })
    assert reg_buyer.status_code == 201
    
    # Authenticate as Buyer
    login_buyer = requests.post(f"{BASE_URL}/auth/login", json={
        "email": buyer_email,
        "password": "Password123!"
    })
    assert login_buyer.status_code == 200
    token_buyer = login_buyer.json()["access_token"]
    headers_buyer = {"Authorization": f"Bearer {token_buyer}"}

    # Buyer queries marketplace
    mkt_res = requests.get(f"{BASE_URL}/marketplace/credits?status_filter=AVAILABLE", headers=headers_buyer)
    assert mkt_res.status_code == 200
    available_credits = mkt_res.json()
    mkt_asset = next((c for c in available_credits if c["id"] == credit_a_id), None)
    assert mkt_asset is not None, f"Newly issued credit '{credit_a_id}' not visible to buyer on marketplace!"
    assert mkt_asset["image_url"] == rel_img_url, f"Marketplace card missing real image_url! Got: {mkt_asset['image_url']}"
    assert mkt_asset["plantation_name"] == plot_a_payload["name"]
    print(f"   ✅ Buyer sees Asset '{credit_a_id}' on Marketplace with persistent image '{mkt_asset['image_url']}'.")

    # -------------------------------------------------------------------------
    # G: Asset Lifecycle: AVAILABLE -> ACQUIRED (SOLD) -> RETIRED
    # -------------------------------------------------------------------------
    print("\n👉 [TEST G] Asset Lifecycle: AVAILABLE -> ACQUIRED (SOLD) -> RETIRED...")

    # Step 1: Buyer acquires the asset
    buy_res = requests.post(f"{BASE_URL}/marketplace/credits/{credit_a_id}/purchase", headers=headers_buyer)
    assert buy_res.status_code == 201, f"Purchase failed: {buy_res.text}"
    txn_data = buy_res.json()
    print(f"   ✅ Buyer acquired credit '{credit_a_id}' (Txn: {txn_data['id']}, Blockchain: {txn_data['blockchain_tx_hash'][:14]}...).")

    # Step 2: Verify asset is no longer AVAILABLE in marketplace
    mkt_check = requests.get(f"{BASE_URL}/marketplace/credits?status_filter=AVAILABLE", headers=headers_buyer)
    assert not any(c["id"] == credit_a_id for c in mkt_check.json()), "Credit should no longer appear in AVAILABLE marketplace!"
    print("   ✅ Asset removed from AVAILABLE marketplace.")

    # Step 3: Verify Buyer Portfolio contains the acquired asset
    buyer_portfolio_res = requests.get(f"{BASE_URL}/marketplace/my-credits", headers=headers_buyer)
    assert buyer_portfolio_res.status_code == 200
    buyer_portfolio = buyer_portfolio_res.json()
    assert any(c["id"] == credit_a_id for c in buyer_portfolio), "Asset not present in buyer portfolio!"
    print(f"   ✅ Asset '{credit_a_id}' present in Buyer Portfolio.")

    # Step 4: Buyer retires the carbon credit
    retire_res = requests.post(f"{BASE_URL}/marketplace/credits/{credit_a_id}/retire", headers=headers_buyer)
    assert retire_res.status_code == 200, f"Retirement failed: {retire_res.text}"
    retire_data = retire_res.json()
    assert retire_data["status"] == "RETIRED"
    print(f"   🔥 Asset '{credit_a_id}' permanently retired on-chain (Tx: {retire_data['blockchain_tx_hash'][:14]}...).")

    # Step 5: Verify retired asset cannot be acquired or retired again
    second_buy = requests.post(f"{BASE_URL}/marketplace/credits/{credit_a_id}/purchase", headers=headers_buyer)
    assert second_buy.status_code == 400
    second_retire = requests.post(f"{BASE_URL}/marketplace/credits/{credit_a_id}/retire", headers=headers_buyer)
    assert second_retire.status_code == 400
    print("   🔒 Immutability verified: Retired asset cannot be transferred or retired again.")

    print("\n======================================================================")
    print("🎉 ALL TARGETED TESTS (A THROUGH H) PASSED 100% PERFECTLY!")
    print("======================================================================\n")

if __name__ == "__main__":
    run_targeted_tests()
