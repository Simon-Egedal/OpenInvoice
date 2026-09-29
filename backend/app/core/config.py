from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = ""
    postgres_host: str = "localhost"
    postgres_db: str = "openinvoice"
    postgres_user: str = "openinvoice"
    postgres_password: str = "change-this-password"
    secret_key: str = ""
    session_cookie_secure: bool = False
    frontend_url: str = "http://localhost:3000"
    local_storage_path: str = "./storage"
    storage_provider: str = "local"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = "eu-central-1"
    email_provider: str = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "OpenInvoice <invoices@example.com>"
    smtp_use_tls: bool = True
    banking_provider: str = "mock"
    enable_banking_app_id: str = ""
    enable_banking_private_key_path: str = ""

settings = Settings()
if not settings.database_url:
    settings.database_url = URL.create("postgresql+asyncpg",username=settings.postgres_user,password=settings.postgres_password,host=settings.postgres_host,port=5432,database=settings.postgres_db).render_as_string(hide_password=False)

from app.core.runtime_config import apply_saved_settings, get_or_create_secret

settings.secret_key = settings.secret_key or get_or_create_secret()
apply_saved_settings(settings)
