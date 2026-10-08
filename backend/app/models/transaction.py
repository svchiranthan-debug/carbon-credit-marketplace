import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from ..database import Base

class TransactionStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    PENDING = "PENDING"
    CANCELLED = "CANCELLED"

class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("quantity_tco2e > 0", name="ck_txn_quantity_positive"),
        CheckConstraint("unit_price > 0", name="ck_txn_unit_price_positive"),
        CheckConstraint("buyer_id != seller_id", name="ck_txn_buyer_not_seller"),
    )

    id = Column(String, primary_key=True, index=True)  # e.g., TXN-2026-0001
    credit_id = Column(String, ForeignKey("credits.id"), nullable=False, index=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    quantity_tco2e = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    
    status = Column(String, default=TransactionStatus.COMPLETED.value)
    payment_method = Column(String, default="PROTOTYPE_ESCROW_SIMULATION")
    certificate_id = Column(String, nullable=True)
    blockchain_tx_hash = Column(String, nullable=True)  # Only set when the transfer was mined on-chain
    blockchain_status = Column(String, nullable=True)   # CONFIRMED | NOT_RECORDED | FAILED
    notes = Column(Text, default="Prototype transaction: no real payment was processed.")
    
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    credit = relationship("Credit", back_populates="transactions")
    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="transactions_as_buyer")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="transactions_as_seller")
