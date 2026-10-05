"""Run with python -m app.worker; PostgreSQL coordinates concurrent workers."""
import asyncio
import logging
from app.db.session import SessionLocal
from app.deliveries import process_one


async def run():
    while True:
        try:
            worked = await process_one(SessionLocal)
        except Exception:
            logging.getLogger(__name__).exception("Outbox worker iteration failed")
            worked = False
        if not worked:
            await asyncio.sleep(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
