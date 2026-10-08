"""
Shared test setup.

* Every test session runs against a fresh, throw-away SQLite database and uploads folder
  (the developer database backend/carbon_marketplace.db is never touched).
* Satellite queries are disabled and the blockchain is off by default, so tests are
  offline and deterministic. tests/test_blockchain_ganache.py turns the chain on when a
  Ganache node is reachable.
* A real uvicorn server is started in a background thread for HTTP-level tests; its base
  URL is exposed as the ``api_base`` fixture (and CCM_API_BASE env var).

All images and NDVI values created by tests are SYNTHETIC TEST FIXTURES.
"""
import io
import os
import socket
import sys
import tempfile
import threading
import time
import uuid

_TMP = tempfile.mkdtemp(prefix="ccm-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'test.db')}"
os.environ["UPLOAD_DIR"] = os.path.join(_TMP, "uploads")
os.environ["ENABLE_REAL_SATELLITE_QUERIES"] = "false"
os.environ.setdefault("ENABLE_BLOCKCHAIN", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import pytest  # noqa: E402
import requests  # noqa: E402
import uvicorn  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from seed_data import seed  # noqa: E402

seed()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def api_base():
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}/api"
    for _ in range(100):
        try:
            if requests.get(f"{base}/health", timeout=1).status_code == 200:
                break
        except requests.RequestException:
            time.sleep(0.1)
    os.environ["CCM_API_BASE"] = base
    yield base
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


# ---------------------------------------------------------------- helpers
def synthetic_image_bytes(kind: str = "plantation", seed: int = 7, fmt: str = "JPEG") -> bytes:
    """SYNTHETIC test image from ml/prepare_dataset.py (not a real photograph)."""
    from ml.prepare_dataset import generate_non_plantation_image, generate_plantation_image
    gen = generate_plantation_image if kind == "plantation" else generate_non_plantation_image
    buf = io.BytesIO()
    gen(seed, (320, 320)).save(buf, format=fmt)
    return buf.getvalue()


def register(client, role: str, name: str = "Test User"):
    email = f"{role.lower()}_{uuid.uuid4().hex[:10]}@test.example"
    r = client.post("/api/auth/register", json={
        "email": email, "password": "TestPass@123", "full_name": name, "role": role,
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]


def login(client, email: str, password: str = "Demo@123"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


_coord_counter = [0]


def unique_coords():
    """Distinct coordinates per call so geospatial-overlap risk checks don't fire across tests."""
    _coord_counter[0] += 1
    n = _coord_counter[0]
    return 12.0 + (n % 90) * 0.01, 76.0 + (n // 90) * 0.01 + (n % 7) * 0.001


def plantation_payload(**overrides):
    lat, lon = unique_coords()
    data = {
        "name": f"Test Areca Plot {uuid.uuid4().hex[:6]}",
        "location": "Test Village, Karnataka, India",
        "latitude": lat,
        "longitude": lon,
        "area_hectares": 0.4047,
        "plantation_age_years": 6.0,
        "tree_count": 450,
        "tree_species": "Areca",
        "plantation_type": "Agroforestry",
    }
    data.update(overrides)
    return data


def upload_image(client, headers, kind="plantation", seed=7):
    r = client.post("/api/plantations/upload-image", headers=headers,
                    files={"file": (f"{kind}_{seed}.jpg", synthetic_image_bytes(kind, seed), "image/jpeg")})
    assert r.status_code == 200, r.text
    return r.json()["image_url"]


# Clearly-labelled synthetic reported NDVI used where a test needs NDVI without network access.
TEST_NDVI = {
    "ndvi_reported_value": 0.78,
    "ndvi_reported_source": "TEST FIXTURE (synthetic value, not a real measurement)",
    "ndvi_reported_date": "2026-09-01",
}


@pytest.fixture
def computed_ndvi(monkeypatch):
    """Patch the satellite client to return a SYNTHETIC 'computed' NDVI (tests only)."""
    from app.services.ai import ndvi_service

    def fake(latitude, longitude, area_hectares=None, **_):
        return {
            "available": True, "mean_ndvi": 0.80, "min_ndvi": 0.62, "max_ndvi": 0.91,
            "vegetation_coverage_pct": 95.0, "valid_pixel_count": 36,
            "source_label": "TEST FIXTURE Sentinel-2 scene (synthetic)", "scene_id": "TEST",
            "acquisition_date": "2026-09-01", "cloud_cover_pct": 1.0,
        }

    monkeypatch.setattr(ndvi_service.SatelliteClient, "query_satellite_ndvi", staticmethod(fake))


def make_scored_plantation(client, farmer_headers, kind="plantation", seed=7, soc=2.4, **overrides):
    """Creates a plantation with photo + soil evidence. NDVI is supplied by the caller (fixture or reported)."""
    image_url = upload_image(client, farmer_headers, kind, seed)
    r = client.post("/api/plantations", headers=farmer_headers, json=plantation_payload(
        image_url=image_url, soil_soc_pct=soc, soil_depth_cm=30, soil_type="Loam", **overrides))
    assert r.status_code == 201, r.text
    return r.json()
