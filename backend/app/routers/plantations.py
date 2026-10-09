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
from ..models.plantation_photo import PhotoStatus, PlantationPhoto
from ..schemas.schemas import (PhotoListResponse, PhotoResponse, PlantationCreate, PlantationEvidenceUpdate,
                               PlantationResponse)
from ..services.photo_store import (active_photos, build_photo_record, ensure_photo_rows, mark_near_duplicate,
                                    refresh_cover, remove_stored_file, sign_upload_url, store_validated_image,
                                    strip_upload_url)
from ..services.geometry import to_geojson_polygon
from ..services.verification_engine import resolve_upload_path

router = APIRouter(prefix="/plantations", tags=["Plantations"])

# Two registrations closer than this (degrees, ~11 m) by the same farmer with the same name are duplicates.
DUPLICATE_COORD_TOLERANCE = 0.0001


def _validate_image_url(image_url: Optional[str]) -> Optional[str]:
    """Only accept references to files that were actually uploaded to this server.

    Signed links ('/uploads/<file>?exp=..&sig=..') returned by the API are accepted too.
    """
    if image_url is None:
        return None
    canonical = strip_upload_url(image_url)
    if not image_url.startswith("/uploads/") or resolve_upload_path(canonical) is None:
        raise HTTPException(
            status_code=422,
            detail="image_url must be an '/uploads/<file>' path returned by the image upload endpoint.",
        )
    return canonical


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


def _photo_out(photo: PlantationPhoto) -> PhotoResponse:
    low = photo.confidence_pct is not None and photo.confidence_pct < settings.CV_LOW_CONFIDENCE_PCT
    data = {c.name: getattr(photo, c.name) for c in PlantationPhoto.__table__.columns
            if c.name in PhotoResponse.model_fields}
    return PhotoResponse(**data, url=sign_upload_url(f"/uploads/{photo.filename}"), low_confidence=low)


def _attach_photo(db: Session, plantation: Plantation, filename: str, user: User,
                  original_name: Optional[str] = None, delete_file_on_error: bool = True) -> PlantationPhoto:
    """Adds an uploaded file as an ACTIVE photo of the plantation (does not commit).

    Enforces the per-plantation limit and rejects exact re-uploads of an existing photo.
    On rejection the stored file is removed so the disk and the database stay consistent.
    """
    try:
        current = ensure_photo_rows(db, plantation)
        if len(current) >= settings.MAX_PHOTOS_PER_PLANTATION:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"Photo limit reached: at most {settings.MAX_PHOTOS_PER_PLANTATION} photos per plantation. Remove one first.")
        photo = build_photo_record(plantation.id, filename, user.id, original_name)
        if photo.validation_status != "VALID":
            raise HTTPException(status_code=400, detail=photo.validation_error or "Invalid photo.")
        same = next((p for p in current if p.sha256 and p.sha256 == photo.sha256), None)
        if same:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"This exact photo is already uploaded for this plantation (photo #{same.id}).")
        mark_near_duplicate(db, photo)
        db.add(photo)
        db.flush()
        return photo
    except BaseException:
        if delete_file_on_error:
            remove_stored_file(filename)
        raise


def _commit_photo_change(db: Session, plantation: Plantation, user: User, action: str, details: str) -> None:
    refresh_cover(db, plantation)
    _mark_needs_reverification(plantation)
    db.add(AuditLog(user_id=user.id, user_email=user.email, user_role=user.role, action=action,
                    target_type="Plantation", target_id=str(plantation.id),
                    details=details + " Status reset to SUBMITTED pending re-verification."))
    db.commit()
    db.refresh(plantation)


@router.post("/upload-image")
async def upload_plantation_image(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role([UserRole.FARMER.value])),
):
    """Upload a photo before the plantation exists; pass the returned image_url when registering it."""
    filename, _ = await store_validated_image(file, "plantation")
    return {"filename": filename, "image_url": sign_upload_url(f"/uploads/{filename}")}


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
    boundary = data.pop("boundary", None)
    data["boundary_geojson"] = to_geojson_polygon(boundary) if boundary else None
    data["image_url"] = None
    data["farmer_name"] = plantation_in.farmer_name or current_user.full_name
    plantation = Plantation(farmer_id=current_user.id, status=PlantationStatus.SUBMITTED.value, **data)
    db.add(plantation)
    db.flush()
    if image_url:
        _attach_photo(db, plantation, image_url.rsplit("/", 1)[-1], current_user, delete_file_on_error=False)
        refresh_cover(db, plantation)
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
    new_image = changes.pop("image_url", None)
    if new_image is not None:
        # Older clients send one image_url: it is added as another photo (nothing is overwritten).
        canonical = _validate_image_url(new_image)
        filename = canonical.rsplit("/", 1)[-1]
        if not db.query(PlantationPhoto).filter(PlantationPhoto.plantation_id == plantation.id,
                                                PlantationPhoto.filename == filename,
                                                PlantationPhoto.status == PhotoStatus.ACTIVE).first():
            _attach_photo(db, plantation, filename, current_user, delete_file_on_error=False)
        refresh_cover(db, plantation)
        changes["image_url"] = canonical
    for field, value in changes.items():
        if field != "image_url":
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
    """Single-photo endpoint kept for older clients: adds one photo (same rules as /photos)."""
    photo = await _upload_one_photo(id, file, current_user, db)
    plantation = db.get(Plantation, id)
    return {
        "message": "Image uploaded and attached to plantation",
        "image_url": sign_upload_url(plantation.image_url),
        "photo_id": photo.id,
        "plantation_id": plantation.id,
        "status": plantation.status,
    }


async def _upload_one_photo(id: int, file: UploadFile, user: User, db: Session) -> PlantationPhoto:
    plantation = _get_owned_plantation(id, user, db, write=True)
    _ensure_evidence_editable(plantation, db)
    if len(ensure_photo_rows(db, plantation)) >= settings.MAX_PHOTOS_PER_PLANTATION:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Photo limit reached: at most {settings.MAX_PHOTOS_PER_PLANTATION} photos per plantation. Remove one first.")
    filename, _ = await store_validated_image(file, f"plantation_{id}")
    try:
        photo = _attach_photo(db, plantation, filename, user, original_name=file.filename)
        dup = f" (near-duplicate of photo #{photo.duplicate_of_id})" if photo.duplicate_of_id else ""
        _commit_photo_change(db, plantation, user, "EVIDENCE_PHOTO_UPLOADED",
                             f"Ground photo #{photo.id} ({filename}) added{dup}.")
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        remove_stored_file(filename)
        raise
    db.refresh(photo)
    return photo


@router.post("/{id}/photos", response_model=PhotoResponse, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add ONE ground photo. Clients upload several photos with one request each, so every
    photo gets its own status and a failed one can be retried alone."""
    return _photo_out(await _upload_one_photo(id, file, current_user, db))


@router.get("/{id}/photos", response_model=PhotoListResponse)
def list_photos(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plantation = _get_owned_plantation(id, current_user, db)
    if current_user.role == UserRole.BUYER.value and plantation.status != PlantationStatus.VERIFIED.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plantation {id} not found")
    photos = ensure_photo_rows(db, plantation)
    db.commit()
    return PhotoListResponse(plantation_id=id, photos=[_photo_out(p) for p in photos], active_count=len(photos),
                             max_photos=settings.MAX_PHOTOS_PER_PLANTATION, max_bytes=settings.MAX_UPLOAD_BYTES)


@router.delete("/{id}/photos/{photo_id}", response_model=PhotoListResponse)
def remove_photo(id: int, photo_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Withdraw a photo from the evidence. The file is kept (evidence is never deleted)."""
    plantation = _get_owned_plantation(id, current_user, db, write=True)
    _ensure_evidence_editable(plantation, db)
    photo = db.query(PlantationPhoto).filter(PlantationPhoto.id == photo_id, PlantationPhoto.plantation_id == id,
                                             PlantationPhoto.status == PhotoStatus.ACTIVE).first()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Photo {photo_id} not found")
    photo.status = PhotoStatus.REMOVED
    for other in active_photos(db, id):
        if other.duplicate_of_id == photo.id:
            other.duplicate_of_id = None
            mark_near_duplicate(db, other)
    _commit_photo_change(db, plantation, current_user, "EVIDENCE_PHOTO_REMOVED", f"Ground photo #{photo.id} removed.")
    photos = active_photos(db, id)
    return PhotoListResponse(plantation_id=id, photos=[_photo_out(p) for p in photos], active_count=len(photos),
                             max_photos=settings.MAX_PHOTOS_PER_PLANTATION, max_bytes=settings.MAX_UPLOAD_BYTES)
