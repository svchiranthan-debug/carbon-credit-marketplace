import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.user import User, UserRole
from ..models.plantation import Plantation, PlantationStatus
from ..models.verification import Verification, VerificationDecision
from ..models.audit_log import AuditLog
from ..schemas.schemas import VerificationResponse, VerificationRunRequest
from ..services.verification_engine import VerificationEngine
from ..core.security import get_current_user

router = APIRouter(tags=["Verification Engine"])

def _execute_verification(plantation: Plantation, current_user: User, db: Session) -> Verification:
    # Resolve physical image path if uploaded
    custom_image_path = None
    if plantation.image_url:
        # e.g., "/uploads/filename.jpg" -> physical path
        filename = os.path.basename(plantation.image_url)
        possible_path = os.path.join(settings.UPLOAD_DIR, filename)
        if os.path.exists(possible_path):
            custom_image_path = possible_path

    # Run Verification Engine
    result = VerificationEngine.run_verification(plantation, custom_image_path=custom_image_path, db=db)
    
    # Create persistent verification record
    verification = Verification(
        id=result["id"],
        plantation_id=plantation.id,
        ndvi_value=result["ndvi_value"],
        ndvi_score=result["ndvi_score"],
        ndvi_status=result["ndvi_status"],
        ndvi_historical_diff=result.get("ndvi_historical_diff"),
        is_real_satellite=result.get("is_real_satellite", False),
        satellite_source=result.get("satellite_source"),
        acquisition_date=result.get("acquisition_date"),
        mean_ndvi=result.get("mean_ndvi"),
        min_ndvi=result.get("min_ndvi"),
        max_ndvi=result.get("max_ndvi"),
        vegetation_coverage_pct=result.get("vegetation_coverage_pct"),
        image_quality_score=result["image_quality_score"],
        vegetation_detection_score=result["vegetation_detection_score"],
        cv_score=result["cv_score"],
        cv_detection_status=result["cv_detection_status"],
        ai_model_name=result.get("ai_model_name", "MobileNetV3-Plantation-v1"),
        ai_model_version=result.get("ai_model_version", "1.0.0"),
        ai_predicted_class=result.get("ai_predicted_class"),
        ai_confidence_pct=result.get("ai_confidence_pct"),
        image_phash=result.get("image_phash"),
        soc_pct=result["soc_pct"],
        soc_score=result["soc_score"],
        soc_status=result["soc_status"],
        ndvi_weight=result["ndvi_weight"],
        cv_weight=result["cv_weight"],
        soc_weight=result["soc_weight"],
        ndvi_contribution=result["ndvi_contribution"],
        cv_contribution=result["cv_contribution"],
        soc_contribution=result["soc_contribution"],
        overall_score=result["overall_score"],
        decision=result["decision"],
        risk_score=result.get("risk_score", 0.0),
        risk_level=result.get("risk_level", "LOW"),
        risk_factors=result.get("risk_factors", []),
        risk_explanation=result.get("risk_explanation"),
        evidence_summary=result["evidence_summary"],
        limitations_disclaimer=result["limitations_disclaimer"],
        verified_at=result["verified_at"]
    )
    db.add(verification)
    
    # Update plantation status
    if result["decision"] == VerificationDecision.APPROVED.value:
        plantation.status = PlantationStatus.VERIFIED.value
    elif result["decision"] == VerificationDecision.REVIEW.value:
        plantation.status = PlantationStatus.REVIEW.value
    elif result["decision"] == VerificationDecision.PENDING.value:
        plantation.status = PlantationStatus.SUBMITTED.value
    else:
        plantation.status = PlantationStatus.REJECTED.value
        
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_role=current_user.role,
        action="VERIFICATION_AUDIT_EXECUTED",
        target_type="Verification",
        target_id=verification.id,
        details=f"Verification audit executed for plantation #{plantation.id}. Score: {verification.overall_score} -> Decision: {verification.decision}"
    )
    db.add(audit)
    db.commit()
    db.refresh(verification)
    
    # Auto-issue verified carbon asset if automated verification decision is APPROVED
    if result["decision"] == VerificationDecision.APPROVED.value:
        from ..services.carbon_engine import CarbonEngine
        CarbonEngine.issue_credit_for_plantation(
            plantation=plantation,
            verification=verification,
            db=db,
            issuer_user_id=current_user.id,
            issuer_email=current_user.email,
            issuer_role=current_user.role
        )
    
    # Attach view fields
    verification.plantation_name = plantation.name
    verification.farmer_name = plantation.farmer_name
    verification.location = plantation.location
    verification.area_hectares = plantation.area_hectares
    verification.image_url = plantation.image_url
    verification.evidence_status = result.get("evidence_status")
    verification.missing_evidence = result.get("missing_evidence")
    
    return verification

@router.post("/plantations/{id}/verify", response_model=VerificationResponse)
def run_plantation_verification(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plantation = db.query(Plantation).filter(Plantation.id == id).first()
    if not plantation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantation not found")
        
    # Permission check: owner farmer or admin
    if current_user.role == UserRole.FARMER.value and plantation.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to verify this plantation")
        
    return _execute_verification(plantation=plantation, current_user=current_user, db=db)

@router.post("/verification/run", response_model=VerificationResponse)
def run_verification_direct(
    body: VerificationRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plantation = db.query(Plantation).filter(Plantation.id == body.plantation_id).first()
    if not plantation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantation not found")
        
    if current_user.role == UserRole.FARMER.value and plantation.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to verify this plantation")
        
    if body.ground_image_path:
        plantation.image_url = body.ground_image_path
    if body.soc_sample_pct is not None:
        plantation.soil_soc_pct = body.soc_sample_pct
    db.commit()
    db.refresh(plantation)

    return _execute_verification(plantation=plantation, current_user=current_user, db=db)

@router.get("/plantations/{id}/verification", response_model=VerificationResponse)
def get_plantation_verification(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plantation = db.query(Plantation).filter(Plantation.id == id).first()
    if not plantation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantation not found")
        
    verification = (
        db.query(Verification)
        .filter(Verification.plantation_id == id)
        .order_by(Verification.verified_at.desc())
        .first()
    )
    
    # If no verification record exists yet, generate initial evaluation
    if not verification:
        result = VerificationEngine.run_verification(plantation=plantation)
        verification = Verification(
            id=result["id"],
            plantation_id=plantation.id,
            ndvi_value=result["ndvi_value"],
            ndvi_score=result["ndvi_score"],
            ndvi_status=result["ndvi_status"],
            ndvi_historical_diff=result.get("ndvi_historical_diff"),
            image_quality_score=result["image_quality_score"],
            vegetation_detection_score=result["vegetation_detection_score"],
            cv_score=result["cv_score"],
            cv_detection_status=result["cv_detection_status"],
            soc_pct=result["soc_pct"],
            soc_score=result["soc_score"],
            soc_status=result["soc_status"],
            ndvi_weight=result["ndvi_weight"],
            cv_weight=result["cv_weight"],
            soc_weight=result["soc_weight"],
            ndvi_contribution=result["ndvi_contribution"],
            cv_contribution=result["cv_contribution"],
            soc_contribution=result["soc_contribution"],
            overall_score=result["overall_score"],
            decision=result["decision"],
            evidence_summary=result["evidence_summary"],
            limitations_disclaimer=result["limitations_disclaimer"],
            verified_at=result["verified_at"]
        )
        db.add(verification)
        db.commit()
        db.refresh(verification)
        verification.evidence_status = result.get("evidence_status")
        verification.missing_evidence = result.get("missing_evidence")
    else:
        # Recompute evidence status for response
        audit = VerificationEngine.check_evidence_completeness(plantation)
        verification.evidence_status = audit["evidence_status"]
        verification.missing_evidence = audit["missing_modalities"]
        
    verification.plantation_name = plantation.name
    verification.farmer_name = plantation.farmer_name
    verification.location = plantation.location
    verification.area_hectares = plantation.area_hectares
    verification.image_url = plantation.image_url
    return verification

@router.get("/verifications/{id}", response_model=VerificationResponse)
def get_verification_by_id(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    verification = db.query(Verification).filter(Verification.id == id).first()
    if not verification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification not found")
        
    plantation = db.query(Plantation).filter(Plantation.id == verification.plantation_id).first()
    if plantation:
        verification.plantation_name = plantation.name
        verification.farmer_name = plantation.farmer_name
        verification.location = plantation.location
        verification.area_hectares = plantation.area_hectares
        verification.image_url = plantation.image_url
        
    return verification
