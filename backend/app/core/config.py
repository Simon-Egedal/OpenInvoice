from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://openinvoice:change-this-password@localhost:5432/openinvoice"
    secret_key: str = "development-only-change-me"
    session_cookie_secure: bool = False
    frontend_url: str = "http://localhost:3000"
    local_storage_path: str = "./storage"
    storage_provider: str = "local"
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

