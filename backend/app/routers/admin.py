import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..config import settings
from ..database import get_db
from ..models.user import User, UserRole
from ..models.plantation import Plantation, PlantationStatus
from ..models.verification import Verification, VerificationDecision
from ..models.credit import Credit, CreditStatus
from ..models.transaction import Transaction
from ..models.audit_log import AuditLog
from ..schemas.schemas import AdminMetricsResponse, AdminDecisionRequest, VerificationResponse, AuditLogResponse
from ..services.verification_engine import VerificationEngine
from ..core.security import get_current_user, require_role

router = APIRouter(prefix="/admin", tags=["Admin Dashboard & Management"])

def _hydrate_verification(v: Verification, db: Session) -> Verification:
    p = db.query(Plantation).filter(Plantation.id == v.plantation_id).first()
    if p:
        v.plantation_name = p.name
        v.farmer_name = p.farmer_name
        v.location = p.location
        v.area_hectares = p.area_hectares
        v.image_url = p.image_url
        audit = VerificationEngine.check_evidence_completeness(p)
        v.evidence_status = audit["evidence_status"]
        v.missing_evidence = audit["missing_modalities"]
    return v

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
    # Ensure all plantations have a verification evaluation
    all_plantations = db.query(Plantation).all()
    for p in all_plantations:
        existing = db.query(Verification).filter(Verification.plantation_id == p.id).first()
        if not existing:
            custom_image_path = None
            if p.image_url:
                filename = os.path.basename(p.image_url)
                candidate = os.path.join(settings.UPLOAD_DIR, filename)
                if os.path.exists(candidate):
                    custom_image_path = candidate
            res = VerificationEngine.run_verification(p, custom_image_path=custom_image_path, db=db)
            ver = Verification(
                id=res["id"],
                plantation_id=p.id,
                ndvi_value=res["ndvi_value"],
                ndvi_score=res["ndvi_score"],
                ndvi_status=res["ndvi_status"],
                ndvi_historical_diff=res.get("ndvi_historical_diff"),
                is_real_satellite=res.get("is_real_satellite", False),
                satellite_source=res.get("satellite_source"),
                acquisition_date=res.get("acquisition_date"),
                mean_ndvi=res.get("mean_ndvi"),
                min_ndvi=res.get("min_ndvi"),
                max_ndvi=res.get("max_ndvi"),
                vegetation_coverage_pct=res.get("vegetation_coverage_pct"),
                image_quality_score=res["image_quality_score"],
                vegetation_detection_score=res["vegetation_detection_score"],
                cv_score=res["cv_score"],
                cv_detection_status=res["cv_detection_status"],
                ai_model_name=res.get("ai_model_name", "MobileNetV3-Plantation-v1"),
                ai_model_version=res.get("ai_model_version", "1.0.0"),
                ai_predicted_class=res.get("ai_predicted_class"),
                ai_confidence_pct=res.get("ai_confidence_pct"),
                image_phash=res.get("image_phash"),
                soc_pct=res["soc_pct"],
                soc_score=res["soc_score"],
                soc_status=res["soc_status"],
                ndvi_weight=res["ndvi_weight"],
                cv_weight=res["cv_weight"],
                soc_weight=res["soc_weight"],
                ndvi_contribution=res["ndvi_contribution"],
                cv_contribution=res["cv_contribution"],
                soc_contribution=res["soc_contribution"],
                overall_score=res["overall_score"],
                decision=res["decision"],
                risk_score=res.get("risk_score", 0.0),
                risk_level=res.get("risk_level", "LOW"),
                risk_factors=res.get("risk_factors", []),
                risk_explanation=res.get("risk_explanation"),
                evidence_summary=res["evidence_summary"],
                limitations_disclaimer=res["limitations_disclaimer"],
                verified_at=res["verified_at"]
            )
            db.add(ver)
            db.commit()

    verifications = db.query(Verification).order_by(Verification.verified_at.desc()).all()
    
    # Return latest verification per plantation
    seen_plantations = set()
    latest = []
    for v in verifications:
        if v.plantation_id not in seen_plantations:
            seen_plantations.add(v.plantation_id)
            latest.append(_hydrate_verification(v, db))
            
    return latest

@router.post("/verifications/{id}/decision", response_model=VerificationResponse)
def update_verification_decision(
    id: str,
    decision_in: AdminDecisionRequest,
    current_user: User = Depends(require_role([UserRole.ADMIN.value, UserRole.AUDITOR.value])),
    db: Session = Depends(get_db)
):
    verification = db.query(Verification).filter(Verification.id == id).first()
    if not verification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification record not found")
        
    valid_decisions = [d.value for d in VerificationDecision]
    dec = decision_in.decision.upper()
    if dec not in valid_decisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision '{decision_in.decision}'. Allowed: {valid_decisions}"
        )
        
    old_decision = verification.decision
    verification.decision = dec
    
    plantation = db.query(Plantation).filter(Plantation.id == verification.plantation_id).first()
    if plantation:
        if dec == VerificationDecision.APPROVED.value:
            audit_result = VerificationEngine.check_evidence_completeness(plantation)
            if not audit_result.get("is_complete"):
                missing = audit_result.get("missing_modalities", [])
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot approve plantation with incomplete evidence. Missing modalities: {missing}"
                )
            plantation.status = PlantationStatus.VERIFIED.value
        elif dec == VerificationDecision.REVIEW.value:
            plantation.status = PlantationStatus.REVIEW.value
        else:
            plantation.status = PlantationStatus.REJECTED.value
            
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_role=current_user.role,
        action="ADMIN_DECISION_OVERRIDE",
        target_type="Verification",
        target_id=verification.id,
        details=f"Auditor/Admin {current_user.email} changed decision from {old_decision} to {dec}. Notes: {decision_in.notes or 'None'}"
    )
    db.add(audit)
    db.commit()
    db.refresh(verification)
    
    # Auto-issue verified carbon asset upon approval so it is immediately available in marketplace
    if dec == VerificationDecision.APPROVED.value and plantation:
        from ..services.carbon_engine import CarbonEngine
        CarbonEngine.issue_credit_for_plantation(
            plantation=plantation,
            verification=verification,
            db=db,
            issuer_user_id=current_user.id,
            issuer_email=current_user.email,
            issuer_role=current_user.role
        )
    
    return _hydrate_verification(verification, db)

@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    current_user: User = Depends(require_role([UserRole.ADMIN.value, UserRole.AUDITOR.value])),
    db: Session = Depends(get_db)
):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
