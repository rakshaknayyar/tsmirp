"""Authentication routes: register, login, refresh, and "who am I"."""

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import login_limiter
from app.core.security import (
    DUMMY_HASH,
    REFRESH,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import Role, User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services.audit import record_event
from app.services.users import EmailAlreadyRegistered, create_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: DbSession) -> User:
    """Public sign-up. Always creates a TOURIST account (staff are created by an admin)."""
    try:
        user = create_user(
            db,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            role=Role.TOURIST,
        )
    except EmailAlreadyRegistered:
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail already registered") from None
    record_event(
        db, "user.registered", actor_user_id=user.id, target_type="user", target_id=user.id
    )
    db.commit()
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: DbSession) -> TokenResponse:
    email = body.email.lower()
    client_ip = request.client.host if request.client else "unknown"
    login_limiter.check(f"{client_ip}:{email}")

    user = db.scalar(select(User).where(User.email == email))
    # Always run one hash check, even for unknown e-mails, so timing does not reveal accounts.
    password_ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)

    if user is None or not password_ok or not user.is_active:
        # The attempted e-mail is not stored, only the account id if it exists.
        record_event(
            db, "auth.login_failed", target_type="user", target_id=user.id if user else None
        )
        db.commit()
        # Same message for "no such user" and "wrong password".
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect e-mail or password")

    record_event(
        db, "auth.login_succeeded", actor_user_id=user.id, target_type="user", target_id=user.id
    )
    db.commit()
    return _tokens_for(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: DbSession) -> TokenResponse:
    """Swap a valid refresh token for a new pair of tokens."""
    try:
        payload = decode_token(body.refresh_token, REFRESH)
    except TokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from None
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return _tokens_for(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
