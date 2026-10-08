"""Reusable FastAPI dependencies: database session, logged-in user, and role checks.

Usage in a route:  def my_route(user: AdminUser, db: DbSession): ...
FastAPI runs the checks before the route; a failed check returns 401 or 403 automatically.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import ACCESS, TokenError, decode_token
from app.models.user import Role, User

DbSession = Annotated[Session, Depends(get_db)]

# Reads the "Authorization: Bearer <token>" header. auto_error=False so we return our own 401.
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_token(credentials.credentials, ACCESS)
    except TokenError:
        raise unauthorized from None

    # Load the user fresh from the database, so a deactivated account or a changed role
    # takes effect immediately, not only when the token expires.
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed: Role) -> Callable[[User], User]:
    def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission for this action",
            )
        return user

    return checker


TouristUser = Annotated[User, Depends(require_roles(Role.TOURIST))]
AuditReader = Annotated[User, Depends(require_roles(Role.SUPERVISOR, Role.ADMINISTRATOR))]
AdminUser = Annotated[User, Depends(require_roles(Role.ADMINISTRATOR))]
