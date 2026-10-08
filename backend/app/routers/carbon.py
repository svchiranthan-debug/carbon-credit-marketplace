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
from typing import Optional

from ..services.carbon_engine import CarbonEngine, CreditIssuanceError
from ..services.marketplace_rules import hydrate_credit
from ..services.verification_store import latest_verification
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plantation {id} not found")
    if current_user.role == UserRole.FARMER.value and plantation.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this plantation")

    estimate = CarbonEngine.calculate_estimate(plantation=plantation)
    return estimate

@router.post("/{id}/generate-credits", response_model=CreditResponse, status_code=status.HTTP_201_CREATED)
def issue_carbon_credits(
    id: int,
    issue_data: Optional[IssueCreditsRequest] = None,
    current_user: User = Depends(require_role([UserRole.FARMER.value, UserRole.ADMIN.value])),
    db: Session = Depends(get_db)
):
    plantation = db.query(Plantation).filter(Plantation.id == id).first()
    if not plantation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plantation {id} not found")
    if current_user.role == UserRole.FARMER.value and plantation.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to issue credits for this plantation")

    price = issue_data.price_per_tco2e if issue_data else None
    existing = db.query(Credit).filter(Credit.plantation_id == id).first()
    if existing:
        # Idempotent: return the existing lot; the owner may re-price it while it is still for sale.
        if price is not None and existing.status == CreditStatus.AVAILABLE.value and existing.owner_id == plantation.farmer_id:
            existing.price_per_tco2e = price
            db.commit()
            db.refresh(existing)
        return hydrate_credit(existing, db)

    verification = latest_verification(db, id)
    try:
        credit = CarbonEngine.issue_credit_for_plantation(
            plantation=plantation,
            verification=verification,
            db=db,
            price_per_tco2e=price,
            issuer_user_id=current_user.id,
            issuer_email=current_user.email,
            issuer_role=current_user.role
        )
    except CreditIssuanceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return hydrate_credit(credit, db)
