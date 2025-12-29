"""API key authentication and validation."""
from typing import Optional
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.cost.models import APIKey
from app.cost.database import get_db

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme
security = HTTPBearer()


def hash_api_key(api_key: str) -> str:
    """Hash an API key using bcrypt."""
    return pwd_context.hash(api_key)


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify a plain API key against its hash."""
    return pwd_context.verify(plain_key, hashed_key)


async def get_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db),
) -> APIKey:
    """
    Validate API key from Authorization header and return API key record.

    Args:
        credentials: HTTP Bearer token credentials
        db: Database session

    Returns:
        APIKey database record

    Raises:
        HTTPException: If API key is invalid or inactive
    """
    api_key = credentials.credentials

    # Find API key by checking all stored keys (brute force for now, could be optimized)
    api_keys = db.query(APIKey).filter(APIKey.is_active == True).all()

    for stored_key in api_keys:
        if verify_api_key(api_key, stored_key.key_hash):
            return stored_key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "Bearer"},
    )

