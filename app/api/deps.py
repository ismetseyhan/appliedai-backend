from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.models.user import User

# HTTPBearer security scheme for Swagger UI
security = HTTPBearer(
    scheme_name="HTTPBearer",
    description="Enter your Firebase ID token"
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Verify Firebase token and return user from database

    Expects: Authorization: Bearer <firebase_token>
    """
    # Get token from credentials
    token = credentials.credentials

    # Verify Firebase token
    decoded_token = verify_firebase_token(token)
    if not decoded_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    # Get user from database
    firebase_uid = decoded_token.get("uid")
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please register first."
        )

    return user
