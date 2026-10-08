import os
import uuid
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.user import User, UserRole
from ..models.plantation import Plantation, PlantationStatus
from ..models.verification import Verification
from ..models.audit_log import AuditLog
from ..schemas.schemas import PlantationCreate, PlantationResponse, PlantationEvidenceUpdate
from ..core.security import get_current_user, require_role

router = APIRouter(prefix="/plantations", tags=["Plantations"])

@router.post("/upload-image")
async def upload_plantation_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    # Validate file extension
    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp", ".tiff"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image format. Allowed formats: {', '.join(allowed_extensions)}"
        )
        
    unique_filename = f"plantation_{uuid.uuid4().hex[:10]}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Return accessible relative URL
    return {
        "filename": unique_filename,
        "image_url": f"/uploads/{unique_filename}",
        "file_path": file_path
    }

@router.post("", response_model=PlantationResponse, status_code=status.HTTP_201_CREATED)
def create_plantation(
    plantation_in: PlantationCreate,
    current_user: User = Depends(require_role([UserRole.FARMER.value])),
    db: Session = Depends(get_db)
):
    plantation = Plantation(
        farmer_id=current_user.id,
        name=plantation_in.name,
        farmer_name=plantation_in.farmer_name or current_user.full_name,
        location=plantation_in.location,
        latitude=plantation_in.latitude,
        longitude=plantation_in.longitude,
        area_hectares=plantation_in.area_hectares,
        plantation_age_years=plantation_in.plantation_age_years,
        tree_count=plantation_in.tree_count,
        tree_species=plantation_in.tree_species,
        plantation_type=plantation_in.plantation_type,
        sustainable_practice=plantation_in.sustainable_practice,
        image_url=plantation_in.image_url,
        soil_soc_pct=plantation_in.soil_soc_pct,
        soil_depth_cm=plantation_in.soil_depth_cm,
        soil_type=plantation_in.soil_type,
        status=PlantationStatus.SUBMITTED.value
    )
    db.add(plantation)
    db.commit()
    db.refresh(plantation)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_role=current_user.role,
        action="PLANTATION_REGISTERED",
        target_type="Plantation",
        target_id=str(plantation.id),
        details=f"Plantation '{plantation.name}' created and submitted for verification."
    )
    db.add(audit)
    db.commit()
    
    return plantation

@router.get("", response_model=List[PlantationResponse])
def list_plantations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role in [UserRole.ADMIN.value, UserRole.AUDITOR.value]:
        return db.query(Plantation).order_by(Plantation.created_at.desc()).all()
    elif current_user.role == UserRole.FARMER.value:
        return db.query(Plantation).filter(Plantation.farmer_id == current_user.id).order_by(Plantation.created_at.desc()).all()
    else:
        # Buyers can see submitted/verified plantations
        return db.query(Plantation).filter(Plantation.status.in_([PlantationStatus.VERIFIED.value, PlantationStatus.SUBMITTED.value])).all()

@router.get("/{id}", response_model=PlantationResponse)
def get_plantation(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plantation = db.query(Plantation).filter(Plantation.id == id).first()
    if not plantation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantation not found")
        
    # Check permissions
    if current_user.role == UserRole.FARMER.value and plantation.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this plantation")
        
    return plantation

@router.put("/{id}/evidence", response_model=PlantationResponse)
def update_plantation_evidence(
    id: int,
    evidence_in: PlantationEvidenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plantation = db.query(Plantation).filter(Plantation.id == id).first()
    if not plantation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantation not found")
        
    if current_user.role == UserRole.FARMER.value and plantation.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this plantation")
        
    if evidence_in.image_url is not None:
        plantation.image_url = evidence_in.image_url
    if evidence_in.soil_soc_pct is not None:
        plantation.soil_soc_pct = evidence_in.soil_soc_pct
    if evidence_in.soil_depth_cm is not None:
        plantation.soil_depth_cm = evidence_in.soil_depth_cm
    if evidence_in.soil_type is not None:
        plantation.soil_type = evidence_in.soil_type
        
    db.commit()
    db.refresh(plantation)
    return plantation

@router.post("/{id}/image")
@router.post("/{id}/evidence")
async def upload_image_for_plantation(
    id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plantation = db.query(Plantation).filter(Plantation.id == id).first()
    if not plantation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantation not found")
        
    if current_user.role == UserRole.FARMER.value and plantation.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this plantation")

    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp", ".tiff"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image format. Allowed formats: {', '.join(allowed_extensions)}"
        )
        
    unique_filename = f"plantation_{id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    plantation.image_url = f"/uploads/{unique_filename}"
    db.commit()
    db.refresh(plantation)
    
    return {
        "message": "Image uploaded and attached to plantation successfully",
        "image_url": plantation.image_url,
        "plantation_id": plantation.id
    }
