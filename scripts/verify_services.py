import asyncio
import sys
import os
import httpx

# Ensure project root is in path
sys.path.append(os.getcwd())

from app.services.wikidata import search_composer, get_composer_by_id
from app.services.openopus import get_popular_composers, search_work

async def main():
    print("--- Testing Wikidata ---")
    try:
        composers = await search_composer("Beethoven")
        print(f"Found {len(composers)} composers matching 'Beethoven'")
        if composers:
            first = composers[0]
            print(f"First result: {first}")
            if first.get('wikidata_id'):
                try:
                    details = await get_composer_by_id(first['wikidata_id'])
                    print(f"Details for {first['wikidata_id']}: Name={details.get('name')}")
                except Exception as e:
                    print(f"Get details failed: {e}")
    except Exception as e:
        print(f"Wikidata search failed: {e}")

    print("\n--- Testing OpenOpus ---")
    try:
        popular = await get_popular_composers()
        print(f"Found {len(popular)} popular composers")
        if popular:
            print(f"First popular: {popular[0]}")
    except Exception as e:
        print(f"Popular composers failed: {e}")

    try:
        print("Searching for 'Brandenburg' by Bach (87)...")
        works = await search_work("Brandenburg", composer_id="87")
        print(f"Found {len(works)} works matching 'Brandenburg'")
        if works:
            # Check structure (keys)
            print(f"First work: {works[0]}")
    except Exception as e:
        print(f"Search work failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
