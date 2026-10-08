from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.security import get_current_user, get_password_hash, require_role
from ..database import get_db
from ..models.audit_log import AuditLog
from ..models.user import User, UserRole
from ..schemas.schemas import AdminUserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("", response_model=List[UserResponse])
def list_users(
    current_user: User = Depends(require_role([UserRole.ADMIN.value])),
    db: Session = Depends(get_db)
):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    user_in: AdminUserCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN.value])),
    db: Session = Depends(get_db),
):
    """ADMIN only: create an account. This is the only way to create AUDITOR accounts."""
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account with this email address already exists.")
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        phone=user_in.phone,
        organization=user_in.organization,
    )
    db.add(user)
    db.flush()
    db.add(AuditLog(
        user_id=current_user.id, user_email=current_user.email, user_role=current_user.role,
        action="ADMIN_USER_CREATED", target_type="User", target_id=str(user.id),
        details=f"{current_user.email} created {user.role} account {user.email}.",
    ))
    db.commit()
    db.refresh(user)
    return user
