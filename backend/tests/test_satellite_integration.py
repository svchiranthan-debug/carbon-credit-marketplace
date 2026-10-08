import pytest
from app.services.ai.satellite_client import SatelliteClient
from app.services.ai.ndvi_service import NDVIService

def test_satellite_bounding_box_generation():
    # Centroid fallback
    bbox = SatelliteClient.get_bounding_box(latitude=12.5, longitude=76.8, boundary_coords=None)
    assert len(bbox) == 4
    assert bbox[0] < bbox[2]  # min_lon < max_lon
    assert bbox[1] < bbox[3]  # min_lat < max_lat

    # Explicit polygon boundary
    polygon = [
        [12.501, 76.801],
        [12.509, 76.801],
        [12.509, 76.809],
        [12.501, 76.809]
    ]
    poly_bbox = SatelliteClient.get_bounding_box(latitude=12.505, longitude=76.805, boundary_coords=polygon)
    assert len(poly_bbox) == 4
    assert poly_bbox[0] <= 76.801
    assert poly_bbox[2] >= 76.809
    assert poly_bbox[1] <= 12.501
    assert poly_bbox[3] >= 12.509

def test_ndvi_calculation_and_statistics():
    res = NDVIService.analyze_ndvi(
        latitude=12.52,
        longitude=76.89,
        area_hectares=3.0,
        tree_count=600,
        plantation_age_years=4.0
    )
    assert "mean_ndvi" in res
    assert "min_ndvi" in res
    assert "max_ndvi" in res
    assert "vegetation_coverage_pct" in res
    assert "ndvi_score" in res
    assert 0.0 <= res["ndvi_score"] <= 100.0
    assert "provenance_type" in res
    assert res["provenance_type"] in ["REAL SATELLITE DATA", "DEMO/PROTOTYPE DATA"]
    assert "band_breakdown" in res
    assert "near_infrared_b8" in res["band_breakdown"]
    assert "red_band_b4" in res["band_breakdown"]

def test_prototype_fallback_honest_labeling():
    bbox = [76.0, 12.0, 76.01, 12.01]
    fallback = SatelliteClient._generate_prototype_fallback(
        latitude=12.0,
        longitude=76.0,
        bbox=bbox,
        reason="Forced simulation test"
    )
    assert fallback["is_real_satellite"] is False
    assert fallback["provenance_type"] == "DEMO/PROTOTYPE DATA"
    assert "SIMULATION" in fallback["data_source"]
    assert fallback["mean_ndvi"] > 0
