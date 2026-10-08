import os
import pytest
from app.models.plantation import Plantation
from app.services.risk_engine import RiskEngine

def test_risk_engine_low_risk_scenario():
    plantation = Plantation(
        id=101,
        farmer_id=1,
        name="Consistent Agroforestry",
        area_hectares=2.5,
        tree_count=600,
        soil_soc_pct=1.8,
        soil_type="Loam",
        latitude=12.5,
        longitude=76.8
    )
    ndvi_res = {"mean_ndvi": 0.72, "ndvi_value": 0.72, "ndvi_score": 82.0}
    cv_res = {"predicted_class": "plantation", "confidence_pct": 94.0, "cv_score": 90.0}
    soc_res = {"soc_pct": 1.8, "soc_score": 75.0}

    risk = RiskEngine.evaluate_risk(plantation, ndvi_res, cv_res, soc_res)
    assert risk["risk_level"] == "LOW"
    assert risk["risk_score"] <= 30
    assert risk["requires_auditor_review"] is False
    assert len(risk["risk_factors"]) == 0

def test_risk_engine_high_risk_non_plantation():
    plantation = Plantation(
        id=102,
        farmer_id=1,
        name="Suspicious Concrete Submission",
        area_hectares=1.0,
        tree_count=300,
        soil_soc_pct=1.2,
        soil_type="Alluvial",
        latitude=13.0,
        longitude=77.5
    )
    ndvi_res = {"mean_ndvi": 0.75, "ndvi_value": 0.75, "ndvi_score": 85.0}
    cv_res = {"predicted_class": "non_plantation", "confidence_pct": 98.0, "cv_score": 15.0}
    soc_res = {"soc_pct": 1.2, "soc_score": 60.0}

    risk = RiskEngine.evaluate_risk(plantation, ndvi_res, cv_res, soc_res)
    assert risk["risk_level"] == "HIGH"
    assert risk["risk_score"] >= 61
    assert risk["requires_auditor_review"] is True
    assert any("Non-Plantation" in f for f in risk["risk_factors"])

def test_risk_engine_density_and_soc_anomalies():
    plantation = Plantation(
        id=103,
        farmer_id=2,
        name="Impossible Density Plot",
        area_hectares=0.5,
        tree_count=3000,  # 6000 trees/ha
        soil_soc_pct=7.5,  # Unrealistic 7.5% SOC
        soil_type="Red Sandy Loam",
        latitude=14.0,
        longitude=75.0
    )
    ndvi_res = {"mean_ndvi": 0.60, "ndvi_value": 0.60, "ndvi_score": 70.0}
    cv_res = {"predicted_class": "plantation", "confidence_pct": 85.0, "cv_score": 80.0}
    soc_res = {"soc_pct": 7.5, "soc_score": 90.0}

    risk = RiskEngine.evaluate_risk(plantation, ndvi_res, cv_res, soc_res)
    assert risk["risk_score"] >= 40
    assert any("density" in f.lower() for f in risk["risk_factors"])
    assert any("soil" in f.lower() or "soc" in f.lower() for f in risk["risk_factors"])
