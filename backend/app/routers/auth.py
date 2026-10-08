from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User, UserRole
from ..models.audit_log import AuditLog
from ..schemas.schemas import UserCreate, UserLogin, UserResponse, Token
from ..core.security import verify_password, get_password_hash, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )
        
    # Role is validated by UserCreate (FARMER, BUYER or AUDITOR only; ADMIN cannot self-register)
    role_val = user_in.role
    db_user = User(
        email=user_in.email.lower(),
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=role_val,
        phone=user_in.phone,
        organization=user_in.organization
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Audit log
    audit = AuditLog(
        user_id=db_user.id,
        user_email=db_user.email,
        user_role=db_user.role,
        action="USER_REGISTER",
        target_type="User",
        target_id=str(db_user.id),
        details=f"User registered with role {db_user.role}"
    )
    db.add(audit)
    db.commit()
    
    access_token = create_access_token(data={"sub": db_user.email, "role": db_user.role, "uid": db_user.id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": db_user
    }

@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_data.email.lower()).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )
        
    # Optional role check if supplied
    if login_data.role:
        req_role = login_data.role.upper()
        if req_role != user.role.upper() and not ({req_role, user.role.upper()} == {"ADMIN", "AUDITOR"}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Account exists but registered role is '{user.role}', not '{login_data.role}'."
            )
        
    access_token = create_access_token(data={"sub": user.email, "role": user.role, "uid": user.id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/login-form", response_model=Token)
def login_form(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username.lower()).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )
    access_token = create_access_token(data={"sub": user.email, "role": user.role, "uid": user.id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
