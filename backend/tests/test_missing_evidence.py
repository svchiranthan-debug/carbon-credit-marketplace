import requests

BASE_URL = "http://localhost:8000/api"

def test_missing_evidence():
    print("\n🔍 TESTING PLANTATION REGISTRATION WITH MAP ONLY (NO IMAGE, NO SOIL DATA)...")

    # 1. Login as farmer
    login_res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "farmer@agrocarbon.demo",
        "password": "Demo@123",
        "role": "FARMER"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Register plantation with only Map/Boundary selection (no image, no soil)
    payload = {
        "name": "Bengaluru Urban Boundary Plot",
        "farmer_name": "Ramesh Kumar",
        "location": "Bengaluru, Karnataka, India",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "area_hectares": 1.75,
        "plantation_age_years": 2.0,
        "tree_count": 250,
        "tree_species": "Neem, Gulmohar",
        "plantation_type": "Agroforestry",
        # NO image_url
        "image_url": None,
        # NO soil data
        "soil_soc_pct": None,
        "soil_depth_cm": None,
        "soil_type": None
    }

    create_res = requests.post(f"{BASE_URL}/plantations", json=payload, headers=headers)
    assert create_res.status_code == 201, f"Create failed: {create_res.text}"
    plot = create_res.json()
    plot_id = plot["id"]
    print(f"   ✅ Plantation #{plot_id} created with Map Boundary only (image_url=None, soil_soc_pct=None).")

    # 3. Get or Run verification
    ver_res = requests.post(f"{BASE_URL}/plantations/{plot_id}/verify", headers=headers)
    assert ver_res.status_code == 200, f"Verification failed: {ver_res.text}"
    ver = ver_res.json()

    print(f"   📋 Verification Decision: {ver['decision']}")
    print(f"   📊 Overall Score: {ver['overall_score']}")
    print(f"   🛰️ Satellite NDVI: Score={ver['ndvi_score']} | Status: {ver['ndvi_status']}")
    print(f"   📷 Computer Vision: Score={ver['cv_score']} | Status: {ver['cv_detection_status']}")
    print(f"   🌱 Soil / SOC: Score={ver['soc_score']} | Status: {ver['soc_status']}")
    print(f"   🔍 Evidence Status: {ver['evidence_status']}")

    assert ver["decision"] == "PENDING", f"Expected decision 'PENDING', got {ver['decision']}"
    assert ver["overall_score"] is None, f"Expected overall_score to be None, got {ver['overall_score']}"
    assert ver["cv_score"] is None, f"Expected cv_score to be None, got {ver['cv_score']}"
    assert ver["cv_detection_status"] == "NOT PROVIDED"
    assert ver["soc_score"] is None, f"Expected soc_score to be None, got {ver['soc_score']}"
    assert ver["soc_status"] == "NOT PROVIDED"
    assert "Satellite imagery available for boundary reference" in ver["ndvi_status"]

    # 4. Confirm credit minting is BLOCKED
    mint_res = requests.post(f"{BASE_URL}/plantations/{plot_id}/generate-credits", json={"price_per_tco2e": 1500.0}, headers=headers)
    print(f"   🔒 Credit minting attempt response status: {mint_res.status_code} (Expected 400 Bad Request)")
    assert mint_res.status_code == 400, f"Expected 400 when minting unverified credits, got {mint_res.status_code}"
    print(f"      Blocked Detail: {mint_res.json()['detail']}")

    print("\n✅ ZERO FABRICATED EVIDENCE TEST PASSED PERFECTLY!\n")

if __name__ == "__main__":
    test_missing_evidence()
