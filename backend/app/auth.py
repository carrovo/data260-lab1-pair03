"""
Shared JWT + bcrypt auth utilities.

Used by both the company-side routes here and (once merged) Xuanhua's
student-side routes — keep this file single-sourced rather than duplicating
it in both halves of the app.
"""
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES

# Plain bearer-token scheme — NOT OAuth2PasswordBearer. We don't implement an
# OAuth2 password-grant token endpoint (no /api/auth/token route exists), so
# OAuth2PasswordBearer's Swagger "Authorize" dialog has nowhere valid to POST
# credentials and fails with 404. HTTPBearer instead gives Swagger a single
# "Value" field — paste the access_token string you get back from
# POST /api/companies/auth/login (or /students/auth/login) there directly.
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(subject: str, role: str, extra: Optional[dict] = None) -> str:
    """role is 'student' or 'company' — included in the token so endpoints
    can tell which persona is calling without a second DB lookup."""
    payload = {
        "sub": subject,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES),
        "iat": datetime.utcnow(),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_claims(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_token(credentials.credentials)


def require_company(claims: dict = Depends(get_current_claims)) -> dict:
    if claims.get("role") != "company":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company account required for this action",
        )
    return claims


def require_student(claims: dict = Depends(get_current_claims)) -> dict:
    if claims.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student account required for this action",
        )
    return claims
