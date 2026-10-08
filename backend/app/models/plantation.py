import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from ..database import Base


class PlantationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"   # Registered; verification PENDING (evidence incomplete or not yet run)
    VERIFIED = "VERIFIED"     # Latest verification decision is APPROVED
    REVIEW = "REVIEW"         # Scored, but needs a human auditor decision
    REJECTED = "REJECTED"     # Latest verification decision is REJECTED


class Plantation(Base):
    __tablename__ = "plantations"
    __table_args__ = (
        CheckConstraint("area_hectares > 0", name="ck_plantation_area_positive"),
        CheckConstraint("tree_count > 0", name="ck_plantation_tree_count_positive"),
        CheckConstraint("plantation_age_years >= 0", name="ck_plantation_age_non_negative"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_plantation_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_plantation_longitude"),
    )

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    farmer_name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    area_hectares = Column(Float, nullable=False)
    plantation_age_years = Column(Float, nullable=False)
    tree_count = Column(Integer, nullable=False)
    tree_species = Column(String, nullable=False)
    plantation_type = Column(String, nullable=False)  # Agroforestry, Timber, Orchard, Mixed, Silvopasture
    sustainable_practice = Column(String, nullable=True)
    image_url = Column(String, nullable=True)

    # Soil evidence entered by the farmer (null until provided)
    soil_soc_pct = Column(Float, nullable=True)  # Soil Organic Carbon %
    soil_depth_cm = Column(Float, nullable=True)
    soil_type = Column(String, nullable=True)

    # Reported NDVI evidence (used only when the backend cannot compute NDVI from
    # Sentinel-2 itself). Must carry its source and acquisition date; null until provided.
    ndvi_reported_value = Column(Float, nullable=True)
    ndvi_reported_source = Column(String, nullable=True)
    ndvi_reported_date = Column(String, nullable=True)  # ISO date (YYYY-MM-DD)

    status = Column(String, nullable=False, default=PlantationStatus.SUBMITTED.value)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    farmer = relationship("User", back_populates="plantations")
    verifications = relationship("Verification", back_populates="plantation", cascade="all, delete-orphan")
    credits = relationship("Credit", back_populates="plantation", cascade="all, delete-orphan")
