import firebase_admin
from firebase_admin import credentials, auth
from typing import Optional
import json
import os


def initialize_firebase():
    """
    Initialize Firebase Admin SDK with Storage

    Requires: GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_SERVICE_ACCOUNT_JSON
    """
    if not firebase_admin._apps:
        from app.core.config import settings

        # (Coolify deployment)
        json_str = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
        if json_str:
            try:
                cred_dict = json.loads(json_str)
                cred = credentials.Certificate(cred_dict)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid FIREBASE_SERVICE_ACCOUNT_JSON: {e}")
        else:
            # Fallback to file path (local development)
            cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)

        firebase_admin.initialize_app(cred, {
            'storageBucket': settings.FIREBASE_STORAGE_BUCKET
        })


def verify_firebase_token(token: str) -> Optional[dict]:
    """
    Verify Firebase ID token and return decoded token

    Based on: https://firebase.google.com/docs/auth/admin/verify-id-tokens

    Args:
        token: Firebase ID token from client

    Returns:
        Decoded token dict with 'uid', 'email', etc. or None if invalid

    Example:
        decoded_token = verify_firebase_token(id_token)
        uid = decoded_token['uid']
    """
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except auth.ExpiredIdTokenError:
        print("Token has expired")
        return None
    except auth.InvalidIdTokenError:
        print("Invalid ID token")
        return None
    except Exception as e:
        print(f"Token verification failed: {e}")
        return None
