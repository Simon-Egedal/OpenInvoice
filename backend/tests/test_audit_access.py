import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.router import audit, router
from app.auth import admin_membership


@pytest.mark.parametrize("role", ["member", "accountant", "viewer", "admin", "owner"])
def test_audit_access_requires_admin_and_scopes_events_to_organization(role):
    organization_id = uuid4()
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [])
    )))
    route = next(route for route in router.routes if route.path == "/audit")
    assert admin_membership in [dependency.call for dependency in route.dependant.dependencies]
    membership = SimpleNamespace(role=role, organization_id=organization_id)

    async def read_activity():
        authorized = await admin_membership(membership)
        return await audit(authorized, db)

    if role in {"admin", "owner"}:
        assert asyncio.run(read_activity()) == []
        db.execute.assert_awaited_once()
        statement = db.execute.call_args.args[0]
        sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
        assert "audit_logs.organization_id" in sql
        assert organization_id.hex in sql.replace("-", "")
    else:
        with pytest.raises(HTTPException) as error:
            asyncio.run(read_activity())
        assert error.value.status_code == 403
        db.execute.assert_not_awaited()
