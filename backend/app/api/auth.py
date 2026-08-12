"""Dev-only token issuance.

Auth is flagged as an open decision in docs/architecture.md section 11 -
standalone JWT chosen for now (see app/core/security.py). This endpoint
exists purely so the rest of the API is exercisable before a real user
store or SSO integration is wired in.

TODO before anything but local dev touches this: replace with a real
username/password check against a user store, or swap this route out
entirely for verifying tokens issued by an external IdP.
"""

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import Scope, create_access_token

router = APIRouter()


@router.post("/auth/token")
async def issue_token(form: OAuth2PasswordRequestForm = Depends()) -> dict:
    # Any username currently gets a read+write token - intentional for local dev,
    # not a real auth check. See module docstring.
    token = create_access_token(user_id=form.username, scopes=[Scope.READ, Scope.WRITE])
    return {"access_token": token, "token_type": "bearer"}
