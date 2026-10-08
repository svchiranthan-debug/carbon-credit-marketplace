from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.security import get_current_user
from ..database import get_db
from ..models.credit import Credit, CreditStatus
from ..models.plantation import Plantation
from ..models.user import User, UserRole
from ..schemas.schemas import CreditResponse
from ..services.marketplace_rules import hydrate_credit, listed_credits

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])

STATUS_FILTERS = {"AVAILABLE", "SOLD", "RETIRED", "ALL"}


@router.get("/credits", response_model=List[CreditResponse])
def list_marketplace_credits(
    location: Optional[str] = Query(None, description="Filter by location keyword"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum overall verification score"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price in INR"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price in INR"),
    status_filter: Optional[str] = Query(
        None,
        description="AVAILABLE (default: only credits that pass every listing rule), SOLD, RETIRED, "
                    "or ALL (= listed + sold + retired). Unverified credits are never returned as AVAILABLE.",
    ),
    db: Session = Depends(get_db),
):
    sf = (status_filter or "AVAILABLE").upper()
    if sf not in STATUS_FILTERS:
        raise HTTPException(status_code=422, detail=f"status_filter must be one of {sorted(STATUS_FILTERS)}")

    credits: List[Credit] = []
    if sf in ("AVAILABLE", "ALL"):
        credits.extend(listed_credits(db))
    if sf in ("SOLD", "ALL"):
        credits.extend(db.query(Credit).filter(Credit.status == CreditStatus.SOLD.value).all())
    if sf in ("RETIRED", "ALL"):
        credits.extend(db.query(Credit).filter(Credit.status == CreditStatus.RETIRED.value).all())

    if min_price is not None:
        credits = [c for c in credits if c.price_per_tco2e >= min_price]
    if max_price is not None:
        credits = [c for c in credits if c.price_per_tco2e <= max_price]

    hydrated = [hydrate_credit(c, db) for c in credits]
    if location:
        hydrated = [c for c in hydrated if c.location and location.lower() in c.location.lower()]
    if min_score is not None:
        hydrated = [c for c in hydrated if c.verification_score is not None and c.verification_score >= min_score]
    hydrated.sort(key=lambda c: c.created_at, reverse=True)
    return hydrated


@router.get("/my-credits", response_model=List[CreditResponse])
@router.get("/credits/my-credits", response_model=List[CreditResponse])
def get_my_credits(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Credit)
    if current_user.role == UserRole.FARMER.value:
        plantation_ids = [p for (p,) in db.query(Plantation.id).filter(Plantation.farmer_id == current_user.id)]
        query = query.filter(Credit.plantation_id.in_(plantation_ids) | (Credit.owner_id == current_user.id))
    elif current_user.role == UserRole.BUYER.value:
        query = query.filter(Credit.owner_id == current_user.id)
    credits = query.order_by(Credit.created_at.desc()).all()
    return [hydrate_credit(c, db) for c in credits]


@router.get("/credits/{id}", response_model=CreditResponse)
def get_marketplace_credit_detail(id: str, db: Session = Depends(get_db)):
    credit = db.query(Credit).filter(Credit.id == id).first()
    if not credit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Carbon credit {id} not found")
    return hydrate_credit(credit, db)
