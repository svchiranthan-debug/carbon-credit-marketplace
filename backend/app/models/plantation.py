import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from ..database import Base

class PlantationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"

class Plantation(Base):
    __tablename__ = "plantations"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
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
    sustainable_practice = Column(String, nullable=True)  # Mulching, Organic, Drip irrigation, Intercropping
    image_url = Column(String, nullable=True)
    
    # Soil fields entered by farmer (nullable until evidence is submitted)
    soil_soc_pct = Column(Float, nullable=True)  # Soil Organic Carbon %
    soil_depth_cm = Column(Float, nullable=True)
    soil_type = Column(String, nullable=True)  # Loam, Clay, Sandy Loam, Black Soil, Red Soil, Alluvial
    
    # Status
    status = Column(String, nullable=False, default=PlantationStatus.DRAFT.value)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    farmer = relationship("User", back_populates="plantations")
    verifications = relationship("Verification", back_populates="plantation", cascade="all, delete-orphan")
    credits = relationship("Credit", back_populates="plantation", cascade="all, delete-orphan")
