import asyncio
from types import SimpleNamespace
import pytest
from fastapi import HTTPException

from app.auth import admin_membership
from app.models.entities import MemberRole, OrganizationMember
from app.schemas import InfrastructureSettingsIn
from app.services import get_infrastructure_config, prepare_infrastructure_update


def test_admin_membership_allows_owner_and_admin():
    async def check():
        owner_member = SimpleNamespace(role=MemberRole.owner)
        admin_member = SimpleNamespace(role=MemberRole.admin)
        assert await admin_membership(owner_member) == owner_member
        assert await admin_membership(admin_member) == admin_member

    asyncio.run(check())


def test_admin_membership_rejects_non_admin_roles():
    async def check(role):
        member = SimpleNamespace(role=role)
        with pytest.raises(HTTPException) as exc:
            await admin_membership(member)
        assert exc.value.status_code == 403

    for non_admin_role in ("accountant", "member", "viewer", "approver"):
        asyncio.run(check(non_admin_role))


def test_get_infrastructure_config_masks_secrets_and_reports_status():
    saved = {
        "setup_completed": True,
        "database_mode": "bundled",
        "email_provider": "smtp",
        "smtp_host": "mail.example.com",
        "smtp_password": "super-secret-smtp-password",
        "storage_provider": "s3",
        "s3_bucket": "my-bucket",
        "s3_secret_access_key": "aws-secret-key-123",
        "banking_provider": "mock",
    }
    runtime = SimpleNamespace(
        postgres_host="localhost",
        postgres_db="openinvoice",
        postgres_user="openinvoice",
        postgres_password="bundled-pw",
        email_provider="console",
        smtp_host="",
        smtp_port=587,
        smtp_username="",
        smtp_from="OpenInvoice <invoices@example.com>",
        smtp_use_tls=True,
        smtp_password="",
        storage_provider="local",
        s3_endpoint_url="",
        s3_bucket="",
        s3_access_key_id="",
        s3_secret_access_key="",
        s3_region="eu-central-1",
        banking_provider="mock",
        enable_banking_app_id="",
        enable_banking_private_key_path="",
        session_cookie_secure=False,
    )

    config = get_infrastructure_config(saved, runtime)
    assert config["email_provider"] == "smtp"
    assert config["smtp_host"] == "mail.example.com"
    assert config["has_smtp_password"] is True
    # Verify plain secrets are NOT exposed in the output dictionary
    assert "super-secret-smtp-password" not in str(config.values())
    assert config["storage_provider"] == "s3"
    assert config["has_s3_secret"] is True
    assert "aws-secret-key-123" not in str(config.values())


def test_prepare_infrastructure_update_preserves_existing_secrets_when_blank():
    saved = {
        "database_password": "existing-db-pw",
        "smtp_password": "existing-smtp-pw",
        "s3_secret_access_key": "existing-s3-secret",
    }
    runtime = SimpleNamespace(
        database_url="postgresql+asyncpg://openinvoice:bundled-pw@localhost:5432/openinvoice",
        postgres_password="bundled-pw",
        smtp_password="",
        s3_secret_access_key="",
        local_storage_path="./storage",
    )

    payload = InfrastructureSettingsIn(
        database_mode="external",
        database_host="external-db.example.com",
        database_port=5432,
        database_name="mydb",
        database_username="myuser",
        database_password="",  # User left password blank to keep existing
        email_provider="smtp",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_password="",  # User left blank to keep existing
        storage_provider="s3",
        s3_bucket="mybucket",
        s3_access_key_id="key123",
        s3_secret_access_key="",  # User left blank to keep existing
        banking_provider="enable_banking",
        enable_banking_app_id="app-123",
        enable_banking_private_key_path="/keys/key.pem",
    )

    values, url = prepare_infrastructure_update(payload, saved, runtime)
    assert values["database_password"] == "existing-db-pw"
    assert values["smtp_password"] == "existing-smtp-pw"
    assert values["s3_secret_access_key"] == "existing-s3-secret"
    assert values["banking_provider"] == "enable_banking"
    assert values["enable_banking_app_id"] == "app-123"
    assert "external-db.example.com" in url
    assert "existing-db-pw" in url
