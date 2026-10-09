"""
Satellite / NDVI verification modality.

NDVI evidence can come from exactly two places, and every result records which one:

  SENTINEL2_COMPUTED  NDVI computed by this backend from real Sentinel-2 B04/B08 pixels.
  REPORTED            An NDVI value supplied with the submission together with its source
                      and acquisition date (e.g. read from Copernicus Browser / EO Browser).
                      Reported values are never auto-approved: they cap the decision at
                      REVIEW so a human auditor must confirm them.

If neither is available the modality is unavailable (all numbers null) and the
verification stays PENDING. No simulated NDVI is ever produced.
"""
from typing import Any, Dict, Optional

from .satellite_client import SatelliteClient, NDVI_FORMULA

PROVENANCE_COMPUTED = "SENTINEL2_COMPUTED"
PROVENANCE_REPORTED = "REPORTED"


def score_ndvi(mean_ndvi: float) -> Dict[str, Any]:
    """Map mean NDVI to a 0-100 modality score (piecewise linear, documented bands)."""
    if mean_ndvi >= 0.70:
        score = 80.0 + min(20.0, ((mean_ndvi - 0.70) / 0.22) * 20.0)
        status = "Healthy high-density canopy (NDVI >= 0.70)"
    elif mean_ndvi >= 0.50:
        score = 65.0 + ((mean_ndvi - 0.50) / 0.20) * 15.0
        status = "Moderate vegetation cover (NDVI 0.50-0.70)"
    elif mean_ndvi >= 0.35:
        score = 45.0 + ((mean_ndvi - 0.35) / 0.15) * 20.0
        status = "Sparse / developing vegetation (NDVI 0.35-0.50)"
    else:
        score = max(10.0, (max(0.0, mean_ndvi) / 0.35) * 45.0)
        status = "Degraded / low vegetation (NDVI < 0.35)"
    return {"ndvi_score": round(max(0.0, min(100.0, score)), 1), "vegetation_status": status}


class NDVIService:

    @staticmethod
    def analyze_ndvi(
        latitude: float,
        longitude: float,
        area_hectares: Optional[float] = None,
        boundary_lonlat=None,
        reported_value: Optional[float] = None,
        reported_source: Optional[str] = None,
        reported_date: Optional[str] = None,
        **_ignored: Any,
    ) -> Dict[str, Any]:
        sat = SatelliteClient.query_satellite_ndvi(
            latitude=latitude, longitude=longitude, area_hectares=area_hectares, boundary_lonlat=boundary_lonlat
        )

        if sat.get("available"):
            scored = score_ndvi(sat["mean_ndvi"])
            return {
                "available": True,
                "provenance": PROVENANCE_COMPUTED,
                "is_real_satellite": True,
                "ndvi_value": sat["mean_ndvi"],
                "mean_ndvi": sat["mean_ndvi"],
                "min_ndvi": sat["min_ndvi"],
                "max_ndvi": sat["max_ndvi"],
                "vegetation_coverage_pct": sat["vegetation_coverage_pct"],
                "valid_pixel_count": sat.get("valid_pixel_count"),
                "ndvi_score": scored["ndvi_score"],
                "vegetation_status": scored["vegetation_status"],
                "satellite_source": sat["source_label"],
                "acquisition_date": sat.get("acquisition_date"),
                "cloud_cover_pct": sat.get("cloud_cover_pct"),
                "clear_pixel_pct": sat.get("clear_pixel_pct"),
                "footprint_type": sat.get("footprint_type"),
                "scene_id": sat.get("scene_id"),
                "stac_item_url": sat.get("stac_item_url"),
                "data_source": sat.get("source"),
                "processing_baseline": sat.get("processing_baseline"),
                "search": sat.get("search"),
                "formula": NDVI_FORMULA,
                "satellite_note": None,
            }

        if reported_value is not None and reported_source and reported_date:
            scored = score_ndvi(reported_value)
            return {
                "available": True,
                "provenance": PROVENANCE_REPORTED,
                "is_real_satellite": False,
                "ndvi_value": round(float(reported_value), 3),
                "mean_ndvi": round(float(reported_value), 3),
                "min_ndvi": None,
                "max_ndvi": None,
                "vegetation_coverage_pct": None,
                "ndvi_score": scored["ndvi_score"],
                "vegetation_status": scored["vegetation_status"],
                "satellite_source": f"Reported NDVI — source: {reported_source}",
                "acquisition_date": reported_date,
                "formula": NDVI_FORMULA,
                "satellite_note": f"Backend NDVI computation unavailable: {sat.get('reason')}",
                "unavailable_reason": sat.get("reason"),
            }

        return {
            "available": False,
            "provenance": None,
            "is_real_satellite": False,
            "ndvi_value": None,
            "mean_ndvi": None,
            "min_ndvi": None,
            "max_ndvi": None,
            "vegetation_coverage_pct": None,
            "ndvi_score": None,
            "vegetation_status": "NOT AVAILABLE",
            "satellite_source": None,
            "acquisition_date": None,
            "formula": NDVI_FORMULA,
            "reason": sat.get("reason", "Satellite NDVI unavailable."),
            "unavailable_reason": sat.get("reason", "Satellite NDVI unavailable."),
        }
