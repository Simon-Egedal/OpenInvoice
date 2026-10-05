"""Seed a dedicated browser-test database; refuse ordinary application databases."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from sqlalchemy.engine import make_url
from app.auth import hash_password
from app.core.config import settings
from app.core.runtime_config import save_settings
from app.db.session import SessionLocal
from app.models.entities import User, Organization, OrganizationMember, Customer


async def seed():
    if not make_url(settings.database_url).database.endswith("_e2e"):
        raise RuntimeError("Browser fixtures require a database name ending in _e2e")
    async with SessionLocal() as db:
        if not await db.scalar(select(User.id).where(User.email == "browser@example.com")):
            user = User(email="browser@example.com", full_name="Browser owner", password_hash=hash_password("Browser test password 123"))
            org = Organization(name="Browser organization", country="DK", currency="DKK", address="Test Street", vat_number="DK12345678", payment_information="Bank 1234", payment_terms="Net 14 days")
            db.add_all([user, org]); await db.flush()
            db.add(OrganizationMember(user_id=user.id, organization_id=org.id, role="owner"))
            db.add(Customer(organization_id=org.id, name="Browser customer", country="DK", email="customer@example.com"))
            await db.commit()
    save_settings({"setup_completed": True})


if __name__ == "__main__":
    asyncio.run(seed())
