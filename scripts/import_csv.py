import asyncio
import sys
import os
import csv

# Ensure project root is in path
sys.path.append(os.getcwd())

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import AsyncSessionLocal
from app.models import Composer, Work

async def import_csv_data():
    csv_path = "data/sample_works.csv"
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    print(f"Importing works from {csv_path}...")
    
    async with AsyncSessionLocal() as db:
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                composer_name = row.get("composer_name").strip()
                work_title = row.get("work_title").strip()
                nickname = row.get("nickname", "").strip()
                
                if not composer_name or not work_title:
                    continue

                # 1. Find Composer
                result = await db.execute(select(Composer).filter(Composer.name == composer_name))
                composer = result.scalar_one_or_none()
                
                if not composer:
                    print(f"Composer not found: {composer_name}. Creating...")
                    composer = Composer(name=composer_name, is_verified=True)
                    db.add(composer)
                    await db.flush() # flush to get ID
                
                # 2. Check/Create Work
                # We check by title + composer_id for duplicate prevention
                result = await db.execute(
                    select(Work).filter(
                        Work.title == work_title, 
                        Work.composer_id == composer.id
                    )
                )
                work = result.scalar_one_or_none()
                
                if not work:
                    work = Work(
                        title=work_title,
                        nickname=nickname,
                        composer_id=composer.id,
                        is_verified=True
                    )
                    db.add(work)
                    print(f"Added Work: {work_title} ({composer_name})")
                else:
                    print(f"Skipped Work (exists): {work_title}")

        await db.commit()
    print("Import complete.")

if __name__ == "__main__":
    asyncio.run(import_csv_data())
