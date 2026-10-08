import requests
import os

BASE_URL = "http://localhost:8000/api"

def run_comprehensive_evidence_integrity_test():
    print("=" * 70)
    print("🚀 COMPREHENSIVE EVIDENCE-INTEGRITY & VERIFICATION TEST SUITE")
    print("=" * 70)

    # -----------------------------------------------------------------
    # SCENARIO 1: NEW USER REGISTERS PLANTATION WITH MAP SELECTION ONLY
    # -----------------------------------------------------------------
    print("\n[SCENARIO 1] New User Registers Plantation with ONLY Map Selection...")
    
    # 1. Register a new user
    import uuid
    unique_email = f"farmer_{uuid.uuid4().hex[:6]}@climate.test"
    reg_res = requests.post(f"{BASE_URL}/auth/register", json={
        "email": unique_email,
        "password": "Password@123",
        "full_name": "Siddharth Gowda",
        "role": "FARMER",
        "phone": "+91 98450 11223",
        "organization": "Gowda Agro Farms"
    })
    assert reg_res.status_code in [200, 201], f"Registration failed: {reg_res.text}"
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"   ✅ New farmer '{unique_email}' registered & authenticated.")

    # 2. Register plantation with map boundary ONLY
    # NO ground image, NO soil SOC data
    plot_payload = {
        "name": "Bengaluru Urban Research Plot",
        "farmer_name": "Siddharth Gowda",
        "location": "Bengaluru, Karnataka, India",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "area_hectares": 2.1,
        "plantation_age_years": 2.5,
        "tree_count": 350,
        "tree_species": "Neem, Honge",
        "plantation_type": "Agroforestry",
        "sustainable_practice": "Standard Organic Agroforestry",
        "image_url": None,
        "soil_soc_pct": None,
        "soil_depth_cm": None,
        "soil_type": None
    }
    create_res = requests.post(f"{BASE_URL}/plantations", json=plot_payload, headers=headers)
    assert create_res.status_code == 201, f"Plot creation failed: {create_res.text}"
    plot = create_res.json()
    plot_id = plot["id"]
    print(f"   ✅ Plot #{plot_id} '{plot['name']}' created.")
    print(f"      - Image: {plot.get('image_url')}")
    print(f"      - Soil SOC %: {plot.get('soil_soc_pct')}")

    # 3. Request Verification Audit
    print(f"\n[SCENARIO 1 - AUDIT] Executing verification audit for Plot #{plot_id}...")
    ver_res = requests.post(f"{BASE_URL}/plantations/{plot_id}/verify", headers=headers)
    assert ver_res.status_code == 200, f"Verification request failed: {ver_res.text}"
    ver = ver_res.json()

    print(f"   📊 DECISION: {ver['decision']}")
    print(f"   📊 OVERALL SCORE: {ver['overall_score']}")
    print(f"   🛰️ SATELLITE / NDVI: Score={ver['ndvi_score']} | Status: {ver['ndvi_status']}")
    print(f"   📷 COMPUTER VISION: Score={ver['cv_score']} | Status: {ver['cv_detection_status']}")
    print(f"   🌱 SOIL / SOC: Score={ver['soc_score']} | Status: {ver['soc_status']}")
    print(f"   📋 EVIDENCE STATUS: {ver['evidence_status']}")

    # Strictly check absence of fabricated data
    assert ver["decision"] == "PENDING", f"Expected 'PENDING', got {ver['decision']}"
    assert ver["overall_score"] is None, f"Expected overall_score None, got {ver['overall_score']}"
    assert ver["cv_score"] is None, f"Expected cv_score None, got {ver['cv_score']}"
    assert ver["cv_detection_status"] == "NOT PROVIDED"
    assert ver["soc_score"] is None, f"Expected soc_score None, got {ver['soc_score']}"
    assert ver["soc_status"] == "NOT PROVIDED"
    assert ver["ndvi_score"] is None, f"Expected ndvi_score None, got {ver['ndvi_score']}"
    assert "Satellite imagery available for boundary reference" in ver["ndvi_status"]
    assert ver["evidence_status"]["boundary"] == "PROVIDED"
    assert ver["evidence_status"]["ground_imagery"] == "NOT PROVIDED"
    assert ver["evidence_status"]["soil_carbon"] == "NOT PROVIDED"
    assert ver["evidence_status"]["satellite_ndvi"] == "PENDING"
    print("   ✅ STRICT EVIDENCE AUDIT PASSED: Zero fabricated scores, status is VERIFICATION PENDING.")

    # 4. Confirm carbon credit minting is BLOCKED
    print(f"\n[SCENARIO 1 - ISSUANCE CHECK] Attempting to issue credits for unverified Plot #{plot_id}...")
    issue_res = requests.post(f"{BASE_URL}/plantations/{plot_id}/generate-credits", json={"price_per_tco2e": 1500.0}, headers=headers)
    assert issue_res.status_code == 400, f"Expected 400 Bad Request, got {issue_res.status_code}"
    print(f"   🔒 Credit minting successfully blocked: '{issue_res.json()['detail']}'")

    # -----------------------------------------------------------------
    # SCENARIO 2: USER SUPPLIES COMPLETE EVIDENCE AND RE-RUNS VERIFICATION
    # -----------------------------------------------------------------
    print(f"\n[SCENARIO 2] User Supplies Ground Imagery & Soil SOC Evidence for Plot #{plot_id}...")
    update_res = requests.put(f"{BASE_URL}/plantations/{plot_id}/evidence", json={
        "image_url": "/uploads/kaveri_agroforestry.jpg",
        "soil_soc_pct": 1.95,
        "soil_depth_cm": 45.0,
        "soil_type": "Red Sandy Loam"
    }, headers=headers)
    assert update_res.status_code == 200, f"Evidence update failed: {update_res.text}"
    print("   ✅ Evidence uploaded to plantation record.")

    # Re-run verification with all 3 modalities present
    rever_res = requests.post(f"{BASE_URL}/plantations/{plot_id}/verify", headers=headers)
    assert rever_res.status_code == 200
    rever = rever_res.json()
    print(f"   🏆 RE-VERIFICATION COMPLETED:")
    print(f"      - Decision: {rever['decision']}")
    print(f"      - NDVI Score: {rever['ndvi_score']} (Weight: 40% -> +{rever['ndvi_contribution']})")
    print(f"      - CV Score: {rever['cv_score']} (Weight: 35% -> +{rever['cv_contribution']})")
    print(f"      - SOC Score: {rever['soc_score']} (Weight: 25% -> +{rever['soc_contribution']})")
    print(f"      - Overall Weighted Score: {rever['overall_score']} / 100")
    
    assert rever["decision"] == "APPROVED"
    assert rever["overall_score"] >= 75.0
    assert rever["cv_score"] is not None
    assert rever["soc_score"] is not None
    assert rever["ndvi_score"] is not None
    print("   ✅ COMPLETE EVIDENCE AUDIT PASSED: Formula produces valid score and APPROVED status.")

    # Now credit minting is unlocked
    mint_res = requests.post(f"{BASE_URL}/plantations/{plot_id}/generate-credits", json={"price_per_tco2e": 1600.0}, headers=headers)
    assert mint_res.status_code == 201, f"Credit minting failed: {mint_res.text}"
    credit = mint_res.json()
    print(f"   ✅ Credit Minted: ID '{credit['id']}' ({credit['carbon_quantity_tco2e']} tCO2e @ ₹{credit['price_per_tco2e']}/tCO2e)")

    print("\n" + "=" * 70)
    print("🎉 ALL SCENARIOS VERIFIED SUCCESSFULLY WITH 100% DATA INTEGRITY!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    run_comprehensive_evidence_integrity_test()
