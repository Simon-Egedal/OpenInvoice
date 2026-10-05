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
from app.services import change_user_password, update_user_profile


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


def test_smtp_message_delivery_uses_provider_without_generated_password(monkeypatch):
    messages = []
    monkeypatch.setattr(SMTPEmailProvider, "_send_message", lambda self, message: messages.append(message))
    asyncio.run(SMTPEmailProvider().send_message("new@example.com", "Invitation", "Use an expiring link"))
    assert messages[0]["To"] == "new@example.com"
    assert messages[0].get_content().strip() == "Use an expiring link"
