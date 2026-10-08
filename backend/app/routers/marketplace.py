from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.credit import Credit, CreditStatus
from ..models.plantation import Plantation
from ..models.verification import Verification
from ..models.user import User
from ..schemas.schemas import CreditResponse
from ..core.security import get_current_user

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])

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

@router.get("/credits", response_model=List[CreditResponse])
def list_marketplace_credits(
    location: Optional[str] = Query(None, description="Filter by location keyword"),
    min_score: Optional[float] = Query(None, description="Minimum overall verification score"),
    min_price: Optional[float] = Query(None, description="Minimum price in INR"),
    max_price: Optional[float] = Query(None, description="Maximum price in INR"),
    status_filter: Optional[str] = Query(None, description="Filter by status (AVAILABLE, SOLD)"),
    db: Session = Depends(get_db)
):
    query = db.query(Credit)
    
    if status_filter:
        if status_filter.upper() != "ALL":
            query = query.filter(Credit.status == status_filter.upper())
    else:
        query = query.filter(Credit.status == CreditStatus.AVAILABLE.value)
        
    if min_price is not None:
        query = query.filter(Credit.price_per_tco2e >= min_price)
    if max_price is not None:
        query = query.filter(Credit.price_per_tco2e <= max_price)
        
    credits = query.order_by(Credit.created_at.desc()).all()
    hydrated = [_hydrate_credit(c, db) for c in credits]
    
    # Filter by in-memory related fields if passed
    if location:
        hydrated = [c for c in hydrated if c.location and location.lower() in c.location.lower()]
    if min_score is not None:
        hydrated = [c for c in hydrated if (c.verification_score or 0.0) >= min_score]
        
    return hydrated

@router.get("/my-credits", response_model=List[CreditResponse])
@router.get("/credits/my-credits", response_model=List[CreditResponse])
def get_my_credits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == "FARMER":
        farmer_plantation_ids = [p[0] for p in db.query(Plantation.id).filter(Plantation.farmer_id == current_user.id).all()]
        if farmer_plantation_ids:
            credits = db.query(Credit).filter(
                (Credit.plantation_id.in_(farmer_plantation_ids)) | (Credit.owner_id == current_user.id)
            ).order_by(Credit.created_at.desc()).all()
        else:
            credits = db.query(Credit).filter(Credit.owner_id == current_user.id).order_by(Credit.created_at.desc()).all()
    elif current_user.role == "BUYER":
        credits = db.query(Credit).filter(Credit.owner_id == current_user.id).order_by(Credit.created_at.desc()).all()
    else:
        credits = db.query(Credit).order_by(Credit.created_at.desc()).all()
        
    return [_hydrate_credit(c, db) for c in credits]

@router.get("/credits/{id}", response_model=CreditResponse)
def get_marketplace_credit_detail(
    id: str,
    db: Session = Depends(get_db)
):
    credit = db.query(Credit).filter(Credit.id == id).first()
    if not credit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carbon credit not found")
        
    return _hydrate_credit(credit, db)
