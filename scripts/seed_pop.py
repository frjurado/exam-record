import asyncio
import logging
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models import Composer
from app.services import openopus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_pop():
    async with AsyncSessionLocal() as session:
        logger.info("Fetching Popular Composers from OpenOpus...")
        try:
            pop_composers = await openopus.get_popular_composers()
            logger.info(f"Found {len(pop_composers)} composers.")
            
            for c_data in pop_composers:
                # OpenOpus keys: id, name, complete_name, epoch, etc.
                # We map: name -> name, id -> openopus_id (wait, we don't have openopus_id col on Composer, only wikidata_id)
                # But wait, Composer model has wikidata_id. OpenOpus doesn't give wikidata_id easily in pop list?
                # Actually OpenOpus 'id' is their internal ID.
                # We need to decide how to store OpenOpus composers.
                # The design said: "Wikidata used for Composers".
                # But we are seeding from OpenOpus.
                # Let's see if OpenOpus gives us enough info to be useful.
                # Pop list gives: id, name, complete_name, birth, death, epoch.
                # We can store them as verified. We won't have wikidata_id populated initially unless we search.
                # But for search, we use local DB 'name'.
                
                # Check if exists by name (fuzzy mismatch risk, but acceptable for seeding)
                name = c_data.get("complete_name", c_data.get("name"))
                stmt = select(Composer).filter(Composer.name == name)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if not existing:
                    # We create them. We don't have wikidata_id, leaving it null.
                    # We mark as verified because they come from a trusted source (OpenOpus).
                    composer = Composer(
                        name=name,
                        is_verified=True,
                        # We might want to store OpenOpus ID if we add column, but not strict req now.
                    )
                    session.add(composer)
                    logger.info(f"Added: {name}")
                else:
                    logger.debug(f"Skipping existing: {name}")
            
            await session.commit()
            logger.info("Seeding Popular Composers Complete.")
            
        except Exception as e:
            logger.error(f"Failed to seed: {e}")

if __name__ == "__main__":
    asyncio.run(seed_pop())
