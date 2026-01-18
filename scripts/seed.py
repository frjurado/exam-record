import asyncio
import logging
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models import Region, Discipline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INITIAL_REGIONS = [
    {"name": "Andalucía", "slug": "andalucia"},
    {"name": "Comunidad de Madrid", "slug": "comunidad-de-madrid"},
    {"name": "Comunidad Valenciana", "slug": "comunidad-valenciana"},
]

INITIAL_DISCIPLINES = [
    {"name": "Piano", "slug": "piano"},
    {"name": "Violín", "slug": "violin"},
    {"name": "Clarinete", "slug": "clarinete"},
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

if __name__ == "__main__":
    asyncio.run(seed())
