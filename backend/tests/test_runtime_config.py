from types import SimpleNamespace

from app.core.runtime_config import apply_saved_settings, get_or_create_secret, read_saved_settings, save_settings, settings_are_applied
from app.schemas import SetupIn

def test_runtime_credentials_are_encrypted_and_loaded(monkeypatch, tmp_path):
    config_file = tmp_path / "runtime.enc"
    monkeypatch.setenv("APP_CONFIG_PATH", str(config_file))
    first_secret = get_or_create_secret()
    save_settings({"setup_completed": True, "smtp_password": "smtp-private-value", "email_provider": "smtp"})

    assert b"smtp-private-value" not in config_file.read_bytes()
    assert read_saved_settings()["smtp_password"] == "smtp-private-value"
    assert get_or_create_secret() == first_secret

    settings = SimpleNamespace(email_provider="console", smtp_password="")
    apply_saved_settings(settings)
    assert settings.email_provider == "smtp"
    assert settings.smtp_password == "smtp-private-value"
    assert settings_are_applied(settings, read_saved_settings())

    settings.smtp_password = "old-password"
    assert not settings_are_applied(settings, read_saved_settings())

def test_settings_are_applied_ignores_database_helper_fields():
    saved = {
        "setup_completed": True,
        "database_mode": "external",
        "database_host": "db.example.com",
        "database_port": 5432,
        "database_name": "mydb",
        "database_username": "myuser",
        "database_password": "secret",
        "database_ssl": False,
        "database_url": "postgresql+asyncpg://myuser:secret@db.example.com:5432/mydb",
    }
    settings = SimpleNamespace(database_url="postgresql+asyncpg://myuser:secret@db.example.com:5432/mydb")
    assert settings_are_applied(settings, saved)

    settings.database_url = "postgresql+asyncpg://old"
    assert not settings_are_applied(settings, saved)

def test_setup_schema_defaults_to_local_self_hosted_services():
    values = SetupIn()
    assert values.database_mode == "bundled"
    assert values.email_provider == "console"
    assert values.storage_provider == "local"
    assert values.banking_provider == "mock"

