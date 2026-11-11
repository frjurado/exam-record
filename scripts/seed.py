import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.models import Discipline, Region

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INITIAL_REGIONS = [
    {"name": "Andalucía", "slug": "andalucia"},
    {"name": "Comunidad de Madrid", "slug": "comunidad-de-madrid"},
    {"name": "Comunidad Valenciana", "slug": "comunidad-valenciana"},
]

INITIAL_DISCIPLINES = [
    {"name": "Piano", "slug": "piano"},
    {"name": "Guitarra", "slug": "guitarra"},
    {"name": "Violín", "slug": "violin"},
    {"name": "Viola", "slug": "viola"},
    {"name": "Violonchelo", "slug": "violonchelo"},
    {"name": "Flauta", "slug": "flauta"},
    {"name": "Oboe", "slug": "oboe"},
    {"name": "Clarinete", "slug": "clarinete"},
    {"name": "Contrabajo", "slug": "contrabajo"},
    {"name": "Fagot", "slug": "fagot"},
    {"name": "Saxofón", "slug": "saxofon"},
    {"name": "Trompa", "slug": "trompa"},
    {"name": "Trompeta", "slug": "trompeta"},
    {"name": "Trombón", "slug": "trombon"},
    {"name": "Tuba", "slug": "tuba"},
    {"name": "Percusión", "slug": "percusion"},
    {"name": "Canto", "slug": "canto"},
]


async def seed():
    async with AsyncSessionLocal() as session:
        logger.info("Seeding Regions...")
        for region_data in INITIAL_REGIONS:
            stmt = select(Region).filter_by(slug=region_data["slug"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if not existing:
                logger.info(f"Adding Region: {region_data['name']}")
                session.add(Region(**region_data))
            else:
                logger.info(f"Region exists: {region_data['name']}")

        logger.info("Seeding Disciplines...")
        for discipline_data in INITIAL_DISCIPLINES:
            stmt = select(Discipline).filter_by(slug=discipline_data["slug"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if not existing:
                logger.info(f"Adding Discipline: {discipline_data['name']}")
                session.add(Discipline(**discipline_data))
            else:
                logger.info(f"Discipline exists: {discipline_data['name']}")

        await session.commit()

    logger.info("Seeding Complete.")


async def main() -> None:
    try:
        await seed()
    finally:
        # Dispose the engine so the aiosqlite connection/background thread is
        # closed cleanly and cannot linger and stall interpreter shutdown.
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
