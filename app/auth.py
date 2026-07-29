"""JWT verification + role loading. Shared secret with GoTrue (SUPABASE_JWT_SECRET)."""
import jwt
from fastapi import Depends, Header, HTTPException

from common.config import settings
from common.db import get_connection


class User:
    def __init__(self, user_id: str, email: str, role: str):
        self.user_id, self.email, self.role = user_id, email, role


def current_user(authorization: str = Header(...)) -> User:
    """Verify the Bearer JWT and load the caller's live role from profiles."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token, settings.supabase_jwt_secret,
            algorithms=["HS256"], audience="authenticated",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"Invalid token: {e}")

    user_id = payload["sub"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT role FROM profiles WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
    role = row[0] if row else "pending"
    return User(user_id, payload.get("email", ""), role)


def require_user(user: User = Depends(current_user)) -> User:
    """Reject pending users — they can log in but not query the KB."""
    if user.role == "pending":
        raise HTTPException(403, "Your access is pending admin approval.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Admin access required.")
    return user