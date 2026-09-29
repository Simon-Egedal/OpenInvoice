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

def test_setup_schema_defaults_to_local_self_hosted_services():
    values = SetupIn()
    assert values.database_mode == "bundled"
    assert values.email_provider == "console"
    assert values.storage_provider == "local"
    assert values.banking_provider == "mock"
