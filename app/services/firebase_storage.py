from firebase_admin import storage
from typing import Optional
from datetime import datetime, timedelta


class FirebaseStorageService:
    """
    Firebase Storage service for document management

    Storage structure: documents/{user_id}/{filename}
    """

    def __init__(self, bucket_name: str):
        self.bucket = storage.bucket(bucket_name)

    def upload_file(
        self,
        file_content: bytes,
        user_id: str,
        filename: str
    ) -> Optional[str]:
        """
        Upload file to Firebase Storage

        Args:
            file_content: File bytes
            user_id: User ID (Firebase UID)
            filename: Original filename

        Returns:
            gs:// path or None if error
        """
        try:
            storage_path = f"documents/{user_id}/{filename}"
            blob = self.bucket.blob(storage_path)

            blob.upload_from_string(
                file_content,
                content_type='application/pdf'
            )

            return f"gs://{self.bucket.name}/{storage_path}"
        except Exception as e:
            print(f"Error uploading file: {e}")
            return None

    def delete_file(self, storage_path: str) -> bool:
        """
        Delete file from Firebase Storage

        Args:
            storage_path: gs:// URL or path

        Returns:
            True if deleted, False if error
        """
        try:
            if storage_path.startswith('gs://'):
                parts = storage_path.replace('gs://', '').split('/', 1)
                if len(parts) == 2:
                    path = parts[1]
                else:
                    return False
            else:
                path = storage_path

            blob = self.bucket.blob(path)

            if not blob.exists():
                return False

            blob.delete()
            return True
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False

    def get_download_url(
        self,
        storage_path: str,
        expiration_hours: int = 1
    ) -> Optional[str]:
        """
        Get signed download URL for private access

        Args:
            storage_path: gs:// URL or path
            expiration_hours: How long the URL should be valid (default 1 hour)

        Returns:
            Signed URL or None if error
        """
        try:
            if storage_path.startswith('gs://'):
                parts = storage_path.replace('gs://', '').split('/', 1)
                if len(parts) == 2:
                    path = parts[1]
                else:
                    return None
            else:
                path = storage_path

            blob = self.bucket.blob(path)

            if not blob.exists():
                return None

            expiration_time = datetime.utcnow() + timedelta(hours=expiration_hours)
            url = blob.generate_signed_url(
                expiration=expiration_time,
                method='GET'
            )
            return url
        except Exception as e:
            print(f"Error generating download URL: {e}")
            return None

    def file_exists(self, storage_path: str) -> bool:
        """
        Check if file exists in storage

        Args:
            storage_path: gs:// URL or path

        Returns:
            True if exists, False otherwise
        """
        try:
            if storage_path.startswith('gs://'):
                parts = storage_path.replace('gs://', '').split('/', 1)
                if len(parts) == 2:
                    path = parts[1]
                else:
                    return False
            else:
                path = storage_path

            blob = self.bucket.blob(path)
            return blob.exists()
        except Exception as e:
            print(f"Error checking file existence: {e}")
            return False
