from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4
import boto3
import os
import asyncio
from app.core.config import settings

class StorageProvider(ABC):
    async def delete(self, key: str) -> None:
        raise NotImplementedError("This storage provider does not support cleanup")
    @abstractmethod
    async def put(self, content: bytes, filename: str, content_type: str)->str: ...
    @abstractmethod
    async def get(self, key: str)->bytes: ...
class LocalStorageProvider(StorageProvider):
    def __init__(self): self.root=Path(settings.local_storage_path).resolve()
    async def put(self, content, filename, content_type):
        key=str(uuid4())
        def write():
            self.root.mkdir(parents=True, exist_ok=True)
            (self.root / key).write_bytes(content)
        await asyncio.to_thread(write)
        return key
    async def get(self,key):
        if Path(key).name!=key: raise ValueError("Invalid storage key")
        return await asyncio.to_thread((self.root/key).read_bytes)
    async def delete(self, key):
        if Path(key).name != key: raise ValueError("Invalid storage key")
        await asyncio.to_thread((self.root / key).unlink, missing_ok=True)
class S3StorageProvider(StorageProvider):
    """Generic S3-compatible implementation; configure endpoint for MinIO/R2/etc."""
    def __init__(self):
        self.client=boto3.client("s3",endpoint_url=settings.s3_endpoint_url or None,aws_access_key_id=settings.s3_access_key_id or os.getenv("S3_ACCESS_KEY_ID"),aws_secret_access_key=settings.s3_secret_access_key or os.getenv("S3_SECRET_ACCESS_KEY"),region_name=settings.s3_region); self.bucket=settings.s3_bucket or os.getenv("S3_BUCKET","")
    async def put(self,content,filename,content_type):
        key=str(uuid4()); await asyncio.to_thread(self.client.put_object,Bucket=self.bucket,Key=key,Body=content,ContentType=content_type); return key
    async def get(self,key):
        def read():
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            with response["Body"] as body:
                return body.read()
        return await asyncio.to_thread(read)
    async def delete(self, key):
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)

def storage_provider()->StorageProvider:
    return S3StorageProvider() if settings.storage_provider=="s3" else LocalStorageProvider()
