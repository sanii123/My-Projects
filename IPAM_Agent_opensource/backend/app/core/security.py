"""JWT auth. docs/architecture.md section 8 and the auth item in section 11.

Standalone JWT for now: self-issued tokens, no external identity provider.
If/when this needs to sit behind existing SSO, that's a change to how a
token gets minted (or to verifying someone else's IdP-issued JWT here
instead) - every caller still depends on get_current_user, so nothing above
this module needs to change.
"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token")


class Scope:
    READ = "ipam:read"
    WRITE = "ipam:write"


class UserContext(BaseModel):
    """Permission scope for the calling user - not the agent's own service
    account. docs/architecture.md 4.3: "the runtime should not expose write
    tools to a read-only user, full stop." Every check against this, not a
    blanket credential, is what enforces that.
    """

    user_id: str
    scopes: list[str] = [Scope.READ]

    @property
    def can_write(self) -> bool:
        return Scope.WRITE in self.scopes


def create_access_token(user_id: str, scopes: list[str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "scopes": scopes,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> UserContext:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return UserContext(user_id=payload["sub"], scopes=payload.get("scopes", [Scope.READ]))


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserContext:
    return decode_access_token(token)


def require_write_scope(user: UserContext = Depends(get_current_user)) -> UserContext:
    if not user.can_write:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Write access required")
    return user
