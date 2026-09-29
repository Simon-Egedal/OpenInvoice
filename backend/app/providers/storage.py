from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4
import boto3
from app.core.config import settings

class StorageProvider(ABC):
    @abstractmethod
    async def put(self, content: bytes, filename: str, content_type: str)->str: ...
    @abstractmethod
    async def get(self, key: str)->bytes: ...
class LocalStorageProvider(StorageProvider):
    def __init__(self): self.root=Path(settings.local_storage_path).resolve()
    async def put(self, content, filename, content_type):
        key=str(uuid4()); self.root.mkdir(parents=True,exist_ok=True); (self.root/key).write_bytes(content); return key
    async def get(self,key):
        if Path(key).name!=key: raise ValueError("Invalid storage key")
        return (self.root/key).read_bytes()
class S3StorageProvider(StorageProvider):
    """Generic S3-compatible implementation; configure endpoint for MinIO/R2/etc."""
    def __init__(self):
        self.client=boto3.client("s3",endpoint_url=__import__("os").getenv("S3_ENDPOINT_URL") or None,aws_access_key_id=__import__("os").getenv("S3_ACCESS_KEY_ID"),aws_secret_access_key=__import__("os").getenv("S3_SECRET_ACCESS_KEY"),region_name=__import__("os").getenv("S3_REGION","eu-central-1")); self.bucket=__import__("os").environ["S3_BUCKET"]
    async def put(self,content,filename,content_type):
        key=str(uuid4()); self.client.put_object(Bucket=self.bucket,Key=key,Body=content,ContentType=content_type); return key
    async def get(self,key): return self.client.get_object(Bucket=self.bucket,Key=key)["Body"].read()

def storage_provider()->StorageProvider:
    return S3StorageProvider() if settings.storage_provider=="s3" else LocalStorageProvider()
