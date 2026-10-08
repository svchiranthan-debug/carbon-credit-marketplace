import requests

BASE_URL = "http://localhost:8000/api"

def test_full_demo_journey():
    print("\n🚀 STARTING COMPREHENSIVE END-TO-END DEMO JOURNEY TEST...\n")
    
    # -------------------------------------------------------------
    # STEP 1 & 2: FARMER LOGIN & DASHBOARD
    # -------------------------------------------------------------
    print("👉 [STEP 1 & 2] Logging in as Farmer (Ramesh Kumar)...")
    login_res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "farmer@agrocarbon.demo",
        "password": "Demo@123",
        "role": "FARMER"
    })
    assert login_res.status_code == 200, f"Farmer login failed: {login_res.text}"
    farmer_token = login_res.json()["access_token"]
    farmer_headers = {"Authorization": f"Bearer {farmer_token}"}
    print("   ✅ Farmer authenticated successfully with JWT.")

    # -------------------------------------------------------------
    # STEP 3 & 4: REGISTER NEW PLANTATION
    # -------------------------------------------------------------
    print("\n👉 [STEP 3 & 4] Registering new Agroforestry Plantation...")
    plantation_payload = {
        "name": "Mandya High-Canopy Teak Agroforest",
        "farmer_name": "Ramesh Kumar",
        "location": "Mandya, Karnataka, India",
        "latitude": 12.5218,
        "longitude": 76.8951,
        "area_hectares": 2.5,
        "plantation_age_years": 5.0,
        "tree_count": 600,
        "tree_species": "Teak, Melia Dubia",
        "plantation_type": "Agroforestry",
        "sustainable_practice": "Organic Mulching & Drip Irrigation",
        "soil_soc_pct": 2.10,
        "soil_depth_cm": 50.0,
        "soil_type": "Loam",
        "image_url": "/uploads/kaveri_agroforestry.jpg"
    }
    create_res = requests.post(f"{BASE_URL}/plantations", json=plantation_payload, headers=farmer_headers)
    assert create_res.status_code == 201, f"Plantation creation failed: {create_res.text}"
    plantation = create_res.json()
    plantation_id = plantation["id"]
    print(f"   ✅ Plantation created: #{plantation_id} - '{plantation['name']}' (Status: {plantation['status']})")

    # -------------------------------------------------------------
    # STEP 5, 6 & 7: MULTI-MODAL AI VERIFICATION ENGINE
    # -------------------------------------------------------------
    print(f"\n👉 [STEP 5, 6 & 7] Running Multi-Modal Verification Engine for Plantation #{plantation_id}...")
    verify_res = requests.post(f"{BASE_URL}/plantations/{plantation_id}/verify", headers=farmer_headers)
    assert verify_res.status_code == 200, f"Verification failed: {verify_res.text}"
    ver = verify_res.json()
    
    print(f"   🛰️ Modality 1 (Satellite NDVI): Score {ver['ndvi_score']}/100 (Contribution: +{ver['ndvi_contribution']})")
    print(f"   📷 Modality 2 (Computer Vision): Score {ver['cv_score']}/100 (Contribution: +{ver['cv_contribution']})")
    print(f"   🌱 Modality 3 (Soil Organic C): Score {ver['soc_score']}/100 (Contribution: +{ver['soc_contribution']})")
    print(f"   🏆 COMPOSITE VERIFICATION SCORE: {ver['overall_score']} / 100 -> DECISION: {ver['decision']}")
    
    assert ver["decision"] == "APPROVED", f"Expected APPROVED, got {ver['decision']}"
    assert ver["overall_score"] >= 75.0, f"Expected score >= 75.0, got {ver['overall_score']}"

    # -------------------------------------------------------------
    # STEP 8: CARBON ESTIMATION & CREDIT MINTING
    # -------------------------------------------------------------
    print(f"\n👉 [STEP 8] Estimating Carbon Sequestration and Minting Marketplace Credits...")
    est_res = requests.post(f"{BASE_URL}/plantations/{plantation_id}/carbon-estimate", headers=farmer_headers)
    assert est_res.status_code == 200
    est = est_res.json()
    print(f"   🌲 Tree Count: {est['tree_count']} | Estimated Carbon: {est['estimated_carbon_tco2e']} tCO2e")
    
    mint_res = requests.post(f"{BASE_URL}/plantations/{plantation_id}/generate-credits", json={"price_per_tco2e": 1500.0}, headers=farmer_headers)
    assert mint_res.status_code == 201, f"Credit minting failed: {mint_res.text}"
    credit = mint_res.json()
    credit_id = credit["id"]
    print(f"   ✅ Carbon Credit Minted: ID '{credit_id}' ({credit['carbon_quantity_tco2e']} tCO2e @ ₹{credit['price_per_tco2e']}/tCO2e)")

    # -------------------------------------------------------------
    # STEP 9, 10 & 11: BUYER LOGIN & MARKETPLACE DISCOVERY
    # -------------------------------------------------------------
    print("\n👉 [STEP 9, 10 & 11] Logging in as Corporate Buyer (Arun Mehta - EcoCorp Solutions)...")
    buyer_login_res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "buyer@ecocorp.demo",
        "password": "Demo@123",
        "role": "BUYER"
    })
    assert buyer_login_res.status_code == 200
    buyer_token = buyer_login_res.json()["access_token"]
    buyer_headers = {"Authorization": f"Bearer {buyer_token}"}
    print("   ✅ Buyer authenticated.")

    market_res = requests.get(f"{BASE_URL}/marketplace/credits", headers=buyer_headers)
    assert market_res.status_code == 200
    all_credits = market_res.json()
    target_credit = next((c for c in all_credits if c["id"] == credit_id), None)
    assert target_credit is not None, "Minted credit not found in marketplace!"
    print(f"   ✅ Credit '{credit_id}' discovered on Marketplace (Status: {target_credit['status']}).")

    # -------------------------------------------------------------
    # STEP 12 & 13: BUYER PURCHASE VIA ESCROW
    # -------------------------------------------------------------
    print(f"\n👉 [STEP 12 & 13] Executing Purchase Order for Credit '{credit_id}'...")
    buy_res = requests.post(f"{BASE_URL}/marketplace/credits/{credit_id}/purchase", json={}, headers=buyer_headers)
    assert buy_res.status_code == 201, f"Purchase failed: {buy_res.text}"
    txn = buy_res.json()
    print(f"   🎉 TRANSACTION SUCCESSFUL! TXN ID: '{txn['id']}'")
    print(f"      Total Transferred: ₹{txn['total_amount']} ({txn['quantity_tco2e']} tCO2e)")
    print(f"      Settlement Status: {txn['status']} | Notes: {txn['notes']}")

    # Verify credit is now marked SOLD
    credit_detail = requests.get(f"{BASE_URL}/marketplace/credits/{credit_id}").json()
    assert credit_detail["status"] == "SOLD", "Credit status should be SOLD after purchase!"
    print("   ✅ Credit status verified as 'SOLD'.")

    # -------------------------------------------------------------
    # STEP 14: TRANSACTION HISTORY & ADMIN AUDIT QUEUE
    # -------------------------------------------------------------
    print("\n👉 [STEP 14] Verifying Buyer Transaction History...")
    txns_res = requests.get(f"{BASE_URL}/transactions", headers=buyer_headers)
    assert txns_res.status_code == 200
    buyer_txns = txns_res.json()
    assert any(t["id"] == txn["id"] for t in buyer_txns)
    print(f"   ✅ Transaction '{txn['id']}' verified in Buyer ESG Portfolio ledger.")

    # -------------------------------------------------------------
    # STEP 15: BLOCKCHAIN AUDIT LAYER & ON-CHAIN RETIREMENT
    # -------------------------------------------------------------
    print(f"\n👉 [STEP 15] Verifying On-Chain Smart Contract Audit Record & Retiring Credit '{credit_id}'...")
    bc_rec_res = requests.get(f"{BASE_URL}/marketplace/credits/{credit_id}/blockchain-record")
    assert bc_rec_res.status_code == 200, f"Failed getting blockchain record: {bc_rec_res.text}"
    bc_rec = bc_rec_res.json()
    print(f"   🔗 On-Chain Credit Record: ID={bc_rec['credit_id']}, Contract={bc_rec['contract_address']}")
    print(f"   📄 Report SHA-256 Hash: {bc_rec['report_hash'][:16]}...")
    print(f"   💼 Current Owner Address: {bc_rec['owner_address']}")
    print(f"   ⚡ Status: {bc_rec['status']} (is_retired={bc_rec['is_retired']})")

    # Retire the credit on smart contract
    retire_res = requests.post(f"{BASE_URL}/marketplace/credits/{credit_id}/retire", headers=buyer_headers)
    assert retire_res.status_code == 200, f"Retirement failed: {retire_res.text}"
    retire_data = retire_res.json()
    assert retire_data["status"] == "RETIRED"
    print(f"   🔥 RETIREMENT SUCCESSFUL! Tx Hash: {retire_data['blockchain_tx_hash']}")
    print(f"      Message: '{retire_data['message']}'")

    # Confirm on-chain record reflects retirement
    bc_rec_after = requests.get(f"{BASE_URL}/marketplace/credits/{credit_id}/blockchain-record").json()
    assert bc_rec_after["is_retired"] is True
    assert bc_rec_after["status"] == "RETIRED"
    print("   ✅ Smart Contract state verified: Credit is permanently retired.")

    # Admin verification
    print("\n👉 [ADMIN AUDIT] Logging in as Admin (Dr. Sunita Rao)...")
    admin_login = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "admin@agrocarbon.demo",
        "password": "Demo@123",
        "role": "ADMIN"
    }).json()
    admin_headers = {"Authorization": f"Bearer {admin_login['access_token']}"}

    metrics = requests.get(f"{BASE_URL}/admin/metrics", headers=admin_headers).json()
    print(f"   📊 Admin Metrics: Farmers={metrics['total_farmers']}, Plantations={metrics['total_plantations']}, Approved={metrics['approved_plantations']}, Traded Volume=₹{metrics['total_transaction_volume_inr']}")

    print("\n🎉 ALL 15 STEPS OF THE END-TO-END DEMO JOURNEY PASSED 100% PERFECTLY!\n")

if __name__ == "__main__":
    test_full_demo_journey()
