"""Planetary Computer access: SAS tokens, retries, timeouts, expired signatures, scene search.

All HTTP is mocked and all rasters are small synthetic GeoTIFFs written by the tests. They test
the algorithm and the failure handling only; none of them is a real satellite observation.
"""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
import requests

from app.config import settings
from app.services.ai import satellite_client as sc
from app.services.ai.ndvi_service import NDVIService
from test_satellite_ndvi import LAT, LON, _Resp, _scene, _write_tiles

GOOD_TOKEN = "st=2026&se=2026&sp=rl&sig=SECRETSIG"


def _token_body(minutes=60, token=GOOD_TOKEN):
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"msft:expiry": expiry, "token": token}


class FakePC:
    """Stub for requests.request: scripted responses for the STAC search and the token service."""

    def __init__(self, scenes=None, token_responses=None, stac_responses=None):
        self.scenes = scenes or []
        self.token_responses = list(token_responses or [])
        self.stac_responses = list(stac_responses or [])
        self.token_calls = 0
        self.stac_calls = 0
        self.stac_payloads = []

    def __call__(self, method, url, **kw):
        if url.endswith("/search"):
            self.stac_calls += 1
            self.stac_payloads.append(kw.get("json"))
            if self.stac_responses:
                r = self.stac_responses.pop(0)
                if isinstance(r, Exception):
                    raise r
                return r
            return _Resp(200, {"features": self.scenes})
        if "/sas/" in url:
            self.token_calls += 1
            if self.token_responses:
                r = self.token_responses.pop(0)
                if isinstance(r, Exception):
                    raise r
                return r
            return _Resp(200, _token_body())
        raise AssertionError(f"unexpected URL {url}")


@pytest.fixture
def pc(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_REAL_SATELLITE_QUERIES", True)
    monkeypatch.setattr(settings, "SATELLITE_MAX_ATTEMPTS", 3)
    sleeps = []
    monkeypatch.setattr(sc.time, "sleep", lambda s: sleeps.append(s))
    sc.SatelliteClient.reset_token_cache()

    def install(fake):
        monkeypatch.setattr(sc.requests, "request", fake)
        fake.sleeps = sleeps
        return fake

    yield install
    sc.SatelliteClient.reset_token_cache()


@pytest.fixture
def clear_tiles(tmp_path):
    red = np.full((100, 100), 1500, dtype=np.uint16)   # reflectance 0.05
    nir = np.full((100, 100), 5000, dtype=np.uint16)   # reflectance 0.40
    scl = np.full((50, 50), 4, dtype=np.uint8)          # vegetation, no cloud
    return _write_tiles(tmp_path, red, nir, scl)


def _local_reads(monkeypatch, seen_hrefs=None):
    """Band reads go to the local fixture file: strip the SAS query the client appended."""
    real = sc.SatelliteClient._read_window.__func__

    def read(cls, href, footprint, out_shape=None):
        if seen_hrefs is not None:
            seen_hrefs.append(href)
        return real(cls, href.split("?")[0], footprint, out_shape)

    monkeypatch.setattr(sc.SatelliteClient, "_read_window", classmethod(read))


# ---------------------------------------------------------------- success path

def test_full_chain_signs_reads_and_records_provenance(pc, monkeypatch, clear_tiles):
    fake = pc(FakePC(scenes=[_scene(clear_tiles)]))
    seen = []
    _local_reads(monkeypatch, seen)
    nd = NDVIService.analyze_ndvi(latitude=LAT, longitude=LON, area_hectares=1.0)
    assert nd["provenance"] == "SENTINEL2_COMPUTED"
    assert nd["mean_ndvi"] == pytest.approx(0.778, abs=1e-3)   # (0.40-0.05)/(0.40+0.05)
    assert nd["scene_id"] == "S2B_TEST" and nd["acquisition_date"] == "2026-09-01"
    assert nd["stac_item_url"].endswith("/collections/sentinel-2-l2a/items/S2B_TEST")
    assert nd["search"]["lookback_days"] == settings.SATELLITE_LOOKBACK_DAYS
    # one token for all three bands, appended to every band URL
    assert fake.token_calls == 1
    assert len(seen) == 3 and all(h.endswith("?" + GOOD_TOKEN) for h in seen)


def test_search_uses_the_plot_polygon_and_configured_filters(pc, monkeypatch, clear_tiles):
    monkeypatch.setattr(settings, "SATELLITE_LOOKBACK_DAYS", 30)
    monkeypatch.setattr(settings, "SATELLITE_MAX_SCENE_CLOUD_PCT", 10.0)
    fake = pc(FakePC(scenes=[]))
    d = 0.0005
    tri = [[LON - d, LAT], [LON + d, LAT], [LON, LAT + d], [LON - d, LAT]]
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 0.3, boundary_lonlat=tri)
    body = fake.stac_payloads[0]
    assert body["intersects"] == {"type": "Polygon", "coordinates": [tri]}
    assert body["query"] == {"eo:cloud_cover": {"lt": 10.0}}
    start, end = body["datetime"].split("/")
    days = (datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(start.replace("Z", "+00:00"))).days
    assert days == 30
    assert res["available"] is False and "No Sentinel-2 L2A scene" in res["reason"] and "10%" in res["reason"]


def test_token_is_cached_across_scenes_and_refreshed_near_expiry(pc):
    fake = pc(FakePC(token_responses=[_Resp(200, _token_body(60)), _Resp(200, _token_body(3)), _Resp(200, _token_body(60))]))
    t1 = sc.SatelliteClient.get_sas_token()
    assert sc.SatelliteClient.get_sas_token() == t1 and fake.token_calls == 1
    sc.SatelliteClient.get_sas_token(force_refresh=True)          # gets the 3-minute token
    sc.SatelliteClient.get_sas_token()                            # < 5 min left → refreshed
    assert fake.token_calls == 3


# ---------------------------------------------------------------- token service failures

def test_token_504_then_200_is_retried_and_succeeds(pc, monkeypatch, clear_tiles):
    fake = pc(FakePC(scenes=[_scene(clear_tiles)], token_responses=[_Resp(504), _Resp(200, _token_body())]))
    _local_reads(monkeypatch)
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"], res.get("reason")
    assert fake.token_calls == 2 and fake.sleeps == [settings.SATELLITE_RETRY_BACKOFF_S]


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_token_transient_errors_give_up_after_bounded_retries(pc, clear_tiles, code):
    s2 = _scene(clear_tiles)
    s2b = dict(s2, id="S2B_OTHER")
    fake = pc(FakePC(scenes=[s2, s2b], token_responses=[_Resp(code)] * 10))
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"] is False
    assert f"token service: HTTP {code} after 3 attempts" in res["reason"]
    assert "could not be authorised" in res["reason"]
    assert fake.token_calls == 3          # not retried again for the second scene
    nd = NDVIService.analyze_ndvi(latitude=LAT, longitude=LON, area_hectares=1.0)
    assert nd["provenance"] is None and nd["ndvi_score"] is None


def test_retry_after_header_is_honoured_and_capped(pc, clear_tiles):
    fake = pc(FakePC(scenes=[_scene(clear_tiles)],
                     token_responses=[_Resp(429, headers={"Retry-After": "3"}), _Resp(429, headers={"Retry-After": "999"}), _Resp(429)]))
    sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert fake.sleeps == [3.0, sc.MAX_RETRY_AFTER_S]


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_token_permanent_errors_are_not_retried(pc, clear_tiles, code):
    fake = pc(FakePC(scenes=[_scene(clear_tiles)], token_responses=[_Resp(code)] * 3))
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"] is False and f"HTTP {code}" in res["reason"] and "not retried" in res["reason"]
    assert fake.token_calls == 1 and fake.sleeps == []


def test_token_timeout_is_reported(pc, clear_tiles):
    fake = pc(FakePC(scenes=[_scene(clear_tiles)], token_responses=[requests.Timeout()] * 3))
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"] is False and "timed out" in res["reason"] and fake.token_calls == 3


@pytest.mark.parametrize("body", [{}, {"token": ""}, {"token": "x", "msft:expiry": "2020-01-01T00:00:00Z"}])
def test_token_response_without_usable_token(pc, clear_tiles, body):
    pc(FakePC(scenes=[_scene(clear_tiles)], token_responses=[_Resp(200, body)]))
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"] is False and "token" in res["reason"]


# ---------------------------------------------------------------- STAC search failures

def test_stac_5xx_is_retried(pc, monkeypatch, clear_tiles):
    fake = pc(FakePC(scenes=[_scene(clear_tiles)], stac_responses=[_Resp(503), requests.ConnectionError()]))
    _local_reads(monkeypatch)
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"] and fake.stac_calls == 3


def test_stac_bad_request_is_not_retried(pc):
    fake = pc(FakePC(stac_responses=[_Resp(400)]))
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"] is False and "HTTP 400" in res["reason"] and fake.stac_calls == 1


def test_stac_unreachable_after_retries(pc):
    fake = pc(FakePC(stac_responses=[requests.ConnectionError()] * 3))
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"] is False and "catalogue unreachable" in res["reason"] and fake.stac_calls == 3


# ---------------------------------------------------------------- band access failures

def test_expired_signature_403_refreshes_token_once(pc, monkeypatch, clear_tiles):
    fake = pc(FakePC(scenes=[_scene(clear_tiles)]))
    real = sc.SatelliteClient._read_window.__func__
    calls = {"n": 0}

    def read(cls, href, footprint, out_shape=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError(f"HTTP response code: 403 for {href}")
        return real(cls, href.split("?")[0], footprint, out_shape)

    monkeypatch.setattr(sc.SatelliteClient, "_read_window", classmethod(read))
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"], res.get("reason")
    assert fake.token_calls == 2


def test_persistent_403_is_reported_without_leaking_the_signature(pc, monkeypatch, clear_tiles):
    fake = pc(FakePC(scenes=[_scene(clear_tiles)]))

    def read(cls, href, footprint, out_shape=None):
        raise OSError(f"HTTP response code: 403 for {href}")

    monkeypatch.setattr(sc.SatelliteClient, "_read_window", classmethod(read))
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"] is False and "403" in res["reason"]
    assert "SECRETSIG" not in res["reason"] and "<signature removed>" in res["reason"]
    assert fake.token_calls == 2   # initial token + exactly one refresh


def test_failed_download_is_unavailable(pc, monkeypatch, clear_tiles):
    pc(FakePC(scenes=[_scene(clear_tiles)]))

    def read(cls, href, footprint, out_shape=None):
        raise OSError("CURL error: Connection timed out")

    monkeypatch.setattr(sc.SatelliteClient, "_read_window", classmethod(read))
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"] is False and "Band read failed" in res["reason"]


def test_missing_red_band(pc, clear_tiles):
    tiles = dict(clear_tiles)
    tiles.pop("B04")
    pc(FakePC(scenes=[_scene(tiles)]))
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"] is False and "B04/B08" in res["reason"]


def test_corrupt_raster_is_unavailable(pc, monkeypatch, tmp_path, clear_tiles):
    bad = tmp_path / "corrupt.tif"
    bad.write_bytes(b"not a tiff at all")
    tiles = dict(clear_tiles, B08=str(bad))
    pc(FakePC(scenes=[_scene(tiles)]))
    _local_reads(monkeypatch)
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"] is False and "Band read failed" in res["reason"]


def test_nodata_pixels_only_is_unavailable(pc, monkeypatch, tmp_path):
    red = np.zeros((100, 100), dtype=np.uint16)        # DN 0 = no-data
    nir = np.zeros((100, 100), dtype=np.uint16)
    scl = np.full((50, 50), 4, dtype=np.uint8)
    pc(FakePC(scenes=[_scene(_write_tiles(tmp_path, red, nir, scl))]))
    _local_reads(monkeypatch)
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"] is False and "no-data" in res["reason"]


def test_plot_outside_the_scene_is_unavailable(pc, monkeypatch, clear_tiles):
    pc(FakePC(scenes=[_scene(clear_tiles)]))
    _local_reads(monkeypatch)
    res = sc.SatelliteClient.query_satellite_ndvi(LAT + 1.0, LON, 1.0)   # ~110 km away from the tile
    assert res["available"] is False


def test_all_clouds_tries_next_scene(pc, monkeypatch, tmp_path, clear_tiles):
    cloudy_dir = tmp_path / "cloudy"
    cloudy_dir.mkdir()
    cloudy = _write_tiles(cloudy_dir, np.full((100, 100), 1500, np.uint16), np.full((100, 100), 5000, np.uint16),
                          np.full((50, 50), 9, np.uint8))
    s_cloudy = dict(_scene(cloudy), id="S2_CLOUDY")
    s_cloudy["properties"] = dict(s_cloudy["properties"], **{"eo:cloud_cover": 1.0})
    pc(FakePC(scenes=[s_cloudy, _scene(clear_tiles)]))
    _local_reads(monkeypatch)
    res = sc.SatelliteClient.query_satellite_ndvi(LAT, LON, 1.0)
    assert res["available"] and res["scene_id"] == "S2B_TEST"


# ---------------------------------------------------------------- verification integrity

def test_unavailable_ndvi_keeps_verification_pending_with_reason(client, monkeypatch):
    """Complete evidence + failing token service → PENDING, provenance UNAVAILABLE, no credits."""
    from conftest import make_scored_plantation, register
    monkeypatch.setattr(settings, "ENABLE_REAL_SATELLITE_QUERIES", True)
    monkeypatch.setattr(sc.time, "sleep", lambda s: None)
    sc.SatelliteClient.reset_token_cache()
    scene = _scene({"B04": "https://x/B04.tif", "B08": "https://x/B08.tif", "SCL": "https://x/SCL.tif"})
    monkeypatch.setattr(sc.requests, "request", FakePC(scenes=[scene], token_responses=[_Resp(504)] * 3))
    farmer = register(client, "FARMER")[0]
    p = make_scored_plantation(client, farmer)
    v = client.post(f"/api/plantations/{p['id']}/verify", headers=farmer).json()
    assert v["decision"] == "PENDING" and v["overall_score"] is None and v["ndvi_provenance"] is None
    assert v["evidence_status"]["satellite_ndvi"] == "UNAVAILABLE"
    snap = v["evidence_snapshot"]["ndvi_measurement"]
    assert snap["provenance"] == "UNAVAILABLE" and "HTTP 504 after 3 attempts" in snap["unavailable_reason"]
    assert client.post(f"/api/plantations/{p['id']}/generate-credits", headers=farmer, json={}).status_code == 409
    sc.SatelliteClient.reset_token_cache()


def test_computed_ndvi_snapshot_records_scene(client, monkeypatch, computed_ndvi):
    from conftest import make_scored_plantation, register
    farmer = register(client, "FARMER")[0]
    p = make_scored_plantation(client, farmer)
    v = client.post(f"/api/plantations/{p['id']}/verify", headers=farmer).json()
    snap = v["evidence_snapshot"]["ndvi_measurement"]
    assert snap["provenance"] == "SENTINEL2_COMPUTED" and snap["scene_id"] == "TEST"
    assert snap["acquisition_date"] == "2026-09-01" and snap["mean_ndvi"] == 0.8
