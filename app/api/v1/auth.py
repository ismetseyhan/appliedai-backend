from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.entities.user import User
from app.schemas.user import UserResponse
from app.api.deps import get_current_user, security

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register user after Firebase signup",
    responses={
        201: {"description": "User successfully registered"},
        400: {"description": "User already exists"},
        401: {"description": "Invalid or expired token"}
    }
)
async def register_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Register user in backend database after Firebase registration

    Flow:
    1. User registers with Firebase on frontend
    2. Frontend gets Firebase token
    3. Frontend calls this endpoint with token
    4. Backend creates user in PostgreSQL
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

    firebase_uid = decoded_token.get("uid")
    email = decoded_token.get("email")
    name = decoded_token.get("name")

    # Check if user already exists
    existing_user = db.query(User).filter(User.id == firebase_uid).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already registered"
        )

    # Create user
    new_user = User(
        id=firebase_uid,
        email=email,
        display_name=name
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user info"
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user info

    Requires: Authorization: Bearer <firebase_token>
    """
    return current_user
