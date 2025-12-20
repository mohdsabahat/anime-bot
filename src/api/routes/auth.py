"""
Authentication routes.

Provides endpoints for user authentication and token generation.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ..auth import authenticate_user, create_access_token
from ..config import api_settings
from ..schemas import Token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    """
    Authenticate user and return access token.

    Args:
        form_data: OAuth2 password request form with username and password.

    Returns:
        Token: JWT access token.

    Raises:
        HTTPException: If authentication fails.
    """
    if not authenticate_user(form_data.username, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=api_settings.api_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": form_data.username},
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token)
