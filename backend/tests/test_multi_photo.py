"""Multi-photo ground evidence: upload rules, access control, per-photo inference, aggregation.

All images are SYNTHETIC test fixtures (ml/prepare_dataset.py), labelled by fixture_classifier.
They test the pipeline only and are not real plantation evidence.
"""
import io
import os
import time

import pytest
from PIL import Image

from app.config import settings
from app.services import photo_cv
from app.services.photo_store import sign_upload_url
from conftest import TEST_NDVI, plantation_payload, register, synthetic_image_bytes, upload_image


@pytest.fixture
def farmer(client):
    return register(client, "FARMER")[0]


def _plot(client, headers, **kw):
    r = client.post("/api/plantations", headers=headers, json=plantation_payload(**kw))
    assert r.status_code == 201, r.text
    return r.json()


def _upload(client, headers, pid, kind="plantation", seed=7, fmt="JPEG", data=None, name=None, mime=None):
    data = data if data is not None else synthetic_image_bytes(kind, seed, fmt)
    ext = {"JPEG": "jpg", "PNG": "png"}[fmt]
    return client.post(f"/api/plantations/{pid}/photos", headers=headers,
                       files={"file": (name or f"{kind}_{seed}.{ext}", data, mime or f"image/{ext.replace('jpg', 'jpeg')}")})


def _photos(client, headers, pid):
    r = client.get(f"/api/plantations/{pid}/photos", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _files_in_uploads():
    return set(os.listdir(settings.UPLOAD_DIR))


def _reencode_png(jpeg_bytes):
    """Same picture, different bytes (near-duplicate by perceptual hash, different SHA-256)."""
    buf = io.BytesIO()
    Image.open(io.BytesIO(jpeg_bytes)).save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- upload + listing

def test_one_and_multiple_photos_are_listed_with_signed_links(client, farmer):
    p = _plot(client, farmer)
    assert _photos(client, farmer, p["id"])["active_count"] == 0
    first = _upload(client, farmer, p["id"], seed=11)
    assert first.status_code == 201, first.text
    for seed in (12, 13):
        assert _upload(client, farmer, p["id"], seed=seed).status_code == 201
    listing = _photos(client, farmer, p["id"])
    assert listing["active_count"] == 3 and listing["max_photos"] == settings.MAX_PHOTOS_PER_PLANTATION
    for ph in listing["photos"]:
        assert ph["validation_status"] == "VALID" and ph["sha256"] and "sig=" in ph["url"]
        assert client.get(ph["url"]).status_code == 200
    # cover photo for single-photo clients = first photo
    plant = client.get(f"/api/plantations/{p['id']}", headers=farmer).json()
    assert plant["image_url"].split("?")[0] == listing["photos"][0]["url"].split("?")[0]


def test_photos_can_be_added_later_and_removed(client, farmer):
    p = _plot(client, farmer, image_url=upload_image(client, farmer, seed=21))   # legacy single-photo create
    assert _photos(client, farmer, p["id"])["active_count"] == 1
    added = _upload(client, farmer, p["id"], seed=22).json()
    assert _photos(client, farmer, p["id"])["active_count"] == 2
    before = _files_in_uploads()
    r = client.delete(f"/api/plantations/{p['id']}/photos/{added['id']}", headers=farmer)
    assert r.status_code == 200 and r.json()["active_count"] == 1
    assert _files_in_uploads() == before          # file is kept for audit, only withdrawn
    assert client.delete(f"/api/plantations/{p['id']}/photos/{added['id']}", headers=farmer).status_code == 404


def test_photo_count_limit(client, farmer, monkeypatch):
    monkeypatch.setattr(settings, "MAX_PHOTOS_PER_PLANTATION", 2)
    p = _plot(client, farmer)
    assert _upload(client, farmer, p["id"], seed=31).status_code == 201
    assert _upload(client, farmer, p["id"], seed=32).status_code == 201
    before = _files_in_uploads()
    r = _upload(client, farmer, p["id"], seed=33)
    assert r.status_code == 409 and "at most 2" in r.json()["detail"]
    assert _files_in_uploads() == before


def test_file_size_limit_leaves_no_file(client, farmer, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 2000)
    p = _plot(client, farmer)
    before = _files_in_uploads()
    r = _upload(client, farmer, p["id"], seed=34)
    assert r.status_code == 413
    assert _files_in_uploads() == before and _photos(client, farmer, p["id"])["active_count"] == 0


def test_invalid_types_and_partial_batch(client, farmer):
    """A batch of uploads where some fail: the good ones are stored, the bad ones leave nothing behind."""
    p = _plot(client, farmer)
    before = _files_in_uploads()
    results = [
        _upload(client, farmer, p["id"], seed=41),
        _upload(client, farmer, p["id"], data=b"%PDF-1.4 not an image", name="evil.jpg", mime="image/jpeg"),
        _upload(client, farmer, p["id"], data=b"hello", name="x.txt", mime="text/plain"),
        _upload(client, farmer, p["id"], data=synthetic_image_bytes("plantation", 42), name="../../etc/passwd.jpg"),
        _upload(client, farmer, p["id"], seed=43),
    ]
    assert [r.status_code for r in results] == [201, 400, 415, 201, 201]
    listing = _photos(client, farmer, p["id"])
    assert listing["active_count"] == 3
    assert all(".." not in ph["url"] for ph in listing["photos"])
    assert listing["photos"][1]["original_name"] == "passwd.jpg"     # client name sanitised, display only
    assert len(_files_in_uploads() - before) == 3
    assert not any(f.endswith(".part") for f in _files_in_uploads())


def test_exact_duplicate_rejected_near_duplicate_flagged(client, farmer):
    p = _plot(client, farmer)
    jpg = synthetic_image_bytes("plantation", 51)
    first = _upload(client, farmer, p["id"], data=jpg).json()
    again = _upload(client, farmer, p["id"], data=jpg)
    assert again.status_code == 409 and f"photo #{first['id']}" in again.json()["detail"]
    near = _upload(client, farmer, p["id"], data=_reencode_png(jpg), fmt="PNG")
    assert near.status_code == 201 and near.json()["duplicate_of_id"] == first["id"]


# ---------------------------------------------------------------- access control

def test_access_control(client, farmer):
    p = _plot(client, farmer)
    ph = _upload(client, farmer, p["id"], seed=61).json()
    other = register(client, "FARMER")[0]
    buyer = register(client, "BUYER")[0]
    auditor = register(client, "AUDITOR")[0]
    assert _upload(client, other, p["id"], seed=62).status_code == 403
    assert client.get(f"/api/plantations/{p['id']}/photos", headers=other).status_code == 403
    assert client.delete(f"/api/plantations/{p['id']}/photos/{ph['id']}", headers=other).status_code == 403
    assert client.get(f"/api/plantations/{p['id']}/photos", headers=buyer).status_code == 404   # not verified
    assert _upload(client, auditor, p["id"], seed=63).status_code == 403
    assert client.get(f"/api/plantations/{p['id']}/photos").status_code == 401
    assert _photos(client, auditor, p["id"])["active_count"] == 1

    url = ph["url"]
    path = url.split("?")[0]
    assert client.get(path).status_code == 403                                   # unsigned
    assert client.get(url.replace("sig=", "sig=0")).status_code == 403          # tampered
    expired = int(time.time()) - 10
    assert client.get(f"{path}?exp={expired}&sig=abc").status_code == 403       # expired
    assert client.get("/uploads/..%2F..%2Fapp%2Fconfig.py?exp=9999999999&sig=x").status_code in (403, 404)
    assert sign_upload_url("/uploads/../../etc/passwd") is None


# ---------------------------------------------------------------- verification

def _complete(client, headers, pid, **ndvi):
    r = client.put(f"/api/plantations/{pid}/evidence", headers=headers,
                   json={"soil_soc_pct": 2.4, "soil_depth_cm": 30, "soil_type": "Loam", **ndvi})
    assert r.status_code == 200, r.text


def _verify(client, headers, pid):
    r = client.post(f"/api/plantations/{pid}/verify", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_per_photo_results_are_persisted_and_snapshotted(client, farmer, computed_ndvi):
    p = _plot(client, farmer)
    for seed in (71, 72):
        _upload(client, farmer, p["id"], seed=seed)
    _complete(client, farmer, p["id"])
    v = _verify(client, farmer, p["id"])
    assert v["decision"] == "APPROVED", v["decision_reasons"]
    snap = v["evidence_snapshot"]
    assert len(snap["photos"]) == 2 and all(e["used_in_score"] for e in snap["photos"])
    agg = snap["cv_measurement"]["aggregation"]
    assert agg["photos_scored"] == 2 and agg["method"].startswith("lower median") and agg["flags"] == []
    for ph in _photos(client, farmer, p["id"])["photos"]:
        assert ph["predicted_class"] == "plantation" and ph["confidence_pct"] == 95.0 and ph["cv_score"] is not None
        assert ph["classified_at"] is not None


def test_conflicting_photos_cap_at_review_and_median_is_used(client, farmer, computed_ndvi):
    p = _plot(client, farmer)
    for kind, seed in (("plantation", 81), ("plantation", 82), ("non_plantation", 83)):
        assert _upload(client, farmer, p["id"], kind=kind, seed=seed).status_code == 201
    _complete(client, farmer, p["id"])
    v = _verify(client, farmer, p["id"])
    agg = v["evidence_snapshot"]["cv_measurement"]["aggregation"]
    scores = sorted(agg["per_photo_scores"])
    assert v["cv_score"] == scores[1]                 # lower median of three, not a sum or a max
    assert "CONFLICTING" in agg["flags"]
    assert v["decision"] == "REVIEW"
    assert any("disagree" in r for r in v["decision_reasons"])


def test_duplicates_count_once(client, farmer, computed_ndvi):
    """Two copies of a non-plantation photo + one plantation photo: the copy must not outvote."""
    p = _plot(client, farmer)
    np_jpg = synthetic_image_bytes("non_plantation", 91)
    _upload(client, farmer, p["id"], data=np_jpg, kind="non_plantation")
    _upload(client, farmer, p["id"], data=_reencode_png(np_jpg), fmt="PNG", kind="non_plantation")
    _upload(client, farmer, p["id"], seed=92)
    _complete(client, farmer, p["id"])
    v = _verify(client, farmer, p["id"])
    agg = v["evidence_snapshot"]["cv_measurement"]["aggregation"]
    assert agg["photos_submitted"] == 3 and agg["duplicates"] == 1 and agg["photos_scored"] == 2
    dup = [e for e in v["evidence_snapshot"]["photos"] if e["duplicate_of"]]
    assert len(dup) == 1 and dup[0]["used_in_score"] is False


def test_more_photos_cannot_replace_missing_soil_or_ndvi(client, farmer):
    auditor = register(client, "AUDITOR")[0]
    p = _plot(client, farmer)
    for seed in range(101, 106):
        _upload(client, farmer, p["id"], seed=seed)
    v = _verify(client, farmer, p["id"])
    assert v["decision"] == "PENDING" and v["missing_evidence"] == ["Soil carbon data"]
    _complete(client, farmer, p["id"])        # soil, but satellite disabled in tests and no reported NDVI
    v = _verify(client, farmer, p["id"])
    assert v["decision"] == "PENDING" and v["overall_score"] is None and v["missing_evidence"] == ["Satellite NDVI"]
    r = client.post(f"/api/admin/verifications/{v['id']}/decision", headers=auditor,
                    json={"decision": "APPROVED", "notes": "Lots of photos"})
    assert r.status_code == 400


def test_invalid_photo_does_not_count(client, farmer, computed_ndvi):
    """A photo file that disappears/corrupts after upload is listed as invalid and not scored."""
    p = _plot(client, farmer)
    good = _upload(client, farmer, p["id"], seed=111).json()
    bad = _upload(client, farmer, p["id"], seed=112).json()
    fname = bad["url"].split("?")[0].rsplit("/", 1)[-1]
    with open(os.path.join(settings.UPLOAD_DIR, fname), "wb") as f:
        f.write(b"corrupted")
    _complete(client, farmer, p["id"])
    v = _verify(client, farmer, p["id"])
    entries = {e["photo_id"]: e for e in v["evidence_snapshot"]["photos"]}
    assert entries[good["id"]]["used_in_score"] and not entries[bad["id"]]["valid"]
    assert v["evidence_snapshot"]["cv_measurement"]["aggregation"]["photos_scored"] == 1
    statuses = {ph["id"]: ph["validation_status"] for ph in _photos(client, farmer, p["id"])["photos"]}
    assert statuses[bad["id"]] == "INVALID"


def test_legacy_single_photo_plantation_without_photo_rows(client, farmer, computed_ndvi):
    """Plantations saved before multi-photo support have only image_url; they keep working."""
    from app.database import SessionLocal
    from app.models.plantation_photo import PlantationPhoto
    p = _plot(client, farmer, image_url=upload_image(client, farmer, seed=121))
    db = SessionLocal()
    db.query(PlantationPhoto).filter(PlantationPhoto.plantation_id == p["id"]).delete()
    db.commit()
    db.close()
    _complete(client, farmer, p["id"])
    v = _verify(client, farmer, p["id"])
    assert v["decision"] == "APPROVED" and v["evidence_snapshot"]["cv_measurement"]["aggregation"]["photos_scored"] == 1
    assert _photos(client, farmer, p["id"])["active_count"] == 1


def test_evidence_locked_after_credits(client, farmer, computed_ndvi):
    p = _plot(client, farmer)
    ph = _upload(client, farmer, p["id"], seed=131).json()
    _complete(client, farmer, p["id"])
    assert _verify(client, farmer, p["id"])["decision"] == "APPROVED"
    assert client.post(f"/api/plantations/{p['id']}/generate-credits", headers=farmer, json={}).status_code in (200, 201)
    assert _upload(client, farmer, p["id"], seed=132).status_code == 409
    assert client.delete(f"/api/plantations/{p['id']}/photos/{ph['id']}", headers=farmer).status_code == 409


# ---------------------------------------------------------------- aggregation unit tests

class _P:
    def __init__(self, pid, cls, conf, score, phash=None):
        self.id, self.filename, self.sha256, self.phash = pid, f"p{pid}.jpg", f"sha{pid}", phash
        self.uploaded_at = None
        self._r = {"available": True, "predicted_class": cls, "confidence_pct": conf, "cv_score": score,
                   "class_probabilities": {}, "model_name": "m", "model_version": "v", "prediction_label": cls,
                   "cv_detection_status": cls, "image_quality_score": 50, "vegetation_detection_score": conf}


def _assess(monkeypatch, photos):
    by_name = {p.filename: p._r for p in photos}
    monkeypatch.setattr(photo_cv, "upload_path", lambda f: f)
    monkeypatch.setattr(photo_cv, "validate_image_file", lambda path: (True, "", {}))
    monkeypatch.setattr(photo_cv.CVService, "analyze_image", staticmethod(lambda path: dict(by_name[path])))
    return photo_cv.assess_photos(photos)


def test_low_confidence_flag(monkeypatch):
    res = _assess(monkeypatch, [_P(1, "plantation", 55.0, 85.4), _P(2, "plantation", 52.0, 84.6), _P(3, "plantation", 90.0, 95.2)])
    assert res["cv_score"] == 85.4 and res["flags"] == ["LOW_CONFIDENCE"]


def test_all_unclear_photos_score_low_without_flags_hiding_it(monkeypatch):
    res = _assess(monkeypatch, [_P(1, "unclear_evidence", 90.0, 21.5), _P(2, "unclear_evidence", 88.0, 21.8)])
    assert res["cv_score"] == 21.5 and res["predicted_class"] == "unclear_evidence"


def test_one_good_photo_cannot_lift_bad_ones(monkeypatch):
    res = _assess(monkeypatch, [_P(1, "plantation", 95.0, 96.6), _P(2, "non_plantation", 90.0, 17.5),
                                _P(3, "unclear_evidence", 85.0, 22.3)])
    assert res["cv_score"] == 22.3 and "CONFLICTING" in res["flags"]


def test_no_scorable_photo_is_unavailable(monkeypatch):
    p = _P(1, "plantation", 95.0, 96.6)
    p._r = {"available": False, "reason": "ML model unavailable"}
    res = _assess(monkeypatch, [p])
    assert res["available"] is False and res["cv_score"] is None and "ML model" in res["reason"]
