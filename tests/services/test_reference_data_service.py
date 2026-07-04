from app.models import Discipline, Region
from app.services.reference_data_service import ReferenceDataService


async def test_get_region_by_slug_returns_none_when_missing(db):
    assert await ReferenceDataService.get_region_by_slug(db, "no-such-region") is None


async def test_get_discipline_by_slug_returns_none_when_missing(db):
    assert await ReferenceDataService.get_discipline_by_slug(db, "no-such-discipline") is None


async def test_get_region_by_slug_caches_across_row_deletion(db):
    region = Region(name="Cache Region", slug="cache-region")
    db.add(region)
    await db.commit()
    await db.refresh(region)

    first = await ReferenceDataService.get_region_by_slug(db, "cache-region")
    assert first is not None
    assert first.id == region.id

    # Delete the row directly; a fresh DB lookup would now return None.
    await db.delete(region)
    await db.commit()

    cached = await ReferenceDataService.get_region_by_slug(db, "cache-region")
    assert cached is not None
    assert cached.id == first.id


async def test_get_discipline_by_slug_caches_across_row_deletion(db):
    discipline = Discipline(name="Cache Discipline", slug="cache-discipline")
    db.add(discipline)
    await db.commit()
    await db.refresh(discipline)

    first = await ReferenceDataService.get_discipline_by_slug(db, "cache-discipline")
    assert first is not None
    assert first.id == discipline.id

    await db.delete(discipline)
    await db.commit()

    cached = await ReferenceDataService.get_discipline_by_slug(db, "cache-discipline")
    assert cached is not None
    assert cached.id == first.id
