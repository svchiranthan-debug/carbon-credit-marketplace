import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from ..database import Base

class CreditStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    SOLD = "SOLD"
    RESERVED = "RESERVED"
    RETIRED = "RETIRED"

class Credit(Base):
    __tablename__ = "credits"
    __table_args__ = (
        CheckConstraint("carbon_quantity_tco2e > 0", name="ck_credit_quantity_positive"),
        CheckConstraint("price_per_tco2e > 0", name="ck_credit_price_positive"),
    )

    id = Column(String, primary_key=True, index=True)  # e.g., CC-2026-001
    plantation_id = Column(Integer, ForeignKey("plantations.id"), nullable=False, unique=True)
    verification_id = Column(String, ForeignKey("verifications.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    carbon_quantity_tco2e = Column(Float, nullable=False)
    price_per_tco2e = Column(Float, nullable=False, default=1500.0)  # INR
    currency = Column(String, default="INR")
    status = Column(String, nullable=False, default=CreditStatus.AVAILABLE.value)
    
    # Estimation assumptions
    tree_count = Column(Integer, nullable=False)
    sequestration_rate = Column(Float, nullable=False)  # tCO2e/tree
    estimation_notes = Column(Text, nullable=True)
    
    # Blockchain audit layer (Ethereum-compatible)
    blockchain_tx_hash = Column(String, nullable=True)
    blockchain_contract_address = Column(String, nullable=True)
    # CONFIRMED (mined on the configured chain) | NOT_RECORDED (chain unavailable) | FAILED
    blockchain_status = Column(String, nullable=True)
    report_hash = Column(String, nullable=True)
    retirement_tx_hash = Column(String, nullable=True)  # Set only if the retirement was mined on-chain
    is_retired = Column(Integer, nullable=False, default=0)
    retired_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    plantation = relationship("Plantation", back_populates="credits")
    verification = relationship("Verification", back_populates="credits")
    owner = relationship("User", back_populates="credits_owned")
    transactions = relationship("Transaction", back_populates="credit")
