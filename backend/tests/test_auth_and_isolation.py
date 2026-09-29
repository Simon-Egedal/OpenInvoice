import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.router import get_customer
from app.auth import hash_password, verify_password, write_membership

def test_password_hash_is_verified_without_storing_plaintext():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)

def test_customer_lookup_returns_not_found_for_another_organization():
    org_id = uuid4()
    statement_seen = []
    class EmptyDatabase:
        async def scalar(self, statement):
            statement_seen.append(str(statement.compile(compile_kwargs={"literal_binds": True})))
            return None
    async def check():
        with pytest.raises(HTTPException) as error:
            await get_customer(uuid4(), SimpleNamespace(organization_id=org_id), EmptyDatabase())
        assert error.value.status_code == 404
    asyncio.run(check())
    assert "customers.organization_id" in statement_seen[0]

def test_viewer_role_cannot_write():
    async def check():
        with pytest.raises(HTTPException) as error:
            await write_membership(SimpleNamespace(role="viewer"))
        assert error.value.status_code == 403
    asyncio.run(check())
