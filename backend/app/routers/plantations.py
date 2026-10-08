import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..core.security import get_current_user, require_role
from ..database import get_db
from ..models.audit_log import AuditLog
from ..models.credit import Credit
from ..models.plantation import Plantation, PlantationStatus
from ..models.user import User, UserRole
from ..schemas.schemas import PlantationCreate, PlantationEvidenceUpdate, PlantationResponse
from ..services.ai.ai_vision_service import validate_image_file
from ..services.verification_engine import resolve_upload_path

router = APIRouter(prefix="/plantations", tags=["Plantations"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
# Two registrations closer than this (degrees, ~11 m) by the same farmer with the same name are duplicates.
DUPLICATE_COORD_TOLERANCE = 0.0001


async def _save_validated_image(file: UploadFile, prefix: str) -> str:
    """Stream an upload to disk with a size limit, then verify it decodes as an image."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image format '{ext or 'none'}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    filename = f"{prefix}_{uuid.uuid4().hex[:10]}{ext}"
    path = os.path.join(settings.UPLOAD_DIR, filename)
    written = 0
    with open(path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > settings.MAX_UPLOAD_BYTES:
                out.close()
                os.remove(path)
                raise HTTPException(
                    status_code=413,
                    detail=f"Image exceeds {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
                )
            out.write(chunk)
    ok, reason, _ = validate_image_file(path)
    if not ok:
        os.remove(path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)
    return filename


def _validate_image_url(image_url: Optional[str]) -> Optional[str]:
    """Only accept references to files that were actually uploaded to this server."""
    if image_url is None:
        return None
    if not image_url.startswith("/uploads/") or resolve_upload_path(image_url) is None:
        raise HTTPException(
            status_code=422,
            detail="image_url must be an '/uploads/<file>' path returned by the image upload endpoint.",
        )
    return f"/uploads/{os.path.basename(image_url)}"


def _get_owned_plantation(id: int, user: User, db: Session, write: bool = False) -> Plantation:
    plantation = db.query(Plantation).filter(Plantation.id == id).first()
    if not plantation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plantation {id} not found")
    if user.role == UserRole.FARMER.value and plantation.farmer_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this plantation")
    if write and user.role not in (UserRole.FARMER.value, UserRole.ADMIN.value):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owning farmer can change evidence")
    return plantation


def _ensure_evidence_editable(plantation: Plantation, db: Session) -> None:
    if db.query(Credit).filter(Credit.plantation_id == plantation.id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evidence is locked: carbon credits have already been issued from this plantation's verification.",
        )


def _mark_needs_reverification(plantation: Plantation) -> None:
    # Any evidence change invalidates the previous decision until verification is re-run.
    plantation.status = PlantationStatus.SUBMITTED.value


@router.post("/upload-image")
async def upload_plantation_image(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role([UserRole.FARMER.value])),
):
    filename = await _save_validated_image(file, "plantation")
    return {"filename": filename, "image_url": f"/uploads/{filename}"}


@router.post("", response_model=PlantationResponse, status_code=status.HTTP_201_CREATED)
def create_plantation(
    plantation_in: PlantationCreate,
    current_user: User = Depends(require_role([UserRole.FARMER.value])),
    db: Session = Depends(get_db),
):
    image_url = _validate_image_url(plantation_in.image_url)

    duplicate = db.query(Plantation).filter(
        Plantation.farmer_id == current_user.id,
        func.lower(Plantation.name) == plantation_in.name.lower(),
        Plantation.latitude.between(plantation_in.latitude - DUPLICATE_COORD_TOLERANCE,
                                    plantation_in.latitude + DUPLICATE_COORD_TOLERANCE),
        Plantation.longitude.between(plantation_in.longitude - DUPLICATE_COORD_TOLERANCE,
                                     plantation_in.longitude + DUPLICATE_COORD_TOLERANCE),
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate submission: you already registered '{duplicate.name}' at this location (plantation #{duplicate.id}).",
        )

    data = plantation_in.model_dump()
    data["image_url"] = image_url
    data["farmer_name"] = plantation_in.farmer_name or current_user.full_name
    plantation = Plantation(farmer_id=current_user.id, status=PlantationStatus.SUBMITTED.value, **data)
    db.add(plantation)
    db.flush()
    db.add(AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_role=current_user.role,
        action="PLANTATION_REGISTERED",
        target_type="Plantation",
        target_id=str(plantation.id),
        details=f"Plantation '{plantation.name}' registered with status SUBMITTED (verification pending).",
    ))
    db.commit()
    db.refresh(plantation)
    return plantation


@router.get("", response_model=List[PlantationResponse])
def list_plantations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Plantation)
    if current_user.role == UserRole.FARMER.value:
        query = query.filter(Plantation.farmer_id == current_user.id)
    elif current_user.role == UserRole.BUYER.value:
        # Buyers only see plantations whose credits are verified.
        query = query.filter(Plantation.status == PlantationStatus.VERIFIED.value)
    return query.order_by(Plantation.created_at.desc()).all()


@router.get("/{id}", response_model=PlantationResponse)
def get_plantation(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plantation = _get_owned_plantation(id, current_user, db)
    if current_user.role == UserRole.BUYER.value and plantation.status != PlantationStatus.VERIFIED.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plantation {id} not found")
    return plantation


@router.put("/{id}/evidence", response_model=PlantationResponse)
def update_plantation_evidence(
    id: int,
    evidence_in: PlantationEvidenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plantation = _get_owned_plantation(id, current_user, db, write=True)
    _ensure_evidence_editable(plantation, db)

    changes = evidence_in.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No evidence fields provided.")
    if "image_url" in changes:
        changes["image_url"] = _validate_image_url(changes["image_url"])
    for field, value in changes.items():
        setattr(plantation, field, value)
    _mark_needs_reverification(plantation)
    db.add(AuditLog(
        user_id=current_user.id, user_email=current_user.email, user_role=current_user.role,
        action="EVIDENCE_UPDATED", target_type="Plantation", target_id=str(plantation.id),
        details=f"Evidence fields updated: {', '.join(sorted(changes))}. Status reset to SUBMITTED pending re-verification.",
    ))
    db.commit()
    db.refresh(plantation)
    return plantation


@router.post("/{id}/image")
@router.post("/{id}/evidence")
async def upload_image_for_plantation(
    id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plantation = _get_owned_plantation(id, current_user, db, write=True)
    _ensure_evidence_editable(plantation, db)
    filename = await _save_validated_image(file, f"plantation_{id}")
    plantation.image_url = f"/uploads/{filename}"
    _mark_needs_reverification(plantation)
    db.add(AuditLog(
        user_id=current_user.id, user_email=current_user.email, user_role=current_user.role,
        action="EVIDENCE_IMAGE_UPLOADED", target_type="Plantation", target_id=str(plantation.id),
        details=f"Ground photograph {filename} attached. Status reset to SUBMITTED pending re-verification.",
    ))
    db.commit()
    db.refresh(plantation)
    return {
        "message": "Image uploaded and attached to plantation",
        "image_url": plantation.image_url,
        "plantation_id": plantation.id,
        "status": plantation.status,
    }
