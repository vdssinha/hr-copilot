from pydantic import BaseModel, EmailStr
from app.models.employee import EmployeeRole


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: EmployeeRole
    user_id: int
    name: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    employee_code: str
    role: EmployeeRole = EmployeeRole.EMPLOYEE
