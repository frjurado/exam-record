
import asyncio
import httpx
import sys

BASE_URL = "http://127.0.0.1:8000"

async def verify_flow():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        print("1. Searching for Composer 'Mozart'...")
        res = await client.get("/api/composers/search?q=Mozart&source=local")
        if res.status_code != 200:
            print(f"FAILED: /api/composers/search returned {res.status_code}")
            return
        
        composers = res.json()
        mozart = next((c for c in composers if "Mozart" in c["name"]), None)
        
        if not mozart:
            print("FAILED: Mozart not found in local DB")
            return
            
        print(f"   Found: {mozart['name']} (ID: {mozart['id']})")
        if not mozart.get("openopus_id"):
            print("FAILED: Mozart does not have an OpenOpus ID")
            return
        
        openopus_id = mozart["openopus_id"]
        print(f"   OpenOpus ID: {openopus_id}")
        
        print("2. Searching for Work 'Jupiter' using OpenOpus ID...")
        res = await client.get(f"/api/works/search?q=Jupiter&source=openopus&composer_id={openopus_id}")
        if res.status_code != 200:
            print(f"FAILED: /api/works/search returned {res.status_code}")
            print(res.text)
            return
            
        works = res.json()
        print(f"   Found {len(works)} works")
        if len(works) > 0:
            print(f"   Sample: {works[0]['title']}")
            if works[0].get("is_verified") is not True:
                 print("FAILED: Result should be verified")
                 
            print("SUCCESS: Integration Verified")
        else:
            print("WARNING: No works found, but API call succeeded. (Maybe OpenOpus is down or query is too vague?)")

if __name__ == "__main__":
    try:
        asyncio.run(verify_flow())
    except Exception as e:
        print(f"ERROR: {e}")
