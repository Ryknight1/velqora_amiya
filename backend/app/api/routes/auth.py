import uuid

from fastapi import APIRouter, Depends

from ...dependencies import Container, current_user, get_container, rate_limit_general
from ...exceptions import AuthError, ConflictError
from ...schemas.auth_schema import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from ...security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(rate_limit_general)])

# Pre-computed so that unknown-email logins take the same time as wrong-password logins.
_DUMMY_HASH = hash_password("velqora-dummy-password")


def _token_response(c: Container, user: dict) -> TokenResponse:
    ttl = c.settings.jwt_expire_minutes
    return TokenResponse(access_token=create_token(user["id"], c.settings.jwt_secret, ttl), expires_in=ttl * 60,
                         user=UserPublic(id=user["id"], email=user["email"], name=user.get("name")))


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, c: Container = Depends(get_container)) -> TokenResponse:
    if c.users.get_by_email(body.email):
        raise ConflictError("An account with this email already exists.", code="email_taken")
    user_id = uuid.uuid4().hex
    c.users.create(user_id, body.email, body.name, hash_password(body.password))
    return _token_response(c, c.users.get(user_id))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, c: Container = Depends(get_container)) -> TokenResponse:
    user = c.users.get_by_email(body.email)
    ok = verify_password(body.password, user["password_hash"] if user else _DUMMY_HASH)
    if not user or not ok:
        raise AuthError("Incorrect email or password.", code="invalid_credentials")
    return _token_response(c, user)


@router.get("/me", response_model=UserPublic)
async def me(user: dict = Depends(current_user)) -> UserPublic:
    return UserPublic(id=user["id"], email=user["email"], name=user.get("name"))
