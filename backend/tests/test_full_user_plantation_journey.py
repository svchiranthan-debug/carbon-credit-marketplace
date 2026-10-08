import time
import requests

BASE_URL = "http://localhost:8000/api"

def test_full_journey():
    timestamp = int(time.time())
    print("🌱 Testing Complete User Journey: Registration -> Login -> Plantation Creation -> Verification...\n")
    
    # 1. Register new user with FARMER role
    farmer_payload = {
        "full_name": "Siddharth Gowda",
        "email": f"siddharth.gowda.{timestamp}@malnadfarms.org",
        "password": "SecurePassword123",
        "role": "FARMER",
        "phone": "+91 98451 23456",
        "organization": "Malnad Agroforestry Collective"
    }
    reg_res = requests.post(f"{BASE_URL}/auth/register", json=farmer_payload)
    assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
    user_info = reg_res.json()["user"]
    print(f"✅ Registered account for: '{user_info['full_name']}'")
    print(f"   Email: {user_info['email']} | Role: {user_info['role']} | Org: {user_info['organization']}")
    assert user_info["full_name"] == "Siddharth Gowda"
    assert user_info["role"] == "FARMER"

    # 2. Login using ONLY email and password (no role passed)
    login_res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": farmer_payload["email"],
        "password": farmer_payload["password"]
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token_data = login_res.json()
    token = token_data["access_token"]
    logged_user = token_data["user"]
    print(f"✅ Login successful for '{logged_user['full_name']}' without manual role input.")
    print(f"   Retrieved user role from DB: {logged_user['role']}")
    assert logged_user["role"] == "FARMER"

    # 3. Create a new plantation with address-level location and calculated area (2.43 ha)
    headers = {"Authorization": f"Bearer {token}"}
    plantation_payload = {
        "name": "Shivamogga Basavanagudi Agroforest Plot",
        "farmer_name": logged_user["full_name"],
        "location": "Basavanagudi 1st Cross, Shivamogga, Karnataka, India",
        "latitude": 13.834591,
        "longitude": 75.733936,
        "area_hectares": 2.43,
        "plantation_age_years": 3.0,
        "tree_count": 450,
        "tree_species": "Arecanut, Pepper, Silver Oak, Teak",
        "plantation_type": "Agroforestry",
        "sustainable_practice": "Organic Multi-Tier Agroforestry",
        "image_url": None,
        "soil_soc_pct": None,
        "soil_depth_cm": None,
        "soil_type": None
    }
    p_res = requests.post(f"{BASE_URL}/plantations", json=plantation_payload, headers=headers)
    assert p_res.status_code == 201, f"Plantation creation failed: {p_res.text}"
    p_data = p_res.json()
    print(f"✅ Plantation created successfully:")
    print(f"   ID: #{p_data['id']} - '{p_data['name']}'")
    print(f"   Farmer: {p_data['farmer_name']} (User ID: {p_data['farmer_id']})")
    print(f"   Location: {p_data['location']}")
    print(f"   Coordinates: ({p_data['latitude']}, {p_data['longitude']})")
    print(f"   Area: {p_data['area_hectares']} ha")
    print(f"   Status: {p_data['status']}")
    assert p_data["farmer_name"] == "Siddharth Gowda"
    assert p_data["farmer_id"] == logged_user["id"]
    assert p_data["area_hectares"] == 2.43
    assert p_data["status"] == "SUBMITTED"

    # 4. Verify farmer's plantation list isolation (Farmer should only see their own plantations)
    my_plantations_res = requests.get(f"{BASE_URL}/plantations", headers=headers)
    assert my_plantations_res.status_code == 200
    my_plantations = my_plantations_res.json()
    print(f"✅ Farmer #{logged_user['id']} has {len(my_plantations)} plantation(s).")
    assert all(p["farmer_id"] == logged_user["id"] for p in my_plantations)
    print("   Data isolation verified: Demo plantations do not leak into newly registered farmer's dashboard!")

    # 5. Add evidence (Image and Soil data)
    # Upload an actual test image
    test_img_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xFF\xC0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xFF\xC4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xFF\xDA\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xFF\xD9"
    img_upload_res = requests.post(
        f"{BASE_URL}/plantations/upload-image",
        files={"file": ("shivamogga_test.jpg", test_img_content, "image/jpeg")},
        headers=headers
    )
    assert img_upload_res.status_code == 200, f"Upload failed: {img_upload_res.text}"
    uploaded_img_url = img_upload_res.json()["image_url"]
    print(f"✅ Ground image uploaded: {uploaded_img_url}")

    evidence_res = requests.put(f"{BASE_URL}/plantations/{p_data['id']}/evidence", json={
        "image_url": uploaded_img_url,
        "soil_soc_pct": 1.95,
        "soil_depth_cm": 45.0,
        "soil_type": "Red Sandy Loam"
    }, headers=headers)
    assert evidence_res.status_code == 200
    print(f"✅ Ground image and soil evidence updated for plantation #{p_data['id']}.")

    # 6. Execute multi-modal verification
    verif_res = requests.post(f"{BASE_URL}/plantations/{p_data['id']}/verify", headers=headers)
    assert verif_res.status_code == 200
    v_data = verif_res.json()
    print(f"✅ Multi-Modal Verification completed:")
    print(f"   Decision: {v_data['decision']}")
    print(f"   Score: {v_data['overall_score']} / 100")
    print(f"   NDVI Score: {v_data['ndvi_score']}")
    print(f"   CV Score: {v_data['cv_score']}")
    print(f"   SOC Score: {v_data['soc_score']}")
    assert v_data["decision"] in ["APPROVED", "REVIEW"]

    print("\n🎉 COMPLETE USER & PLANTATION JOURNEY TEST PASSED 100%!")

if __name__ == "__main__":
    test_full_journey()
