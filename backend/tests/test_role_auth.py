import time
import requests

BASE_URL = "http://localhost:8000/api"

def run_role_auth_tests():
    timestamp = int(time.time())
    
    print("🧪 Running Authentication & Role Isolation Verification Tests...\n")
    
    # Test 1: Register Farmer
    farmer_data = {
        "full_name": "Chiranthan SV",
        "email": f"chiranthan.farmer.{timestamp}@test.com",
        "password": "Password123!",
        "role": "FARMER",
        "organization": "Malnad Agroforestry Group"
    }
    res = requests.post(f"{BASE_URL}/auth/register", json=farmer_data)
    assert res.status_code == 201, f"Farmer registration failed: {res.text}"
    farmer_resp = res.json()
    assert farmer_resp["user"]["full_name"] == "Chiranthan SV"
    assert farmer_resp["user"]["role"] == "FARMER"
    farmer_token = farmer_resp["access_token"]
    print(f"✅ Farmer registered: {farmer_resp['user']['full_name']} (Role: {farmer_resp['user']['role']})")
    
    # Test 2: Register Buyer
    buyer_data = {
        "full_name": "Kavitha Sharma",
        "email": f"kavitha.buyer.{timestamp}@test.com",
        "password": "Password123!",
        "role": "BUYER",
        "organization": "CleanPlanet Ventures"
    }
    res = requests.post(f"{BASE_URL}/auth/register", json=buyer_data)
    assert res.status_code == 201, f"Buyer registration failed: {res.text}"
    buyer_resp = res.json()
    assert buyer_resp["user"]["full_name"] == "Kavitha Sharma"
    assert buyer_resp["user"]["role"] == "BUYER"
    buyer_token = buyer_resp["access_token"]
    print(f"✅ Buyer registered: {buyer_resp['user']['full_name']} (Role: {buyer_resp['user']['role']})")

    # Test 3: Register Auditor
    auditor_data = {
        "full_name": "Prof. S. N. Murthy",
        "email": f"murthy.auditor.{timestamp}@test.com",
        "password": "Password123!",
        "role": "AUDITOR",
        "organization": "Karnataka Carbon Audit Board"
    }
    res = requests.post(f"{BASE_URL}/auth/register", json=auditor_data)
    assert res.status_code == 201, f"Auditor registration failed: {res.text}"
    auditor_resp = res.json()
    assert auditor_resp["user"]["full_name"] == "Prof. S. N. Murthy"
    assert auditor_resp["user"]["role"] == "AUDITOR"
    auditor_token = auditor_resp["access_token"]
    print(f"✅ Auditor registered: {auditor_resp['user']['full_name']} (Role: {auditor_resp['user']['role']})")

    # Test 4: Reject Invalid Role
    invalid_data = {
        "full_name": "Hacker",
        "email": f"hacker.{timestamp}@test.com",
        "password": "Password123!",
        "role": "SUPERADMIN"
    }
    res = requests.post(f"{BASE_URL}/auth/register", json=invalid_data)
    assert res.status_code == 400, "Should have rejected invalid role"
    print("✅ Invalid role correctly rejected with HTTP 400.")

    # Test 5: Login with Email & Password ONLY (no role parameter)
    for cred, expected_role, expected_name in [
        (farmer_data, "FARMER", "Chiranthan SV"),
        (buyer_data, "BUYER", "Kavitha Sharma"),
        (auditor_data, "AUDITOR", "Prof. S. N. Murthy")
    ]:
        login_payload = {
            "email": cred["email"],
            "password": cred["password"]
            # Notice role is omitted!
        }
        lres = requests.post(f"{BASE_URL}/auth/login", json=login_payload)
        assert lres.status_code == 200, f"Login failed for {cred['email']}: {lres.text}"
        ldata = lres.json()
        assert ldata["user"]["role"] == expected_role, f"Expected {expected_role}, got {ldata['user']['role']}"
        assert ldata["user"]["full_name"] == expected_name, f"Expected {expected_name}, got {ldata['user']['full_name']}"
        print(f"✅ Pure Email/Password Login successful for {expected_name}: Stored Role '{ldata['user']['role']}' retrieved.")

    # Test 6: RBAC Verification
    # Auditor should have access to /api/admin/metrics
    admin_res = requests.get(f"{BASE_URL}/admin/metrics", headers={"Authorization": f"Bearer {auditor_token}"})
    assert admin_res.status_code == 200, f"Auditor failed to access admin metrics: {admin_res.text}"
    print("✅ Auditor successfully accessed /api/admin/metrics via RBAC.")

    # Farmer should be FORBIDDEN from /api/admin/metrics
    f_admin_res = requests.get(f"{BASE_URL}/admin/metrics", headers={"Authorization": f"Bearer {farmer_token}"})
    assert f_admin_res.status_code == 403, f"Farmer should be forbidden from admin metrics: {f_admin_res.status_code}"
    print("✅ Farmer correctly blocked from /api/admin/metrics with HTTP 403.")

    print("\n🎉 ALL AUTHENTICATION & ROLE TESTS PASSED!")

if __name__ == "__main__":
    run_role_auth_tests()
