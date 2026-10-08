"""Task 3: verification engine rules (PENDING handling, no fabrication, explainability, auditability)."""
import pytest

from conftest import TEST_NDVI, make_scored_plantation, plantation_payload, register, upload_image


@pytest.fixture
def farmer(client):
    return register(client, "FARMER")[0]


def _verify(client, headers, pid):
    r = client.post(f"/api/plantations/{pid}/verify", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _assert_all_scores_null(v):
    for key in ("overall_score", "ndvi_contribution", "cv_contribution", "soc_contribution", "risk_score", "risk_level"):
        assert v[key] is None, f"{key} should be null, got {v[key]}"


def test_boundary_only_stays_pending_with_null_values(client, farmer):
    p = client.post("/api/plantations", headers=farmer, json=plantation_payload()).json()
    assert p["status"] == "SUBMITTED"
    v = _verify(client, farmer, p["id"])
    assert v["decision"] == "PENDING"
    _assert_all_scores_null(v)
    for key in ("ndvi_value", "ndvi_score", "cv_score", "soc_score", "soc_pct", "ai_confidence_pct", "mean_ndvi"):
        assert v[key] is None, key
    assert v["is_real_satellite"] is False
    assert set(v["missing_evidence"]) == {"Ground imagery", "Soil carbon data"}
    assert v["evidence_status"] == {"boundary": "PROVIDED", "boundary_type": "CENTRE_AND_AREA", "ground_imagery": "NOT PROVIDED",
                                    "soil_carbon": "NOT PROVIDED", "satellite_ndvi": "PENDING"}
    assert any("Missing required evidence: Ground imagery" in r for r in v["decision_reasons"])
    assert client.get(f"/api/plantations/{p['id']}", headers=farmer).json()["status"] == "SUBMITTED"


def test_soil_only_still_pending_but_shows_submitted_soc(client, farmer):
    p = client.post("/api/plantations", headers=farmer, json=plantation_payload(soil_soc_pct=1.6)).json()
    v = _verify(client, farmer, p["id"])
    assert v["decision"] == "PENDING"
    assert v["soc_pct"] == 1.6           # the farmer's real input is shown...
    assert v["soc_score"] is None        # ...but it is not scored
    _assert_all_scores_null(v)
    assert v["missing_evidence"] == ["Ground imagery"]


def test_complete_evidence_but_no_ndvi_source_stays_pending(client, farmer):
    """Satellite disabled in tests and no reported NDVI → NDVI unavailable → PENDING, never simulated."""
    p = make_scored_plantation(client, farmer)
    v = _verify(client, farmer, p["id"])
    assert v["decision"] == "PENDING"
    assert v["ndvi_score"] is None and v["ndvi_value"] is None and v["ndvi_provenance"] is None
    assert v["evidence_status"]["satellite_ndvi"] == "UNAVAILABLE"
    assert v["missing_evidence"] == ["Satellite NDVI"]
    # Real measurements that DID run are still reported
    assert v["cv_score"] is not None and v["soc_score"] is not None
    assert v["overall_score"] is None
    assert any("Satellite NDVI unavailable" in r for r in v["decision_reasons"])
    # No credit
    assert client.post(f"/api/plantations/{p['id']}/generate-credits", headers=farmer, json={}).status_code == 409


def test_computed_ndvi_full_score_approves_and_explains(client, farmer, computed_ndvi):
    p = make_scored_plantation(client, farmer, soc=2.4)
    v = _verify(client, farmer, p["id"])
    assert v["ndvi_provenance"] == "SENTINEL2_COMPUTED"
    expected = round(round(0.40 * v["ndvi_score"], 2) + round(0.35 * v["cv_score"], 2) + round(0.25 * v["soc_score"], 2), 1)
    assert v["overall_score"] == expected
    assert v["decision"] == "APPROVED", v["decision_reasons"]
    assert v["decided_by"] == "VERIFICATION_ENGINE" and v["engine_decision"] == "APPROVED"
    assert any("Overall score" in r for r in v["decision_reasons"])
    assert any("approval threshold" in r for r in v["decision_reasons"])
    snap = v["evidence_snapshot"]
    assert snap["soil_soc_pct"] == 2.4 and len(snap["image_sha256"]) == 64
    assert snap["ndvi_measurement"]["provenance"] == "SENTINEL2_COMPUTED"


def test_reported_ndvi_caps_decision_at_review(client, farmer):
    p = make_scored_plantation(client, farmer, soc=2.4, **TEST_NDVI)
    v = _verify(client, farmer, p["id"])
    assert v["ndvi_provenance"] == "REPORTED"
    assert v["overall_score"] >= 75
    assert v["decision"] == "REVIEW"
    assert any("auditor confirmation" in r for r in v["decision_reasons"])
    assert client.post(f"/api/plantations/{p['id']}/generate-credits", headers=farmer, json={}).status_code == 409


def test_non_plantation_photo_is_rejected(client, farmer, computed_ndvi):
    p = make_scored_plantation(client, farmer, kind="non_plantation", seed=3, soc=0.5)
    v = _verify(client, farmer, p["id"])
    assert v["ai_predicted_class"] == "non_plantation"
    assert v["decision"] in ("REJECTED", "REVIEW")
    assert v["decision"] != "APPROVED"
    assert v["risk_factors"], "a non-plantation photo must raise a risk factor"


def test_low_scores_rejected(client, farmer, monkeypatch):
    from app.services.ai import ndvi_service
    monkeypatch.setattr(ndvi_service.SatelliteClient, "query_satellite_ndvi", staticmethod(lambda **k: {
        "available": True, "mean_ndvi": 0.15, "min_ndvi": 0.05, "max_ndvi": 0.3, "vegetation_coverage_pct": 0.0,
        "source_label": "TEST FIXTURE (synthetic)", "acquisition_date": "2026-09-01"}))
    p = make_scored_plantation(client, farmer, kind="non_plantation", seed=5, soc=0.3)
    v = _verify(client, farmer, p["id"])
    assert v["overall_score"] < 55
    assert v["decision"] == "REJECTED"
    assert client.get(f"/api/plantations/{p['id']}", headers=farmer).json()["status"] == "REJECTED"


def test_invalid_image_url_is_not_accepted_as_evidence(client, farmer):
    r = client.post("/api/plantations", headers=farmer, json=plantation_payload(image_url="https://example.com/fake.jpg"))
    assert r.status_code == 422
    r = client.post("/api/plantations", headers=farmer, json=plantation_payload(image_url="/uploads/does-not-exist.jpg"))
    assert r.status_code == 422


def test_get_verification_is_read_only(client, farmer):
    p = client.post("/api/plantations", headers=farmer, json=plantation_payload()).json()
    v = client.get(f"/api/plantations/{p['id']}/verification", headers=farmer).json()
    assert v["id"] is None and v["is_persisted"] is False and v["decision"] == "PENDING"
    assert client.get(f"/api/plantations/{p['id']}/verifications", headers=farmer).json() == []


def test_evidence_change_resets_status_and_history_is_kept(client, farmer):
    p = make_scored_plantation(client, farmer, **TEST_NDVI)
    v1 = _verify(client, farmer, p["id"])
    assert v1["decision"] == "REVIEW"
    r = client.put(f"/api/plantations/{p['id']}/evidence", headers=farmer, json={"soil_soc_pct": 2.0})
    assert r.status_code == 200 and r.json()["status"] == "SUBMITTED"
    v2 = _verify(client, farmer, p["id"])
    history = client.get(f"/api/plantations/{p['id']}/verifications", headers=farmer).json()
    assert [h["id"] for h in history] == [v2["id"], v1["id"]]


def test_unit_engine_never_defaults_scores(monkeypatch):
    """Direct unit test: CV model failure → PENDING, no default CV score."""
    from app.models.plantation import Plantation
    from app.services import verification_engine as ve

    plantation = Plantation(id=999, latitude=12.9, longitude=77.5, area_hectares=1.0, tree_count=100,
                            image_url=None, soil_soc_pct=1.5)
    monkeypatch.setattr(ve.VerificationEngine, "check_evidence_completeness", classmethod(lambda cls, p: {
        "is_complete": True, "has_boundary": True, "has_ground_image": True, "ground_image_issue": None,
        "has_soil": True, "has_reported_ndvi": False, "image_path": "/nonexistent.jpg", "missing_modalities": [],
        "evidence_status": {"boundary": "PROVIDED", "ground_imagery": "PROVIDED", "soil_carbon": "PROVIDED", "satellite_ndvi": "PENDING"}}))
    monkeypatch.setattr(ve.NDVIService, "analyze_ndvi", staticmethod(lambda **k: {
        "available": True, "provenance": "SENTINEL2_COMPUTED", "is_real_satellite": True, "ndvi_value": 0.8,
        "mean_ndvi": 0.8, "min_ndvi": 0.7, "max_ndvi": 0.9, "vegetation_coverage_pct": 90.0, "ndvi_score": 89.0,
        "vegetation_status": "x", "satellite_source": "TEST", "acquisition_date": "2026-09-01"}))
    monkeypatch.setattr(ve, "_sha256", lambda p: None)
    res = ve.VerificationEngine.run_verification(plantation)
    assert res["decision"] == "PENDING"
    assert res["cv_score"] is None and res["overall_score"] is None
    assert "Ground photo analysis" in res["missing_evidence"]
