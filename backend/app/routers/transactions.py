import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.security import get_current_user, require_role
from ..database import get_db
from ..models.audit_log import AuditLog
from ..models.credit import Credit, CreditStatus
from ..models.plantation import Plantation
from ..models.transaction import Transaction, TransactionStatus
from ..models.user import User, UserRole
from ..schemas.schemas import BlockchainRecordResponse, PurchaseRequest, TransactionResponse
from ..services.blockchain_service import STATUS_CONFIRMED, STATUS_NOT_RECORDED, BlockchainService
from ..services.marketplace_rules import listing_check

router = APIRouter(tags=["Transactions & Purchase Flow"])

QTY_TOLERANCE = 1e-6


def _claim(db: Session, credit_id: str, from_status: str, to_status: str) -> bool:
    """Atomic compare-and-set on credit status; prevents double purchase / double retirement."""
    updated = (
        db.query(Credit)
        .filter(Credit.id == credit_id, Credit.status == from_status)
        .update({Credit.status: to_status}, synchronize_session=False)
    )
    db.commit()
    return updated == 1


@router.post("/marketplace/credits/{id}/purchase", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def purchase_carbon_credit(
    id: str,
    purchase_data: Optional[PurchaseRequest] = None,
    current_user: User = Depends(require_role([UserRole.BUYER.value])),
    db: Session = Depends(get_db),
):
    credit = db.query(Credit).filter(Credit.id == id).first()
    if not credit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Carbon credit {id} not found")

    if credit.owner_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already own this carbon credit.")

    listed, reason = listing_check(credit, db)
    if not listed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Credit is not available for purchase: {reason}")

    lot = credit.carbon_quantity_tco2e
    qty = purchase_data.quantity_tco2e if purchase_data and purchase_data.quantity_tco2e is not None else lot
    if qty > lot + QTY_TOLERANCE:
        raise HTTPException(
            status_code=422,
            detail=f"Requested {qty} tCO2e exceeds the {lot} tCO2e available in this lot.",
        )
    if abs(qty - lot) > QTY_TOLERANCE:
        raise HTTPException(
            status_code=422,
            detail=f"Credits are sold as whole lots. This lot is {lot} tCO2e; partial purchases are not supported.",
        )

    seller_id = credit.owner_id
    if not _claim(db, credit.id, CreditStatus.AVAILABLE.value, CreditStatus.RESERVED.value):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This credit was just purchased by someone else.")

    try:
        if credit.blockchain_status == STATUS_CONFIRMED:
            bc = BlockchainService.transfer_credit_on_chain(credit.id, new_owner_user_id=current_user.id)
            if bc["status"] != STATUS_CONFIRMED:
                # The credit exists on-chain; do not let the database and chain disagree on ownership.
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"On-chain transfer failed; purchase cancelled. ({bc.get('reason')})",
                )
        else:
            bc = {"status": STATUS_NOT_RECORDED, "tx_hash": None,
                  "reason": "Credit was never recorded on-chain; ownership is tracked in the database only."}
    except HTTPException:
        _claim(db, credit.id, CreditStatus.RESERVED.value, CreditStatus.AVAILABLE.value)
        raise

    db.refresh(credit)
    seller = db.get(User, seller_id)
    plantation = db.get(Plantation, credit.plantation_id)
    total = round(qty * credit.price_per_tco2e, 2)
    txn = Transaction(
        id=f"TXN-{datetime.utcnow():%Y}-{uuid.uuid4().hex[:8].upper()}",
        credit_id=credit.id,
        buyer_id=current_user.id,
        seller_id=seller_id,
        quantity_tco2e=qty,
        unit_price=credit.price_per_tco2e,
        total_amount=total,
        currency=credit.currency or "INR",
        status=TransactionStatus.COMPLETED.value,
        payment_method="PROTOTYPE_NO_PAYMENT",
        certificate_id=f"CERT-OFFSET-{uuid.uuid4().hex[:8].upper()}",
        blockchain_tx_hash=bc.get("tx_hash"),
        blockchain_status=bc["status"],
        notes=(
            "Prototype transaction: no real payment was processed. "
            + (f"Ownership transferred on-chain in tx {bc['tx_hash']}." if bc["status"] == STATUS_CONFIRMED
               else f"Not recorded on-chain: {bc.get('reason')}")
        ),
        timestamp=datetime.utcnow(),
    )
    db.add(txn)
    credit.owner_id = current_user.id
    credit.status = CreditStatus.SOLD.value
    db.add(AuditLog(
        user_id=current_user.id, user_email=current_user.email, user_role=current_user.role,
        action="CREDIT_PURCHASE_COMPLETED", target_type="Transaction", target_id=txn.id,
        details=(f"{current_user.email} bought {credit.id} ({qty} tCO2e) from {seller.email if seller else seller_id} "
                 f"for INR {total}. Chain: {bc['status']} {bc.get('tx_hash') or ''}".strip()),
    ))
    db.commit()
    db.refresh(txn)

    txn.buyer_name = current_user.full_name
    txn.seller_name = seller.full_name if seller else None
    txn.plantation_name = plantation.name if plantation else None
    return txn


@router.post("/marketplace/credits/{id}/retire")
def retire_carbon_credit(
    id: str,
    current_user: User = Depends(require_role([UserRole.BUYER.value])),
    db: Session = Depends(get_db),
):
    """Permanently retires a purchased credit (owner only)."""
    credit = db.query(Credit).filter(Credit.id == id).first()
    if not credit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Carbon credit {id} not found")
    if credit.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the credit owner can retire this credit")
    if credit.is_retired or credit.status == CreditStatus.RETIRED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This credit is already retired")
    if credit.status != CreditStatus.SOLD.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only purchased (SOLD) credits can be retired; status is {credit.status}")

    if not _claim(db, credit.id, CreditStatus.SOLD.value, CreditStatus.RESERVED.value):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Credit state changed; please retry.")
    db.refresh(credit)

    if credit.blockchain_status == STATUS_CONFIRMED:
        bc = BlockchainService.retire_credit_on_chain(credit.id)
        if bc["status"] != STATUS_CONFIRMED:
            _claim(db, credit.id, CreditStatus.RESERVED.value, CreditStatus.SOLD.value)
            raise HTTPException(status_code=503, detail=f"On-chain retirement failed; nothing changed. ({bc.get('reason')})")
    else:
        bc = {"status": STATUS_NOT_RECORDED, "tx_hash": None, "reason": "Credit was never recorded on-chain."}

    now = datetime.utcnow()
    credit.is_retired = 1
    credit.status = CreditStatus.RETIRED.value
    credit.retired_at = now
    credit.retirement_tx_hash = bc.get("tx_hash")
    db.add(AuditLog(
        user_id=current_user.id, user_email=current_user.email, user_role=current_user.role,
        action="CREDIT_RETIRED", target_type="Credit", target_id=credit.id,
        details=f"{credit.id} ({credit.carbon_quantity_tco2e} tCO2e) retired by {current_user.email}. Chain: {bc['status']} {bc.get('tx_hash') or ''}".strip(),
    ))
    db.commit()

    return {
        "success": True,
        "credit_id": credit.id,
        "carbon_quantity_tco2e": credit.carbon_quantity_tco2e,
        "status": "RETIRED",
        "blockchain_status": bc["status"],
        "blockchain_tx_hash": bc.get("tx_hash"),
        "retired_at": now.isoformat(),
        "message": f"{credit.carbon_quantity_tco2e} tCO2e retired. Retired credits cannot be transferred or sold again.",
    }


@router.get("/marketplace/credits/{id}/blockchain-record", response_model=BlockchainRecordResponse)
def get_blockchain_credit_record(id: str, db: Session = Depends(get_db)):
    """On-chain record if it exists; otherwise the database record, clearly marked DATABASE_ONLY."""
    credit = db.query(Credit).filter(Credit.id == id).first()
    if not credit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Carbon credit {id} not found")

    on_chain = BlockchainService.get_on_chain_record(id)
    if on_chain:
        return BlockchainRecordResponse(
            credit_id=on_chain["credit_id"],
            on_chain=True,
            source="CONTRACT",
            blockchain_status=credit.blockchain_status,
            plantation_id=on_chain["plantation_id"],
            carbon_quantity_tco2e=on_chain["carbon_quantity_tco2e"],
            report_hash=on_chain["report_hash"],
            owner_address=on_chain["owner_address"],
            issued_at_timestamp=on_chain["issued_at_timestamp"],
            is_retired=on_chain["is_retired"],
            retired_at_timestamp=on_chain["retired_at_timestamp"] or None,
            contract_address=on_chain["contract_address"],
            transaction_hash=credit.blockchain_tx_hash,
            status="RETIRED" if on_chain["is_retired"] else "ACTIVE",
        )

    return BlockchainRecordResponse(
        credit_id=credit.id,
        on_chain=False,
        source="DATABASE_ONLY",
        blockchain_status=credit.blockchain_status or STATUS_NOT_RECORDED,
        plantation_id=credit.plantation_id,
        carbon_quantity_tco2e=credit.carbon_quantity_tco2e,
        report_hash=credit.report_hash,
        owner_address=None,
        issued_at_timestamp=int(credit.created_at.timestamp()) if credit.created_at else None,
        is_retired=bool(credit.is_retired),
        retired_at_timestamp=int(credit.retired_at.timestamp()) if credit.retired_at else None,
        contract_address=credit.blockchain_contract_address,
        transaction_hash=credit.blockchain_tx_hash,
        status="RETIRED" if credit.is_retired else credit.status,
        note="No on-chain record could be read (chain offline, reset, or credit never recorded). "
             "Values shown come from the application database.",
    )


@router.get("/blockchain/status")
def blockchain_status():
    return BlockchainService.status()


@router.get("/transactions", response_model=List[TransactionResponse])
def list_transactions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Transaction)
    if current_user.role == UserRole.BUYER.value:
        query = query.filter(Transaction.buyer_id == current_user.id)
    elif current_user.role == UserRole.FARMER.value:
        query = query.filter(Transaction.seller_id == current_user.id)
    txns = query.order_by(Transaction.timestamp.desc()).all()

    for t in txns:
        credit = db.get(Credit, t.credit_id)
        plantation = db.get(Plantation, credit.plantation_id) if credit else None
        buyer = db.get(User, t.buyer_id)
        seller = db.get(User, t.seller_id)
        t.plantation_name = plantation.name if plantation else None
        t.buyer_name = buyer.full_name if buyer else None
        t.seller_name = seller.full_name if seller else None
    return txns
