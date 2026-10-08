from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models.user import User, UserRole
from ..models.plantation import Plantation, PlantationStatus
from ..models.verification import Verification, VerificationDecision
from ..models.credit import Credit, CreditStatus
from ..models.transaction import Transaction
from ..models.audit_log import AuditLog
from ..schemas.schemas import AdminMetricsResponse, AdminDecisionRequest, VerificationResponse, AuditLogResponse
from ..services.carbon_engine import CarbonEngine, CreditIssuanceError
from ..services.verification_store import (
    DECISION_TO_PLANTATION_STATUS, PreviewVerification, hydrate, latest_verification,
)
from ..core.security import get_current_user, require_role

router = APIRouter(prefix="/admin", tags=["Admin Dashboard & Management"])

@router.get("/metrics", response_model=AdminMetricsResponse)
def get_admin_metrics(
    current_user: User = Depends(require_role([UserRole.ADMIN.value, UserRole.AUDITOR.value])),
    db: Session = Depends(get_db)
):
    total_farmers = db.query(User).filter(User.role == UserRole.FARMER.value).count()
    total_buyers = db.query(User).filter(User.role == UserRole.BUYER.value).count()
    total_plantations = db.query(Plantation).count()
    
    pending_verifications = db.query(Plantation).filter(
        Plantation.status.in_([PlantationStatus.SUBMITTED.value, PlantationStatus.REVIEW.value])
    ).count()
    
    approved_plantations = db.query(Plantation).filter(Plantation.status == PlantationStatus.VERIFIED.value).count()
    review_plantations = db.query(Plantation).filter(Plantation.status == PlantationStatus.REVIEW.value).count()
    rejected_plantations = db.query(Plantation).filter(Plantation.status == PlantationStatus.REJECTED.value).count()
    
    credits_issued_count = db.query(Credit).count()
    total_credits_vol = db.query(func.sum(Credit.carbon_quantity_tco2e)).scalar() or 0.0
    
    total_txns = db.query(Transaction).count()
    total_txn_amount = db.query(func.sum(Transaction.total_amount)).scalar() or 0.0
    
    return {
        "total_farmers": total_farmers,
        "total_buyers": total_buyers,
        "total_plantations": total_plantations,
        "pending_verifications": pending_verifications,
        "approved_plantations": approved_plantations,
        "review_plantations": review_plantations,
        "rejected_plantations": rejected_plantations,
        "credits_issued_count": credits_issued_count,
        "total_carbon_credits_tco2e": round(float(total_credits_vol), 1),
        "total_transactions_count": total_txns,
        "total_transaction_volume_inr": round(float(total_txn_amount), 2)
    }

@router.get("/verifications", response_model=List[VerificationResponse])
def list_admin_verifications(
    current_user: User = Depends(require_role([UserRole.ADMIN.value, UserRole.AUDITOR.value])),
    db: Session = Depends(get_db)
):
    """Latest verification per plantation. Plantations never verified appear as read-only PENDING previews."""
    items = []
    for p in db.query(Plantation).order_by(Plantation.created_at.desc()).all():
        v = latest_verification(db, p.id)
        items.append(hydrate(v, p) if v is not None else PreviewVerification(p))
    return items


@router.post("/verifications/{id}/decision", response_model=VerificationResponse)
def update_verification_decision(
    id: str,
    decision_in: AdminDecisionRequest,
    current_user: User = Depends(require_role([UserRole.ADMIN.value, UserRole.AUDITOR.value])),
    db: Session = Depends(get_db)
):
    """
    Human auditor decision on a scored verification.

    * Only the plantation's latest verification can be decided.
    * APPROVED requires a fully scored verification (all three modality scores present).
    * Changing the engine's decision requires notes (recorded in the audit log).
    * Once credits are issued the decision is final.
    """
    verification = db.query(Verification).filter(Verification.id == id).first()
    if not verification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Verification {id} not found")
    plantation = db.query(Plantation).filter(Plantation.id == verification.plantation_id).first()
    if plantation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantation for this verification not found")

    latest = latest_verification(db, plantation.id)
    if latest.id != verification.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Verification {id} is superseded by {latest.id}; decide on the latest one.")
    if db.query(Credit).filter(Credit.plantation_id == plantation.id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Credits have already been issued for this plantation; the decision is final.")

    dec = decision_in.decision
    notes = (decision_in.notes or "").strip()
    if dec == VerificationDecision.APPROVED.value:
        missing = [name for name, val in (("NDVI", verification.ndvi_score), ("CV", verification.cv_score),
                                          ("SOC", verification.soc_score)) if val is None]
        if verification.overall_score is None or missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve: verification is not fully scored (missing {', '.join(missing) or 'overall score'}). "
                       "Required evidence must be submitted and verification re-run first.",
            )
    engine_dec = verification.engine_decision or verification.decision
    if dec != engine_dec and not notes:
        raise HTTPException(status_code=422,
                            detail=f"Notes are required when overriding the engine decision ({engine_dec}).")

    old = verification.decision
    if verification.engine_decision is None:
        verification.engine_decision = old
    verification.decision = dec
    verification.decided_by = current_user.email
    verification.auditor_notes = notes or None
    verification.decision_reasons = (verification.decision_reasons or []) + [
        f"Auditor {current_user.email} set decision {old} → {dec}" + (f": {notes}" if notes else ".")
    ]
    plantation.status = DECISION_TO_PLANTATION_STATUS[dec]
    db.add(AuditLog(
        user_id=current_user.id, user_email=current_user.email, user_role=current_user.role,
        action="AUDITOR_DECISION", target_type="Verification", target_id=verification.id,
        details=f"{current_user.email} changed decision {old} → {dec} (engine: {engine_dec}). Notes: {notes or 'none'}",
    ))
    db.commit()
    db.refresh(verification)

    if dec == VerificationDecision.APPROVED.value:
        try:
            CarbonEngine.issue_credit_for_plantation(
                plantation=plantation, verification=verification, db=db,
                issuer_user_id=current_user.id, issuer_email=current_user.email, issuer_role=current_user.role,
            )
        except CreditIssuanceError as exc:
            verification.decision_reasons = (verification.decision_reasons or []) + [f"Credit issuance skipped: {exc}"]
            db.commit()
            db.refresh(verification)

    return hydrate(verification, plantation)

@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    current_user: User = Depends(require_role([UserRole.ADMIN.value, UserRole.AUDITOR.value])),
    db: Session = Depends(get_db)
):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
