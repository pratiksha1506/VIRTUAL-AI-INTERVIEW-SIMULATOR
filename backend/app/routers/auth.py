from fastapi import APIRouter, Response, Request, HTTPException, status
from typing import Dict, Any, Optional
from ..models import RegisterRequest, LoginRequest
from ..database import create_user, get_user_by_email, get_user_by_id, verify_password
from ..config import SESSION_SECRET
import hmac
import hashlib

router = APIRouter(prefix="/api/auth", tags=["auth"])

def sign_session_id(user_id: int) -> str:
    signature = hmac.new(SESSION_SECRET.encode(), str(user_id).encode(), hashlib.sha256).hexdigest()
    return f"{user_id}.{signature}"

def verify_session_id(cookie_val: Optional[str]) -> Optional[int]:
    if not cookie_val or "." not in cookie_val:
        return None
    user_id_str, sig = cookie_val.split(".", 1)
    expected = hmac.new(SESSION_SECRET.encode(), user_id_str.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig, expected):
        try:
            return int(user_id_str)
        except ValueError:
            return None
    return None

def get_current_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    # 1. Check Authorization header first if explicitly provided
    auth_hdr = request.headers.get("Authorization", "")
    if auth_hdr.startswith("Bearer "):
        user_id = verify_session_id(auth_hdr[7:].strip())
        if user_id:
            return get_user_by_id(user_id)

    # 2. Check cookie
    cookie = request.cookies.get("session_id")
    user_id = verify_session_id(cookie)
    if user_id:
        return get_user_by_id(user_id)
    return None

@router.post("/register")
async def register(req: RegisterRequest, response: Response):
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    user = create_user(req.name, req.email, req.password, role="job_seeker")
    token = sign_session_id(user["id"])
    response.set_cookie(key="session_id", value=token, httponly=True, samesite="lax", max_age=86400 * 7)
    return {"user": user, "token": token}

@router.post("/login")
async def login(req: LoginRequest, response: Response):
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if user["role"] != "job_seeker":
        raise HTTPException(status_code=403, detail="Please use the admin login portal.")
    token = sign_session_id(user["id"])
    response.set_cookie(key="session_id", value=token, httponly=True, samesite="lax", max_age=86400 * 7)
    safe_user = {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}
    return {"user": safe_user, "token": token}

@router.post("/admin-login")
async def admin_login(req: LoginRequest, response: Response):
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied. Admin role required.")
    token = sign_session_id(user["id"])
    response.set_cookie(key="session_id", value=token, httponly=True, samesite="lax", max_age=86400 * 7)
    safe_user = {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}
    return {"user": safe_user, "token": token}

@router.get("/me")
async def get_me(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}}

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("session_id")
    return {"message": "Logged out successfully."}
