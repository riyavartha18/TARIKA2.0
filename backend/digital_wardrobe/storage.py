import os
import io
import time
import uuid
import hmac
import hashlib
from typing import Optional, Tuple
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class WardrobeStorageManager:
    """
    Manages private, per-customer file storage for digital wardrobe assets.
    Supports:
    1. AWS S3 with presigned short-lived URLs (when AWS env vars are present).
    2. Secure local storage fallback with HMAC-signed download URLs for offline / dev / tests.
    """

    def __init__(self):
        self.bucket_name = os.environ.get('AWS_STORAGE_BUCKET_NAME') or getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
        self.region = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
        self.access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        self.secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.use_s3 = bool(self.bucket_name and self.access_key and self.secret_key and BOTO3_AVAILABLE)
        
        if self.use_s3:
            self.s3_client = boto3.client(
                's3',
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            )
        else:
            self.s3_client = None

    def upload_file(
        self,
        customer_id: str,
        item_uuid: str,
        filename: str,
        file_bytes: bytes,
        content_type: str = 'image/webp'
    ) -> str:
        """
        Uploads an image into the customer's isolated folder.
        Key structure: wardrobe/{customer_id}/{item_uuid}/{filename}
        Returns the persistent storage key or relative path.
        """
        s_cust = str(customer_id).strip()
        key = f"wardrobe/{s_cust}/{item_uuid}/{filename}"

        if self.use_s3:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_bytes,
                ContentType=content_type,
            )
            return key
        else:
            # Local private storage
            local_rel_path = f"private_wardrobe/{s_cust}/{item_uuid}/{filename}"
            full_path = os.path.join(settings.MEDIA_ROOT, local_rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'wb') as f:
                f.write(file_bytes)
            return local_rel_path

    def get_signed_url(self, file_key: Optional[str], customer_id: str, expiry_seconds: int = 3600) -> Optional[str]:
        """
        Generates a signed, short-lived URL.
        Only the owner with matching customer_id can generate or access this URL.
        """
        if not file_key:
            return None

        # If file_key is already a complete absolute URL (e.g. external asset), return it directly
        if file_key.startswith('http://') or file_key.startswith('https://') or file_key.startswith('data:'):
            return file_key

        # S3 presigned URL
        if self.use_s3 and file_key.startswith('wardrobe/'):
            try:
                # Ensure customer_id matches the path prefix
                parts = file_key.split('/')
                if len(parts) >= 3 and str(parts[1]) != str(customer_id):
                    return None  # Privacy boundary
                
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': file_key},
                    ExpiresIn=expiry_seconds
                )
                return url
            except Exception as e:
                return None

        # Local signed token URL fallback
        # Signature format: /api/wardrobe/media-serve/?key=...&cid=...&exp=...&sig=...
        exp = int(time.time()) + expiry_seconds
        secret = settings.SECRET_KEY.encode('utf-8')
        message = f"{file_key}:{customer_id}:{exp}".encode('utf-8')
        sig = hmac.new(secret, message, hashlib.sha256).hexdigest()
        
        backend_origin = getattr(settings, 'BACKEND_ORIGIN', None) or os.environ.get('BACKEND_URL', 'http://127.0.0.1:8000')
        backend_origin = backend_origin.rstrip('/')
        return f"{backend_origin}/api/wardrobe/media-serve/?key={file_key}&cid={customer_id}&exp={exp}&sig={sig}"

    def verify_local_signed_url(self, file_key: str, customer_id: str, exp_timestamp: int, signature: str) -> bool:
        """
        Validates HMAC signature and timestamp for locally stored files.
        """
        if int(time.time()) > int(exp_timestamp):
            return False
        secret = settings.SECRET_KEY.encode('utf-8')
        message = f"{file_key}:{customer_id}:{exp_timestamp}".encode('utf-8')
        expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def delete_item_files(self, customer_id: str, item_uuid: str):
        """
        Deletes all stored versions of an item (original, transparent, flat, thumbnail).
        """
        s_cust = str(customer_id).strip()
        prefix = f"wardrobe/{s_cust}/{item_uuid}/"

        if self.use_s3:
            try:
                paginator = self.s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
                for page in pages:
                    if 'Contents' in page:
                        del_keys = [{'Key': obj['Key']} for obj in page['Contents']]
                        self.s3_client.delete_objects(Bucket=self.bucket_name, Delete={'Objects': del_keys})
            except Exception:
                pass
        else:
            local_dir = os.path.join(settings.MEDIA_ROOT, 'private_wardrobe', s_cust, item_uuid)
            if os.path.exists(local_dir):
                import shutil
                shutil.rmtree(local_dir, ignore_errors=True)

    def delete_all_customer_files(self, customer_id: str):
        """
        Deletes all wardrobe files belonging to a customer (privacy delete-all).
        """
        s_cust = str(customer_id).strip()
        prefix = f"wardrobe/{s_cust}/"

        if self.use_s3:
            try:
                paginator = self.s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
                for page in pages:
                    if 'Contents' in page:
                        del_keys = [{'Key': obj['Key']} for obj in page['Contents']]
                        self.s3_client.delete_objects(Bucket=self.bucket_name, Delete={'Objects': del_keys})
            except Exception:
                pass
        else:
            local_dir = os.path.join(settings.MEDIA_ROOT, 'private_wardrobe', s_cust)
            if os.path.exists(local_dir):
                import shutil
                shutil.rmtree(local_dir, ignore_errors=True)
