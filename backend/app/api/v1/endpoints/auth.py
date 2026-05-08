from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.employee import Employee
from app.core.security import verify_password, create_access_token, hash_password
from app.schemas.auth import LoginRequest, TokenResponse, RegisterRequest
from app.schemas.common import APIResponse

router = APIRouter()


@router.post("/login", response_model=APIResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(Employee).filter(Employee.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return APIResponse.ok(TokenResponse(
        access_token=token,
        role=user.role,
        user_id=user.id,
        name=user.name,
    ))


@router.post("/register", response_model=APIResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(Employee).filter(Employee.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(Employee).filter(Employee.employee_code == payload.employee_code).first():
        raise HTTPException(status_code=400, detail="Employee code already in use")

    user = Employee(
        name=payload.name,
        email=payload.email,
        employee_code=payload.employee_code,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return APIResponse.ok({"id": user.id, "email": user.email, "role": user.role})
