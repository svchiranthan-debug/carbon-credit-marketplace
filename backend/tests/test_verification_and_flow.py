import os
import pytest
from app.services.verification_engine import VerificationEngine
from app.services.carbon_engine import CarbonEngine
from app.models.plantation import Plantation, PlantationStatus
from app.models.verification import VerificationDecision
from app.core.security import get_password_hash, verify_password, create_access_token
from app.database import SessionLocal, Base, engine
from app.models.user import User, UserRole
from app.models.credit import Credit, CreditStatus
from app.models.transaction import Transaction

def test_password_hashing():
    raw_pwd = "Demo@123"
    hashed = get_password_hash(raw_pwd)
    assert hashed != raw_pwd
    assert verify_password(raw_pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

def test_verification_engine_formula_and_thresholds():
    # Test Approved Threshold >= 75.0
    p_high = Plantation(
        id=991,
        farmer_id=1,
        name="High Biomass Plot",
        farmer_name="Test Farmer",
        location="Karnataka",
        latitude=12.5,
        longitude=76.8,
        area_hectares=2.0,
        plantation_age_years=5.0,
        tree_count=600,
        tree_species="Teak, Bamboo",
        plantation_type="Agroforestry",
        sustainable_practice="Organic Mulching & Drip Irrigation",
        soil_soc_pct=2.2,
        soil_depth_cm=50.0,
        soil_type="Loam",
        status="SUBMITTED"
    )
    sample_plant_img = os.path.join(
        os.path.dirname(__file__), "..", "ml", "dataset", "train", "plantation", "plant_train_000.jpg"
    )
    sample_nonplant_img = os.path.join(
        os.path.dirname(__file__), "..", "ml", "dataset", "train", "non_plantation", "nonplant_train_000.jpg"
    )

    res_high = VerificationEngine.run_verification(p_high, custom_image_path=sample_plant_img)
    assert res_high["overall_score"] is not None
    assert res_high["overall_score"] >= 75.0
    assert res_high["decision"] in [VerificationDecision.APPROVED.value, VerificationDecision.REVIEW.value]
    
    # Check exact mathematical formula
    expected_score = round(
        (0.40 * res_high["ndvi_score"]) + 
        (0.35 * res_high["cv_score"]) + 
        (0.25 * res_high["soc_score"]), 
        1
    )
    assert res_high["overall_score"] == expected_score

    # Test Low/Rejected Threshold < 55.0
    p_low = Plantation(
        id=992,
        farmer_id=1,
        name="Depleted Barren Land",
        farmer_name="Test Farmer",
        location="Semi-Arid Zone",
        latitude=16.0,
        longitude=77.0,
        area_hectares=10.0,
        plantation_age_years=0.5,
        tree_count=30,  # Very sparse density
        tree_species="Acacia",
        plantation_type="Timber",
        sustainable_practice="Standard Maintenance",
        soil_soc_pct=0.3,
        soil_depth_cm=15.0,
        soil_type="Sandy",
        status="SUBMITTED"
    )
    res_low = VerificationEngine.run_verification(p_low, custom_image_path=sample_nonplant_img)
    assert res_low["overall_score"] is not None
    assert res_low["overall_score"] < 55.0
    assert res_low["decision"] == VerificationDecision.REJECTED.value

def test_carbon_engine_estimation():
    p = Plantation(
        id=993,
        farmer_id=1,
        name="Test Carbon Orchard",
        farmer_name="Farmer Ramesh",
        location="Mandya",
        latitude=12.5,
        longitude=76.8,
        area_hectares=2.0,
        plantation_age_years=4.0,
        tree_count=500,
        tree_species="Teak",
        plantation_type="Agroforestry",
        sustainable_practice="Organic Mulching & Drip Irrigation",
        soil_soc_pct=1.8,
        soil_depth_cm=40.0,
        soil_type="Loam",
        status=PlantationStatus.VERIFIED.value
    )
    
    estimate = CarbonEngine.calculate_estimate(p)
    assert estimate["tree_count"] == 500
    assert estimate["sequestration_rate_per_tree"] == 0.05
    # Species factor (Teak = 1.15) * Practice factor (1.10)
    expected_carbon = round(500 * 0.05 * 1.15 * 1.10, 1)
    assert estimate["estimated_carbon_tco2e"] == expected_carbon
    assert estimate["is_eligible_for_issuance"] is True

def test_unverified_plantation_carbon_ineligibility():
    p_unverified = Plantation(
        id=994,
        farmer_id=1,
        name="Pending Plot",
        farmer_name="Farmer",
        location="Location",
        latitude=12.0,
        longitude=76.0,
        area_hectares=1.0,
        plantation_age_years=1.0,
        tree_count=100,
        tree_species="Neem",
        plantation_type="Agroforestry",
        soil_soc_pct=1.0,
        soil_depth_cm=30.0,
        soil_type="Loam",
        status=PlantationStatus.SUBMITTED.value  # Not VERIFIED
    )
    estimate = CarbonEngine.calculate_estimate(p_unverified)
    assert estimate["is_eligible_for_issuance"] is False
