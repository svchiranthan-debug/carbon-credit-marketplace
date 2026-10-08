"""Satellite NDVI: math, provenance and the 'never simulate' failure policy."""
import math

import numpy as np
import pytest
import requests

from app.config import settings
from app.services.ai import satellite_client as sc
from app.services.ai.ndvi_service import NDVIService, score_ndvi


def test_footprint_bbox_matches_area():
    bbox = sc.footprint_bbox(12.75, 75.2, 0.4047)  # 1 acre ≈ 63.6 m square
    height_m = (bbox[3] - bbox[1]) * 111_320
    width_m = (bbox[2] - bbox[0]) * 111_320 * math.cos(math.radians(12.75))
    assert abs(height_m - 63.6) < 1 and abs(width_m - 63.6) < 1


def test_reflectance_offset_and_nodata():
    dn = np.array([[0, 1000, 3000]], dtype=np.uint16)
    old = sc.dn_to_reflectance(dn, "03.01")
    new = sc.dn_to_reflectance(dn, "05.10")
    assert np.isnan(old[0, 0]) and np.isnan(new[0, 0])
    assert old[0, 2] == pytest.approx(0.30)
    assert new[0, 2] == pytest.approx(0.20)  # -1000 offset since baseline 04.00


def test_ndvi_formula_and_summary():
    red = np.array([[0.05, 0.10], [np.nan, 0.2]])
    nir = np.array([[0.45, 0.30], [0.4, 0.2]])
    ndvi = sc.compute_ndvi(red, nir)
    assert ndvi[0, 0] == pytest.approx(0.8)
    assert ndvi[0, 1] == pytest.approx(0.5)
    assert np.isnan(ndvi[1, 0])
    s = sc.summarize_ndvi(ndvi)
    assert s["valid_pixel_count"] == 3 and s["max_ndvi"] == 0.8
    assert sc.summarize_ndvi(np.full((2, 2), np.nan)) is None


def test_score_bands():
    assert score_ndvi(0.92)["ndvi_score"] == 100.0
    assert score_ndvi(0.70)["ndvi_score"] == 80.0
    assert score_ndvi(0.50)["ndvi_score"] == 65.0
    assert score_ndvi(0.0)["ndvi_score"] == 10.0


def test_disabled_queries_are_unavailable():
    res = sc.SatelliteClient.query_satellite_ndvi(12.5, 76.9, 1.0)
    assert res["available"] is False and "disabled" in res["reason"]
    assert "mean_ndvi" not in res


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_REAL_SATELLITE_QUERIES", True)


def test_network_error_is_unavailable(enabled, monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("offline")
    monkeypatch.setattr(sc.requests, "post", boom)
    res = sc.SatelliteClient.query_satellite_ndvi(12.5, 76.9, 1.0)
    assert res["available"] is False and "unreachable" in res["reason"]


class _Resp:
    def __init__(self, code, payload):
        self.status_code, self._p = code, payload

    def json(self):
        return self._p


SCENE = {"id": "S2B_TEST", "properties": {"eo:cloud_cover": 3.0, "datetime": "2026-09-01T05:00:00Z",
                                          "platform": "Sentinel-2B", "s2:processing_baseline": "05.11"},
         "assets": {"B04": {"href": "https://example/B04.tif"}, "B08": {"href": "https://example/B08.tif"}}}


def test_scene_found_but_bands_unreadable_is_unavailable_not_synthetic(enabled, monkeypatch):
    """The old code generated a random grid and labelled it REAL SATELLITE DATA here."""
    monkeypatch.setattr(sc.requests, "post", lambda *a, **k: _Resp(200, {"features": [SCENE]}))
    monkeypatch.setattr(sc.SatelliteClient, "_sign_href", classmethod(lambda cls, h: h + "?sig"))

    def fail(cls, href, bbox):
        raise OSError("HTTP range request failed")
    monkeypatch.setattr(sc.SatelliteClient, "_read_band_window", classmethod(fail))
    res = sc.SatelliteClient.query_satellite_ndvi(12.5, 76.9, 1.0)
    assert res["available"] is False
    assert "could not be read" in res["reason"]
    nd = NDVIService.analyze_ndvi(latitude=12.5, longitude=76.9, area_hectares=1.0)
    assert nd["ndvi_score"] is None and nd["provenance"] is None and nd["is_real_satellite"] is False


def test_real_band_pixels_produce_computed_provenance(enabled, monkeypatch):
    monkeypatch.setattr(sc.requests, "post", lambda *a, **k: _Resp(200, {"features": [SCENE]}))
    monkeypatch.setattr(sc.SatelliteClient, "_sign_href", classmethod(lambda cls, h: h + "?sig"))
    bands = {"B04": np.full((6, 6), 1500, dtype=np.uint16), "B08": np.full((6, 6), 5000, dtype=np.uint16)}
    monkeypatch.setattr(sc.SatelliteClient, "_read_band_window",
                        classmethod(lambda cls, href, bbox: bands["B04" if "B04" in href else "B08"]))
    nd = NDVIService.analyze_ndvi(latitude=12.5, longitude=76.9, area_hectares=1.0)
    # reflectance: red (1500-1000)/1e4=0.05, nir (5000-1000)/1e4=0.40 → NDVI 0.35/0.45
    assert nd["provenance"] == "SENTINEL2_COMPUTED" and nd["is_real_satellite"] is True
    assert nd["mean_ndvi"] == pytest.approx(0.778, abs=1e-3)
    assert nd["acquisition_date"] == "2026-09-01" and "S2B_TEST" in nd["satellite_source"]


def test_reported_ndvi_requires_source_and_date():
    nd = NDVIService.analyze_ndvi(latitude=1, longitude=1, reported_value=0.6)
    assert nd["available"] is False
    nd = NDVIService.analyze_ndvi(latitude=1, longitude=1, reported_value=0.6,
                                  reported_source="TEST FIXTURE", reported_date="2026-09-01")
    assert nd["provenance"] == "REPORTED" and nd["is_real_satellite"] is False and nd["ndvi_score"] is not None


def test_band_window_read_from_real_geotiff(tmp_path):
    """Exercises the rasterio windowed read on a local GeoTIFF (UTM 43N, 10 m pixels)."""
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin
    from rasterio.warp import transform as warp_transform

    lon, lat = 75.2, 12.75
    xs, ys = warp_transform("EPSG:4326", "EPSG:32643", [lon], [lat])
    origin_x, origin_y = xs[0] - 500, ys[0] + 500
    data = np.arange(100 * 100, dtype=np.uint16).reshape(100, 100) + 1
    path = tmp_path / "band.tif"
    with rasterio.open(path, "w", driver="GTiff", width=100, height=100, count=1, dtype="uint16",
                       crs="EPSG:32643", transform=from_origin(origin_x, origin_y, 10, 10)) as dst:
        dst.write(data, 1)

    bbox = sc.footprint_bbox(lat, lon, 0.4047)  # ~64 m square → ~6-7 pixels per side
    window = sc.SatelliteClient._read_band_window(str(path), bbox)
    assert 5 <= window.shape[0] <= 8 and 5 <= window.shape[1] <= 8
    # The window is centred on the plantation: pixel (50, 50) of the raster
    centre = data[50, 50]
    assert window.min() <= centre <= window.max()
