import asyncio
from types import SimpleNamespace
from uuid import uuid4
import pytest
from pydantic import ValidationError

from app.auth import verify_password
from app.models.entities import MemberRole, Organization, User
from app.schemas import SetupAdminIn
from app.services import create_initial_admin, create_initial_organization


def test_setup_admin_schema_requires_minimum_password_length():
    with pytest.raises(ValidationError):
        SetupAdminIn(full_name="Admin", email="admin@example.com", password="short")
    
    valid = SetupAdminIn(full_name="Admin", email="admin@example.com", password="longenoughpassword123")
    assert valid.full_name == "Admin"
    assert valid.password == "longenoughpassword123"


def test_create_initial_organization_fails_if_users_already_exist():
    class ExistingUserDB:
        async def scalar(self, statement):
            return User(email="existing@example.com", full_name="Admin", password_hash="hash")

    async def check():
        with pytest.raises(ValueError, match="Setup has already been completed"):
            await create_initial_organization(ExistingUserDB(), name="Test Org")

    asyncio.run(check())


def test_create_initial_admin_fails_if_admin_already_exists():
    class ExistingAdminDB:
        async def scalar(self, statement):
            return User(email="existing@example.com", full_name="Admin", password_hash="hash")

    async def check():
        with pytest.raises(ValueError, match="already exists"):
            await create_initial_admin(
                ExistingAdminDB(),
                full_name="Admin",
                email="admin@example.com",
                password="longenoughpassword123"
            )

    asyncio.run(check())


def test_create_initial_admin_fails_if_no_organization_exists():
    class NoOrgDB:
        async def scalar(self, statement):
            return None

    async def check():
        with pytest.raises(ValueError, match="set up an organization"):
            await create_initial_admin(
                NoOrgDB(),
                full_name="Admin",
                email="admin@example.com",
                password="longenoughpassword123"
            )

    asyncio.run(check())


def test_create_initial_admin_creates_owner_member_and_hashes_password():
    saved_entities = []
    test_org = Organization(name="Acme Inc", country="DK", currency="DKK")
    test_org.id = uuid4()

    class MockDB:
        async def scalar(self, statement):
            # First query checks if user exists -> return None
            # Second query looks up organization -> return test_org
            # Third query checks email -> return None
            if "users" in str(statement).lower() and "where" not in str(statement).lower():
                return None
            if "organizations" in str(statement).lower():
                return test_org
            if "users" in str(statement).lower() and "where" in str(statement).lower():
                return None
            return None

        def add(self, entity):
            saved_entities.append(entity)

        async def flush(self):
            pass

        async def commit(self):
            pass

        async def refresh(self, entity):
            pass

    async def check():
        user, org = await create_initial_admin(
            MockDB(),
            full_name="Alice Owner",
            email="Alice@Example.Com",
            password="verysecretpassphrase123",
        )
        assert user.email == "alice@example.com"
        assert user.full_name == "Alice Owner"
        assert verify_password("verysecretpassphrase123", user.password_hash)
        assert org == test_org

        # Check that OrganizationMember was created with owner role
        roles = [getattr(e, "role", None) for e in saved_entities]
        assert MemberRole.owner in roles

    asyncio.run(check())
