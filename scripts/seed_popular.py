import asyncio
import sys
import os

# Ensure project root is in path
sys.path.append(os.getcwd())

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import AsyncSessionLocal
from app.models import Composer
from app.services.openopus import get_popular_composers

async def seed_popular_composers():
    print("Fetching popular composers from OpenOpus...")
    try:
        popular_composers = await get_popular_composers()
    except Exception as e:
        print(f"Error fetching from OpenOpus: {e}")
        return

    print(f"Found {len(popular_composers)} composers. Inserting into DB...")
    
    async with AsyncSessionLocal() as db:
        for item in popular_composers:
            # Check if exists
            # item keys: name, id, complete_name, birth, death, epoch, portrait
            # Our model: name, wikidata_id, is_verified.
            # We don't have OpenOpus ID in Composer model yet? 
            # Let's check models.py first.
            
            # Wait, I should check models.py to map fields correctly.
            # Assuming 'name' is the key for now.
            name = item.get("complete_name", item.get("name"))
            
            # Check existence by name (simple check for now)
            result = await db.execute(select(Composer).filter(Composer.name == name))
            existing = result.scalar_one_or_none()
            
            if not existing:
                new_composer = Composer(
                    name=name,
                    is_verified=True
                    # We don't have openopus_id on Composer in the spec? 
                    # Spec says: Composers { id, name, wikidata_id, is_verified }
                    # We can leave wikidata_id null for now or try to fetch it later if needed.
                )
                db.add(new_composer)
                print(f"Added: {name}")
            else:
                pass # print(f"Skipped (exists): {name}")
        
        await db.commit()
    print("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed_popular_composers())
