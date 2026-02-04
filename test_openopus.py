
import asyncio
import httpx

OPENOPUS_API_URL = "https://api.openopus.org"

async def test_openopus():
    print("Fetching popular composers...")
    url = f"{OPENOPUS_API_URL}/composer/list/pop.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            composers = data.get("composers", [])
            print(f"Found {len(composers)} composers.")
            if composers:
                print("First composer sample:", composers[0])
        else:
            print("Failed to fetch composers")

async def search_work_test(composer_id):
    print(f"Fetching works for composer {composer_id}...")
    url = f"{OPENOPUS_API_URL}/work/list/composer/{composer_id}/genre/all.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            works = data.get("works", [])
            print(f"Found {len(works)} works.")
            if works:
                print("First work sample:", works[0])
        else:
            print(f"Failed to fetch works for {composer_id}: {response.status_code}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_openopus())
    # Try searching for Beethoven (usually ID 87 or similar, let's see from output)
    # loop.run_until_complete(search_work_test(87))
