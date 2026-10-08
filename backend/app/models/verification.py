import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from ..database import Base

class VerificationDecision(str, enum.Enum):
    APPROVED = "APPROVED"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"
    PENDING = "PENDING"

class Verification(Base):
    __tablename__ = "verifications"

    id = Column(String, primary_key=True, index=True)  # e.g., VER-2026-001
    plantation_id = Column(Integer, ForeignKey("plantations.id"), nullable=False)
    
    # Modality 1: Satellite / NDVI
    ndvi_value = Column(Float, nullable=True)  # Normalized Index (e.g., 0.76), null if pending
    ndvi_score = Column(Float, nullable=True)  # Scaled 0-100 (e.g., 82.0), null if pending
    ndvi_status = Column(String, nullable=False)  # "Healthy Vegetation", "PENDING", etc.
    ndvi_historical_diff = Column(Float, nullable=True)  # e.g. +5.2%
    
    # Modality 2: Computer Vision
    image_quality_score = Column(Float, nullable=True)  # 0-100, null if not provided
    vegetation_detection_score = Column(Float, nullable=True)  # 0-100, null if not provided
    cv_score = Column(Float, nullable=True)  # 0-100, null if not provided
    cv_detection_status = Column(String, nullable=False)  # "High Density Canopy Confirmed" or "NOT PROVIDED"
    
    # Modality 3: Soil / SOC
    soc_pct = Column(Float, nullable=True)  # Soil Organic Carbon %, null if not provided
    soc_score = Column(Float, nullable=True)  # 0-100, null if not provided
    soc_status = Column(String, nullable=False)  # "Rich Organic Baseline" or "NOT PROVIDED"
    
    # Formula Contributions & Final Score
    # Verification Score = 0.40 * NDVI + 0.35 * CV + 0.25 * SOC
    ndvi_weight = Column(Float, default=0.40)
    cv_weight = Column(Float, default=0.35)
    soc_weight = Column(Float, default=0.25)
    
    ndvi_contribution = Column(Float, nullable=True)
    cv_contribution = Column(Float, nullable=True)
    soc_contribution = Column(Float, nullable=True)
    
    overall_score = Column(Float, nullable=True)  # Final weighted score, null if incomplete evidence
    decision = Column(String, nullable=False)  # APPROVED, REVIEW, REJECTED, PENDING
    
    evidence_summary = Column(Text, nullable=True)
    limitations_disclaimer = Column(Text, nullable=True)
    # Modality 1: Satellite / NDVI Provenance
    is_real_satellite = Column(Boolean, default=False)
    satellite_source = Column(String, nullable=True)  # e.g. "REAL SATELLITE DATA (Sentinel-2 L2A)"
    acquisition_date = Column(String, nullable=True)
    mean_ndvi = Column(Float, nullable=True)
    min_ndvi = Column(Float, nullable=True)
    max_ndvi = Column(Float, nullable=True)
    vegetation_coverage_pct = Column(Float, nullable=True)

    # Modality 2: Computer Vision & Deep Learning AI
    ai_model_name = Column(String, default="MobileNetV3-Plantation-v1")
    ai_model_version = Column(String, default="1.0.0")
    ai_predicted_class = Column(String, nullable=True)
    ai_confidence_pct = Column(Float, nullable=True)
    image_phash = Column(String, nullable=True)

    # Risk & Fraud Engine Assessment
    risk_score = Column(Float, default=0.0)  # 0 to 100
    risk_level = Column(String, default="LOW")  # LOW, MEDIUM, HIGH
    risk_factors = Column(JSON, nullable=True)  # List of triggered factor strings
    risk_explanation = Column(Text, nullable=True)
    
    verified_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    plantation = relationship("Plantation", back_populates="verifications")
    credits = relationship("Credit", back_populates="verification")
