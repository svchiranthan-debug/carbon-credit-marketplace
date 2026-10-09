"""Task 5: farmer submission flow — validation, duplicates, ownership, evidence updates, uploads."""
import pytest

from conftest import TEST_NDVI, plantation_payload, register, synthetic_image_bytes, upload_image


@pytest.fixture
def farmer(client):
    return register(client, "FARMER", "Synthetic Farmer")


def test_create_returns_id_and_pending_status(client, farmer):
    headers, user = farmer
    r = client.post("/api/plantations", headers=headers, json=plantation_payload())
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body["id"], int) and body["status"] == "SUBMITTED"
    assert body["farmer_id"] == user["id"] and body["farmer_name"] == "Synthetic Farmer"
    assert body["soil_soc_pct"] is None and body["image_url"] is None


@pytest.mark.parametrize("override", [
    {"name": ""}, {"name": "   "}, {"location": ""},
    {"latitude": 91}, {"longitude": -181}, {"area_hectares": 0}, {"area_hectares": -1},
    {"tree_count": 0}, {"tree_count": 2.5}, {"plantation_age_years": -1},
    {"soil_soc_pct": 0}, {"soil_soc_pct": 11}, {"soil_depth_cm": -5},
    {"ndvi_reported_value": 1.5, "ndvi_reported_source": "x", "ndvi_reported_date": "2026-01-01"},
    {"ndvi_reported_value": 0.5},                                   # incomplete NDVI evidence
    {"ndvi_reported_value": 0.5, "ndvi_reported_source": "x", "ndvi_reported_date": "2999-01-01"},
    {"ndvi_reported_value": 0.5, "ndvi_reported_source": "x", "ndvi_reported_date": "01/02/2026"},
    {"latitude": "north"},
])
def test_malformed_input_rejected(client, farmer, override):
    r = client.post("/api/plantations", headers=farmer[0], json=plantation_payload(**override))
    assert r.status_code == 422, (override, r.text)


def test_missing_required_field_rejected(client, farmer):
    payload = plantation_payload()
    del payload["tree_species"]
    r = client.post("/api/plantations", headers=farmer[0], json=payload)
    assert r.status_code == 422
    assert any(e["loc"][-1] == "tree_species" for e in r.json()["detail"])


def test_duplicate_submission_rejected(client, farmer):
    payload = plantation_payload()
    assert client.post("/api/plantations", headers=farmer[0], json=payload).status_code == 201
    dup = client.post("/api/plantations", headers=farmer[0], json={**payload, "name": payload["name"].upper()})
    assert dup.status_code == 409 and "Duplicate" in dup.json()["detail"]


def test_ownership_isolation(client, farmer):
    a = client.post("/api/plantations", headers=farmer[0], json=plantation_payload()).json()
    other, _ = register(client, "FARMER")
    assert client.get(f"/api/plantations/{a['id']}", headers=other).status_code == 403
    assert client.put(f"/api/plantations/{a['id']}/evidence", headers=other, json={"soil_soc_pct": 1.0}).status_code == 403
    assert client.post(f"/api/plantations/{a['id']}/verify", headers=other).status_code == 403
    assert all(p["id"] != a["id"] for p in client.get("/api/plantations", headers=other).json())
    buyer, _ = register(client, "BUYER")
    assert client.get(f"/api/plantations/{a['id']}", headers=buyer).status_code == 404  # unverified hidden from buyers
    assert client.get("/api/plantations/999999", headers=farmer[0]).status_code == 404


def test_upload_validation_and_serving(client, farmer):
    url = upload_image(client, farmer[0])
    assert url.startswith("/uploads/")
    served = client.get(url)   # signed link from the API
    assert served.status_code == 200 and served.content[:2] == b"\xff\xd8"
    assert client.get(url.split("?")[0]).status_code == 403          # photos are not public
    bad_ext = client.post("/api/plantations/upload-image", headers=farmer[0], files={"file": ("x.txt", b"hello", "text/plain")})
    assert bad_ext.status_code == 415
    fake_jpg = client.post("/api/plantations/upload-image", headers=farmer[0], files={"file": ("x.jpg", b"not really", "image/jpeg")})
    assert fake_jpg.status_code == 400 and "decoded" in fake_jpg.json()["detail"]


def test_evidence_update_and_per_plantation_image_upload(client, farmer):
    p = client.post("/api/plantations", headers=farmer[0], json=plantation_payload()).json()
    assert client.put(f"/api/plantations/{p['id']}/evidence", headers=farmer[0], json={}).status_code == 422
    r = client.put(f"/api/plantations/{p['id']}/evidence", headers=farmer[0], json={"soil_soc_pct": 1.9, "soil_type": "Loam", **TEST_NDVI})
    assert r.status_code == 200 and r.json()["soil_soc_pct"] == 1.9 and r.json()["ndvi_reported_value"] == 0.78
    up = client.post(f"/api/plantations/{p['id']}/image", headers=farmer[0],
                     files={"file": ("photo.png", synthetic_image_bytes("plantation", 9, "PNG"), "image/png")})
    assert up.status_code == 200 and up.json()["status"] == "SUBMITTED"
    v = client.post(f"/api/plantations/{p['id']}/verify", headers=farmer[0]).json()
    assert v["decision"] == "REVIEW" and v["overall_score"] is not None


def test_verification_run_endpoint_rejects_foreign_paths(client, farmer):
    p = client.post("/api/plantations", headers=farmer[0], json=plantation_payload()).json()
    r = client.post("/api/verification/run", headers=farmer[0], json={"plantation_id": p["id"], "ground_image_path": "/etc/passwd"})
    assert r.status_code == 422
    r = client.post("/api/verification/run", headers=farmer[0], json={"plantation_id": p["id"], "soc_sample_pct": 1.75})
    assert r.status_code == 200 and r.json()["decision"] == "PENDING" and r.json()["soc_pct"] == 1.75


def _square(lat, lng, side_m=63.6):
    import math
    dlat = side_m / 111_320
    dlng = side_m / (111_320 * math.cos(math.radians(lat)))
    return [[lat, lng], [lat, lng + dlng], [lat + dlat, lng + dlng], [lat + dlat, lng]], (lat + dlat / 2, lng + dlng / 2)


def test_boundary_polygon_stored_and_validated(client, farmer):
    pts, (clat, clng) = _square(13.30, 75.40)
    ok = client.post("/api/plantations", headers=farmer[0], json=plantation_payload(
        latitude=clat, longitude=clng, area_hectares=0.4047, boundary=pts))
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert body["boundary"] == [[round(a, 10), round(b, 10)] for a, b in pts] or len(body["boundary"]) == 4
    v = client.get(f"/api/plantations/{body['id']}/verification", headers=farmer[0]).json()
    assert v["evidence_status"]["boundary_type"] == "POLYGON"

    pts2, (clat2, clng2) = _square(13.31, 75.41)
    # Declared area far from the drawn polygon's area
    bad_area = client.post("/api/plantations", headers=farmer[0], json=plantation_payload(
        latitude=clat2, longitude=clng2, area_hectares=2.0, boundary=pts2))
    assert bad_area.status_code == 422 and "does not match" in bad_area.text
    # Centre point outside the polygon
    outside = client.post("/api/plantations", headers=farmer[0], json=plantation_payload(
        latitude=clat2 + 0.01, longitude=clng2, area_hectares=0.4047, boundary=pts2))
    assert outside.status_code == 422
    # Too few / malformed points
    for bad in ([[13.3, 75.4], [13.31, 75.4]], [[13.3, 75.4, 1], [13.31, 75.4], [13.3, 75.41]], [[95, 75.4], [13.31, 75.4], [13.3, 75.41]]):
        r = client.post("/api/plantations", headers=farmer[0], json=plantation_payload(boundary=bad))
        assert r.status_code == 422, bad


def test_plantation_without_boundary_uses_centre_and_area(client, farmer):
    p = client.post("/api/plantations", headers=farmer[0], json=plantation_payload()).json()
    assert p["boundary"] is None
    v = client.get(f"/api/plantations/{p['id']}/verification", headers=farmer[0]).json()
    assert v["evidence_status"]["boundary_type"] == "CENTRE_AND_AREA"
