import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from ..database import Base

class TransactionStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    PENDING = "PENDING"
    CANCELLED = "CANCELLED"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)  # e.g., TXN-2026-0001
    credit_id = Column(String, ForeignKey("credits.id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    quantity_tco2e = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    
    status = Column(String, default=TransactionStatus.COMPLETED.value)
    payment_method = Column(String, default="PROTOTYPE_ESCROW_SIMULATION")
    certificate_id = Column(String, nullable=True)
    blockchain_tx_hash = Column(String, nullable=True)
    notes = Column(Text, default="Prototype Transaction — No Real Payment Processed")
    
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    credit = relationship("Credit", back_populates="transactions")
    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="transactions_as_buyer")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="transactions_as_seller")
