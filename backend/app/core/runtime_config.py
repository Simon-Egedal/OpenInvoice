"""Encrypted self-hosted settings stored on the persistent application volume."""
import base64
import json
import os
from pathlib import Path
from typing import Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def config_path() -> Path:
    configured = os.getenv("APP_CONFIG_PATH")
    if configured:
        return Path(configured)
    return Path(os.getenv("LOCAL_STORAGE_PATH", "./storage")) / "openinvoice-settings.enc"

def _key_path() -> Path:
    return config_path().with_suffix(".key")

def get_or_create_secret() -> str:
    """Create a persistent encryption/session key on first run."""
    path = _key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        key = path.read_bytes()
    else:
        key = AESGCM.generate_key(bit_length=256)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(key)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return base64.urlsafe_b64encode(key).decode("ascii")

def _read_settings() -> dict[str, Any] | None:
    path = config_path()
    if not path.exists():
        return None
    key = _key_path().read_bytes()
    blob = path.read_bytes()
    if not blob.startswith(b"OI1"):
        raise RuntimeError("Stored OpenInvoice settings have an unsupported format")
    plaintext = AESGCM(key).decrypt(blob[3:15], blob[15:], b"openinvoice-settings-v1")
    return json.loads(plaintext)

def apply_saved_settings(settings: Any) -> None:
    values = _read_settings()
    if not values:
        return
    for name, value in values.items():
        if hasattr(settings, name) and name != "secret_key":
            setattr(settings, name, value)

def save_settings(values: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = _key_path().read_bytes()
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, json.dumps(values, separators=(",", ":")).encode(), b"openinvoice-settings-v1")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(b"OI1" + nonce + ciphertext)
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    os.replace(temporary, path)

def read_saved_settings() -> dict[str, Any] | None:
    return _read_settings()

IGNORED_APPLIED_KEYS = {
    "setup_completed",
    "database_mode",
    "database_host",
    "database_port",
    "database_name",
    "database_username",
    "database_password",
    "database_ssl",
    "secret_key",
}

def settings_are_applied(settings: Any, values: dict[str, Any] | None) -> bool:
    if not values or not values.get("setup_completed"):
        return False
    return all(
        getattr(settings, name, object()) == value
        for name, value in values.items()
        if name not in IGNORED_APPLIED_KEYS and hasattr(settings, name)
    )

