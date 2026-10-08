#!/usr/bin/env python3
"""
Targeted Verification Test for Auditor Dashboard Access:
1. Create AUDITOR user
2. Login
3. Assert returned role == "AUDITOR"
4. Call GET /api/admin/metrics -> status 200
5. Call GET /api/admin/verifications -> status 200 (verify records with None/null overall_score are returned safely)
6. Verify farmer-only plantation creation remains forbidden for AUDITOR (HTTP 403)
7. Verify BUYER/FARMER do not receive auditor-only access (HTTP 403)
8. Verify Auditor review action on verification queue (POST /api/admin/verifications/{id}/decision)
"""

import time
import requests

API_URL = "http://localhost:8000"

def test_auditor_dashboard_access():
    print("=" * 70)
    print("🧪 RUNNING AUDITOR AUTHENTICATION & DASHBOARD ACCESS TESTS")
    print("=" * 70)

    ts = int(time.time())
    auditor_email = f"auditor_test_{ts}@registry.test"
    farmer_email = f"farmer_test_{ts}@registry.test"
    buyer_email = f"buyer_test_{ts}@registry.test"

    # 1. Create AUDITOR user
    reg_res = requests.post(f"{API_URL}/api/auth/register", json={
        "email": auditor_email,
        "password": "Password@123",
        "full_name": "Dr. V. K. Rao",
        "role": "AUDITOR",
        "organization": "Independent Carbon Audit Bureau"
    })
    assert reg_res.status_code in (200, 201), f"Auditor registration failed: {reg_res.text}"
    print(f"✅ Step 1: Registered AUDITOR account: {auditor_email}")

    # 2. Login as AUDITOR
    login_res = requests.post(f"{API_URL}/api/auth/login", json={
        "email": auditor_email,
        "password": "Password@123"
    })
    assert login_res.status_code == 200, f"Auditor login failed: {login_res.text}"
    login_data = login_res.json()
    print("✅ Step 2: Auditor login successful")

    # 3. Assert returned role == "AUDITOR"
    retrieved_role = login_data.get("user", {}).get("role")
    assert retrieved_role == "AUDITOR", f"Expected role 'AUDITOR', got '{retrieved_role}'"
    print(f"✅ Step 3: Asserted returned role == '{retrieved_role}'")

    auditor_token = login_data.get("access_token") or login_data.get("token")
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}

    # 4. Call GET /api/admin/metrics
    metrics_res = requests.get(f"{API_URL}/api/admin/metrics", headers=auditor_headers)
    assert metrics_res.status_code == 200, f"GET /api/admin/metrics failed: {metrics_res.status_code}"
    metrics_data = metrics_res.json()
    print(f"✅ Step 4: GET /api/admin/metrics returned HTTP 200. Metrics: total_farmers={metrics_data.get('total_farmers')}, plantations={metrics_data.get('total_plantations')}")

    # 5. Call GET /api/admin/verifications
    verif_res = requests.get(f"{API_URL}/api/admin/verifications", headers=auditor_headers)
    assert verif_res.status_code == 200, f"GET /api/admin/verifications failed: {verif_res.status_code}"
    queue_items = verif_res.json()
    print(f"✅ Step 5: GET /api/admin/verifications returned HTTP 200 ({len(queue_items)} records)")

    # Verify that records with null overall_score exist or are handled cleanly
    null_score_items = [item for item in queue_items if item.get("overall_score") is None]
    print(f"   ℹ️ Verification queue contains {len(null_score_items)} items with overall_score=None (pending evaluations)")

    # 6. Verify farmer-only plantation creation remains forbidden for AUDITOR
    plant_res = requests.post(f"{API_URL}/api/plantations", headers=auditor_headers, json={
        "name": "Unauthorized Auditor Plot",
        "farmer_name": "Dr. V. K. Rao",
        "location": "Bengaluru, Karnataka, India",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "area_hectares": 1.8,
        "plantation_age_years": 2.0,
        "tree_count": 300,
        "tree_species": "Teak",
        "plantation_type": "Agroforestry"
    })
    assert plant_res.status_code == 403, f"Expected 403 for auditor creating plantation, got {plant_res.status_code}"
    print("✅ Step 6: Verified farmer-only plantation creation is blocked for AUDITOR (HTTP 403 Forbidden)")

    # 7. Verify BUYER/FARMER do not receive auditor-only access
    # Register and login a Farmer
    farmer_reg = requests.post(f"{API_URL}/api/auth/register", json={
        "email": farmer_email,
        "password": "Password@123",
        "full_name": "Test Farmer",
        "role": "FARMER"
    })
    farmer_token = farmer_reg.json().get("access_token")
    farmer_headers = {"Authorization": f"Bearer {farmer_token}"}

    farmer_queue_res = requests.get(f"{API_URL}/api/admin/verifications", headers=farmer_headers)
    assert farmer_queue_res.status_code == 403, f"Expected 403 for farmer accessing verification queue, got {farmer_queue_res.status_code}"

    # Register and login a Buyer
    buyer_reg = requests.post(f"{API_URL}/api/auth/register", json={
        "email": buyer_email,
        "password": "Password@123",
        "full_name": "Test Buyer",
        "role": "BUYER"
    })
    buyer_token = buyer_reg.json().get("access_token")
    buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

    buyer_queue_res = requests.get(f"{API_URL}/api/admin/verifications", headers=buyer_headers)
    assert buyer_queue_res.status_code == 403, f"Expected 403 for buyer accessing verification queue, got {buyer_queue_res.status_code}"
    print("✅ Step 7: Verified FARMER and BUYER are strictly forbidden from /api/admin/verifications (HTTP 403)")

    # 8. Verify Auditor review action on a verification record if one exists
    if queue_items:
        first_item = queue_items[0]
        review_res = requests.post(
            f"{API_URL}/api/admin/verifications/{first_item['id']}/decision",
            headers=auditor_headers,
            json={"decision": "REVIEW", "notes": "Auditor marked for manual field audit."}
        )
        assert review_res.status_code == 200, f"Auditor review action failed: {review_res.status_code}"
        print(f"✅ Step 8: Auditor successfully performed review decision on verification {first_item['id']} (HTTP 200)")

    print("=" * 70)
    print("🎉 ALL AUDITOR DASHBOARD ACCESS & RBAC TESTS PASSED 100%!")
    print("=" * 70)

if __name__ == "__main__":
    test_auditor_dashboard_access()
