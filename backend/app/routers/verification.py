from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.security import get_current_user
from ..database import get_db
from ..models.credit import Credit
from ..models.plantation import Plantation, PlantationStatus
from ..models.user import User, UserRole
from ..models.verification import Verification, VerificationDecision
from ..schemas.schemas import VerificationResponse, VerificationRunRequest
from ..services.carbon_engine import CarbonEngine, CreditIssuanceError
from ..services.verification_engine import VerificationEngine, resolve_upload_path
from ..services.verification_store import PreviewVerification, hydrate, latest_verification, persist_verification

router = APIRouter(tags=["Verification Engine"])


def _load_plantation(id: int, user: User, db: Session) -> Plantation:
    plantation = db.query(Plantation).filter(Plantation.id == id).first()
    if not plantation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plantation {id} not found")
    if user.role == UserRole.FARMER.value and plantation.farmer_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this plantation")
    if user.role == UserRole.BUYER.value and plantation.status != PlantationStatus.VERIFIED.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plantation {id} not found")
    return plantation


def _execute_verification(plantation: Plantation, current_user: User, db: Session) -> Verification:
    if current_user.role == UserRole.BUYER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Buyers cannot run verifications")
    if db.query(Credit).filter(Credit.plantation_id == plantation.id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Credits were already issued from this plantation's approved verification; it cannot be re-verified.",
        )

    result = VerificationEngine.run_verification(plantation, db=db)
    verification = persist_verification(result, plantation, current_user, db)

    if verification.decision == VerificationDecision.APPROVED.value:
        try:
            CarbonEngine.issue_credit_for_plantation(
                plantation=plantation, verification=verification, db=db,
                issuer_user_id=current_user.id, issuer_email=current_user.email, issuer_role=current_user.role,
            )
        except CreditIssuanceError as exc:
            # The approval stands; the reason credits were not minted is recorded on the verification.
            verification.decision_reasons = (verification.decision_reasons or []) + [f"Credit issuance skipped: {exc}"]
            db.commit()
            db.refresh(verification)

    return hydrate(verification, plantation)


@router.post("/plantations/{id}/verify", response_model=VerificationResponse)
def run_plantation_verification(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plantation = _load_plantation(id, current_user, db)
    return _execute_verification(plantation, current_user, db)


@router.post("/verification/run", response_model=VerificationResponse)
def run_verification_direct(
    body: VerificationRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plantation = _load_plantation(body.plantation_id, current_user, db)
    if body.ground_image_path is not None or body.soc_sample_pct is not None:
        if current_user.role not in (UserRole.FARMER.value, UserRole.ADMIN.value):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owning farmer can change evidence")
        if body.ground_image_path is not None:
            if not body.ground_image_path.startswith("/uploads/") or resolve_upload_path(body.ground_image_path) is None:
                raise HTTPException(status_code=422, detail="ground_image_path must be an uploaded '/uploads/<file>' path.")
            plantation.image_url = body.ground_image_path
        if body.soc_sample_pct is not None:
            plantation.soil_soc_pct = body.soc_sample_pct
        db.commit()
    return _execute_verification(plantation, current_user, db)


@router.get("/plantations/{id}/verification", response_model=VerificationResponse)
def get_plantation_verification(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Latest verification for a plantation. Read-only: never runs or stores a verification."""
    plantation = _load_plantation(id, current_user, db)
    verification = latest_verification(db, plantation.id)
    if verification is None:
        return PreviewVerification(plantation)
    return hydrate(verification, plantation)


@router.get("/plantations/{id}/verifications", response_model=list[VerificationResponse])
def list_plantation_verifications(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Full verification history (newest first) for audit purposes."""
    plantation = _load_plantation(id, current_user, db)
    rows = (
        db.query(Verification)
        .filter(Verification.plantation_id == plantation.id)
        .order_by(Verification.verified_at.desc())
        .all()
    )
    return [hydrate(v, plantation) for v in rows]


@router.get("/verifications/{id}", response_model=VerificationResponse)
def get_verification_by_id(id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    verification = db.query(Verification).filter(Verification.id == id).first()
    if not verification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Verification {id} not found")
    plantation = _load_plantation(verification.plantation_id, current_user, db)
    return hydrate(verification, plantation)
