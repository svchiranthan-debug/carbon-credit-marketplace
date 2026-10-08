import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User, UserRole
from ..models.credit import Credit, CreditStatus
from ..models.plantation import Plantation
from ..models.transaction import Transaction, TransactionStatus
from ..models.audit_log import AuditLog
from ..schemas.schemas import PurchaseRequest, TransactionResponse, BlockchainRecordResponse
from ..services.blockchain_service import BlockchainService
from ..core.security import get_current_user, require_role

router = APIRouter(tags=["Transactions & Purchase Flow"])

@router.post("/marketplace/credits/{id}/purchase", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def purchase_carbon_credit(
    id: str,
    purchase_data: PurchaseRequest = PurchaseRequest(),
    current_user: User = Depends(require_role([UserRole.BUYER.value, UserRole.ADMIN.value])),
    db: Session = Depends(get_db)
):
    credit = db.query(Credit).filter(Credit.id == id).first()
    if not credit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carbon credit not found")
        
    if credit.status == CreditStatus.SOLD.value or credit.status == CreditStatus.RETIRED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This carbon credit is already SOLD or RETIRED and no longer available in the marketplace."
        )
        
    if credit.owner_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already own this carbon credit."
        )
        
    plantation = db.query(Plantation).filter(Plantation.id == credit.plantation_id).first()
    seller = db.query(User).filter(User.id == credit.owner_id).first()
    
    qty = purchase_data.quantity_tco2e or credit.carbon_quantity_tco2e
    total_inr = round(qty * credit.price_per_tco2e, 2)
    
    txn_id = f"TXN-2026-{uuid.uuid4().hex[:6].upper()}"
    cert_id = f"CERT-OFFSET-{uuid.uuid4().hex[:8].upper()}"
    
    # 1. Execute On-Chain Ownership Transfer on Smart Contract
    bc_res = BlockchainService.transfer_credit_on_chain(credit_id=credit.id)
    bc_tx_hash = bc_res.get("tx_hash")

    transaction = Transaction(
        id=txn_id,
        credit_id=credit.id,
        buyer_id=current_user.id,
        seller_id=credit.owner_id,
        quantity_tco2e=qty,
        unit_price=credit.price_per_tco2e,
        total_amount=total_inr,
        currency="INR",
        status=TransactionStatus.COMPLETED.value,
        payment_method="PROTOTYPE_INSTANT_ESCROW",
        certificate_id=cert_id,
        blockchain_tx_hash=bc_tx_hash,
        notes=f"Prototype Transaction — Transferred on-chain (Tx: {bc_tx_hash[:12]}...). Transferred to buyer portfolio.",
        timestamp=datetime.utcnow()
    )
    db.add(transaction)
    
    # 2. Update credit ownership & status
    credit.status = CreditStatus.SOLD.value
    credit.owner_id = current_user.id
    credit.blockchain_tx_hash = bc_tx_hash
    
    # 3. Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_role=current_user.role,
        action="CREDIT_PURCHASE_COMPLETED",
        target_type="Transaction",
        target_id=txn_id,
        details=f"Buyer '{current_user.email}' purchased Credit '{credit.id}' ({qty} tCO2e) from Seller '{seller.email if seller else 'Unknown'}' for ₹{total_inr}. On-Chain Tx: {bc_tx_hash}."
    )
    db.add(audit)
    db.commit()
    db.refresh(transaction)
    
    # Hydrate for response
    transaction.buyer_name = current_user.full_name
    transaction.seller_name = seller.full_name if seller else "Farmer"
    transaction.plantation_name = plantation.name if plantation else "Agroforestry Plot"
    
    return transaction

@router.post("/marketplace/credits/{id}/retire")
def retire_carbon_credit(
    id: str,
    current_user: User = Depends(require_role([UserRole.BUYER.value, UserRole.ADMIN.value])),
    db: Session = Depends(get_db)
):
    """
    Retires a carbon credit permanently on the smart contract and database.
    """
    credit = db.query(Credit).filter(Credit.id == id).first()
    if not credit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carbon credit not found")

    if credit.owner_id != current_user.id and current_user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the credit owner or auditor can retire this credit")

    if credit.is_retired or credit.status == CreditStatus.RETIRED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This credit is already retired and burned")

    # 1. Execute On-Chain Retirement on Smart Contract
    bc_res = BlockchainService.retire_credit_on_chain(credit_id=credit.id)
    retire_tx_hash = bc_res.get("tx_hash")

    # 2. Update Database Record
    now = datetime.utcnow()
    credit.is_retired = 1
    credit.status = CreditStatus.RETIRED.value
    credit.retired_at = now
    credit.blockchain_tx_hash = retire_tx_hash

    # 3. Audit Log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_role=current_user.role,
        action="CREDIT_RETIRED_ON_CHAIN",
        target_type="Credit",
        target_id=credit.id,
        details=f"Credit '{credit.id}' ({credit.carbon_quantity_tco2e} tCO2e) permanently retired on-chain by '{current_user.email}'. Tx: {retire_tx_hash}."
    )
    db.add(audit)
    db.commit()

    return {
        "success": True,
        "credit_id": credit.id,
        "carbon_quantity_tco2e": credit.carbon_quantity_tco2e,
        "status": "RETIRED",
        "blockchain_tx_hash": retire_tx_hash,
        "retired_at": now.isoformat(),
        "message": f"{credit.carbon_quantity_tco2e} tCO₂e Retired. Retired credits cannot be transferred or sold again."
    }

@router.get("/marketplace/credits/{id}/blockchain-record", response_model=BlockchainRecordResponse)
def get_blockchain_credit_record(
    id: str,
    db: Session = Depends(get_db)
):
    """
    Returns live on-chain audit and ownership state from the smart contract.
    """
    credit = db.query(Credit).filter(Credit.id == id).first()
    if not credit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carbon credit not found")

    on_chain = BlockchainService.get_on_chain_record(id)
    if on_chain:
        return BlockchainRecordResponse(
            credit_id=on_chain["credit_id"],
            plantation_id=on_chain["plantation_id"],
            carbon_quantity_tco2e=on_chain["carbon_quantity_tco2e"],
            report_hash=on_chain["report_hash"],
            owner_address=on_chain["owner_address"],
            issued_at_timestamp=on_chain["issued_at_timestamp"],
            is_retired=on_chain["is_retired"],
            retired_at_timestamp=on_chain["retired_at_timestamp"],
            contract_address=on_chain["contract_address"] or "0xC89Ce4735882C9F0f0FE26686c53074E09B0D550",
            transaction_hash=credit.blockchain_tx_hash or "0x" + uuid.uuid4().hex,
            status=on_chain["status"]
        )

    # Fallback to DB state
    return BlockchainRecordResponse(
        credit_id=credit.id,
        plantation_id=credit.plantation_id,
        carbon_quantity_tco2e=credit.carbon_quantity_tco2e,
        report_hash=credit.report_hash or BlockchainService.compute_report_hash(credit.verification_id),
        owner_address="0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1",
        issued_at_timestamp=int(credit.created_at.timestamp()) if credit.created_at else int(datetime.utcnow().timestamp()),
        is_retired=bool(credit.is_retired),
        retired_at_timestamp=int(credit.retired_at.timestamp()) if credit.retired_at else 0,
        contract_address=credit.blockchain_contract_address or BlockchainService._contract_address or "0xC89Ce4735882C9F0f0FE26686c53074E09B0D550",
        transaction_hash=credit.blockchain_tx_hash or "0x" + uuid.uuid4().hex,
        status="RETIRED" if credit.is_retired else "CONFIRMED"
    )

@router.get("/transactions", response_model=List[TransactionResponse])
def list_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == UserRole.ADMIN.value:
        txns = db.query(Transaction).order_by(Transaction.timestamp.desc()).all()
    elif current_user.role == UserRole.BUYER.value:
        txns = db.query(Transaction).filter(Transaction.buyer_id == current_user.id).order_by(Transaction.timestamp.desc()).all()
    else:
        txns = db.query(Transaction).filter(Transaction.seller_id == current_user.id).order_by(Transaction.timestamp.desc()).all()

    for t in txns:
        plantation = db.query(Plantation).join(Credit, Credit.plantation_id == Plantation.id).filter(Credit.id == t.credit_id).first()
        buyer = db.query(User).filter(User.id == t.buyer_id).first()
        seller = db.query(User).filter(User.id == t.seller_id).first()
        
        t.plantation_name = plantation.name if plantation else "Agroforestry Plot"
        t.buyer_name = buyer.full_name if buyer else "Buyer"
        t.seller_name = seller.full_name if seller else "Farmer"
        
    return txns
