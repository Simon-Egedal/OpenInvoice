import asyncio
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.router import router, list_accounts
from app.auth import admin_membership, current_user, hash_password, verify_password
from app.models.entities import User, OrganizationMember, AuditLog
from app.providers.email import ConsoleEmailProvider, SMTPEmailProvider
from app.schemas import AccountCreateIn, ProfileUpdateIn, PasswordChangeIn
from app.services import create_member_account, change_user_password, update_user_profile


class AccountDB:
    def __init__(self, duplicate=False):
        self.duplicate = duplicate
        self.added = []
        self.statements = []
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.refresh = AsyncMock()

    async def scalar(self, statement):
        self.statements.append(str(statement))
        if len(self.statements) == 1:
            return SimpleNamespace(id=uuid4()) if self.duplicate else None
        return SimpleNamespace(name="Example organization")

    def add(self, obj):
        if isinstance(obj, User):
            obj.id = uuid4()
        self.added.append(obj)

    async def flush(self):
        pass


@pytest.mark.parametrize("role", ["member", "admin"])
def test_account_creation_hashes_password_sends_email_and_scopes_membership(role):
    db = AccountDB()
    organization_id = uuid4()
    provider = SimpleNamespace(send_account_credentials=AsyncMock())
    result = asyncio.run(create_member_account(db, AccountCreateIn(email="New@Example.com", role=role),
                         SimpleNamespace(organization_id=organization_id), SimpleNamespace(id=uuid4()), provider))
    user = next(obj for obj in db.added if isinstance(obj, User))
    membership = next(obj for obj in db.added if isinstance(obj, OrganizationMember))
    audit = next(obj for obj in db.added if isinstance(obj, AuditLog))
    email, password, sent_role, organization = provider.send_account_credentials.call_args.args
    assert email == "new@example.com" == result["email"]
    assert len(password) >= 24
    assert verify_password(password, user.password_hash)
    assert password not in str(result) and password not in str(audit.new_values)
    assert membership.organization_id == organization_id == audit.organization_id
    assert membership.role == role == sent_role
    assert organization == "Example organization"
    db.commit.assert_awaited_once()


def test_email_failure_rolls_back_account_without_exposing_password():
    db = AccountDB()
    provider = SimpleNamespace(send_account_credentials=AsyncMock(side_effect=RuntimeError("private SMTP detail")))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(create_member_account(db, AccountCreateIn(email="new@example.com", role="member"),
                    SimpleNamespace(organization_id=uuid4()), SimpleNamespace(id=uuid4()), provider))
    assert exc.value.status_code == 502
    assert "private SMTP detail" not in exc.value.detail
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


def test_existing_email_is_rejected_without_modifying_existing_user():
    db = AccountDB(duplicate=True)
    provider = SimpleNamespace(send_account_credentials=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(create_member_account(db, AccountCreateIn(email="existing@example.com", role="admin"),
                    SimpleNamespace(organization_id=uuid4()), SimpleNamespace(id=uuid4()), provider))
    assert exc.value.status_code == 409
    assert not db.added
    provider.send_account_credentials.assert_not_awaited()


def test_account_and_infrastructure_routes_require_admin_dependency():
    routes = [route for route in router.routes if route.path in {"/administration/accounts", "/settings/infrastructure"}]
    assert len(routes) == 4
    for route in routes:
        assert admin_membership in [dependency.call for dependency in route.dependant.dependencies]
    assert current_user in [dependency.call for dependency in router.routes if dependency.path == "/auth/profile" for dependency in dependency.dependant.dependencies]


def test_account_list_is_scoped_to_authenticated_organization():
    statements = []
    class DB:
        async def execute(self, statement):
            statements.append(str(statement.compile(compile_kwargs={"literal_binds": True})))
            return SimpleNamespace(all=lambda: [])
    organization_id = uuid4()
    assert asyncio.run(list_accounts(SimpleNamespace(organization_id=organization_id), DB())) == []
    assert "organization_members.organization_id" in statements[0]
    assert organization_id.hex in statements[0].replace("-", "")


def test_password_change_requires_current_password_and_replaces_hash():
    db = AccountDB()
    user = User(password_hash=hash_password("old password 123"))
    with pytest.raises(HTTPException):
        asyncio.run(change_user_password(db, user, "wrong password", "new password 123"))
    assert verify_password("old password 123", user.password_hash)
    db.commit.assert_not_awaited()
    asyncio.run(change_user_password(db, user, "old password 123", "new password 123"))
    assert verify_password("new password 123", user.password_hash)
    assert not verify_password("old password 123", user.password_hash)


def test_name_update_and_request_validation():
    db = AccountDB()
    user = User(full_name="Old name")
    payload = ProfileUpdateIn(full_name="  New name  ")
    asyncio.run(update_user_profile(db, user, payload.full_name))
    assert user.full_name == "New name"
    with pytest.raises(ValidationError):
        ProfileUpdateIn(full_name="   ")
    with pytest.raises(ValidationError):
        AccountCreateIn(email="invalid", role="member")
    with pytest.raises(ValidationError):
        AccountCreateIn(email="new@example.com", role="owner")
    with pytest.raises(ValidationError):
        PasswordChangeIn(current_password="old", new_password="short")


def test_console_provider_does_not_claim_credentials_were_delivered():
    with pytest.raises(RuntimeError, match="Configure SMTP"):
        asyncio.run(ConsoleEmailProvider().send_account_credentials("new@example.com", "secret", "member", "Example"))


def test_smtp_credentials_message_contains_login_and_password(monkeypatch):
    from app.providers.email import settings
    messages = []
    monkeypatch.setattr(SMTPEmailProvider, "_send_message", lambda self, message: messages.append(message))
    asyncio.run(SMTPEmailProvider().send_account_credentials("new@example.com", "generated secret", "admin", "Example"))
    assert messages[0]["To"] == "new@example.com"
    assert "generated secret" in messages[0].get_content()
    assert settings.frontend_url.rstrip("/") + "/auth" in messages[0].get_content()
