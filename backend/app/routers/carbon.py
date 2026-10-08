import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.user import User, UserRole
from ..models.plantation import Plantation, PlantationStatus
from ..models.verification import Verification, VerificationDecision
from ..models.credit import Credit, CreditStatus
from ..models.audit_log import AuditLog
from ..schemas.schemas import CarbonEstimateResponse, IssueCreditsRequest, CreditResponse
from ..services.carbon_engine import CarbonEngine
from ..services.blockchain_service import BlockchainService
from ..core.security import get_current_user, require_role

router = APIRouter(prefix="/plantations", tags=["Carbon Engine & Credit Issuance"])

@router.post("/{id}/carbon-estimate", response_model=CarbonEstimateResponse)
def estimate_carbon_sequestration(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plantation = db.query(Plantation).filter(Plantation.id == id).first()
    if not plantation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantation not found")
        
    estimate = CarbonEngine.calculate_estimate(plantation=plantation)
    return estimate

def _hydrate_credit(credit: Credit, db: Session) -> Credit:
    plantation = db.query(Plantation).filter(Plantation.id == credit.plantation_id).first()
    if plantation:
        credit.plantation_name = plantation.name
        credit.location = plantation.location
        credit.farmer_name = plantation.farmer_name
        credit.image_url = plantation.image_url
        
    verification = db.query(Verification).filter(Verification.id == credit.verification_id).first()
    if verification:
        credit.verification_score = verification.overall_score
        credit.verification_decision = verification.decision
        credit.ndvi_score = verification.ndvi_score
        credit.cv_score = verification.cv_score
        credit.soc_score = verification.soc_score
    return credit

@router.post("/{id}/generate-credits", response_model=CreditResponse, status_code=status.HTTP_201_CREATED)
def issue_carbon_credits(
    id: int,
    issue_data: IssueCreditsRequest = IssueCreditsRequest(),
    current_user: User = Depends(require_role([UserRole.FARMER.value, UserRole.ADMIN.value])),
    db: Session = Depends(get_db)
):
    plantation = db.query(Plantation).filter(Plantation.id == id).first()
    if not plantation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantation not found")
        
    # Permission check
    if current_user.role == UserRole.FARMER.value and plantation.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to issue credits for this plantation")
        
    # Verify status
    if plantation.status != PlantationStatus.VERIFIED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot issue credits. Plantation status is '{plantation.status}'. Only 'VERIFIED' (APPROVED) plantations are eligible."
        )
        
    # Check latest verification
    latest_verification = (
        db.query(Verification)
        .filter(Verification.plantation_id == id)
        .order_by(Verification.verified_at.desc())
        .first()
    )
    if not latest_verification or latest_verification.decision != VerificationDecision.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid APPROVED verification record required before credit issuance."
        )
        
    # Check if credits were already issued for this plantation (idempotent retrieval)
    existing_credit = db.query(Credit).filter(Credit.plantation_id == id).first()
    if existing_credit:
        if issue_data and issue_data.price_per_tco2e:
            existing_credit.price_per_tco2e = issue_data.price_per_tco2e
            db.commit()
            db.refresh(existing_credit)
        return _hydrate_credit(existing_credit, db)
        
    credit = CarbonEngine.issue_credit_for_plantation(
        plantation=plantation,
        verification=latest_verification,
        db=db,
        price_per_tco2e=issue_data.price_per_tco2e,
        issuer_user_id=current_user.id,
        issuer_email=current_user.email,
        issuer_role=current_user.role
    )
    if not credit:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to issue carbon credit."
        )
        
    return _hydrate_credit(credit, db)
