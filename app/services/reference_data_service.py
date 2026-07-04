from dataclasses import dataclass

from cachetools import TTLCache
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.constants import Cache
from app.models import Discipline, Region


@dataclass(frozen=True)
class RegionRef:
    id: int
    slug: str
    name: str


@dataclass(frozen=True)
class DisciplineRef:
    id: int
    slug: str
    name: str


class ReferenceDataService:
    """Cached slug lookups for Region/Discipline — static reference data re-read on every
    exam/discipline page view. Caches plain dataclasses rather than ORM instances so a
    cached entry can never end up bound to a closed session or trigger a lazy load.
    """

    _region_cache: TTLCache[str, RegionRef] = TTLCache(
        maxsize=Cache.REFERENCE_DATA_MAX_ENTRIES, ttl=Cache.REFERENCE_DATA_TTL_SECONDS
    )
    _discipline_cache: TTLCache[str, DisciplineRef] = TTLCache(
        maxsize=Cache.REFERENCE_DATA_MAX_ENTRIES, ttl=Cache.REFERENCE_DATA_TTL_SECONDS
    )

    @staticmethod
    async def get_region_by_slug(db: AsyncSession, slug: str) -> RegionRef | None:
        cached = ReferenceDataService._region_cache.get(slug)
        if cached is not None:
            return cached

        result = await db.execute(select(Region).filter(Region.slug == slug))
        region = result.scalar_one_or_none()
        if region is None:
            return None

        ref = RegionRef(id=region.id, slug=region.slug, name=region.name)
        ReferenceDataService._region_cache[slug] = ref
        return ref

    @staticmethod
    async def get_discipline_by_slug(db: AsyncSession, slug: str) -> DisciplineRef | None:
        cached = ReferenceDataService._discipline_cache.get(slug)
        if cached is not None:
            return cached

        result = await db.execute(select(Discipline).filter(Discipline.slug == slug))
        discipline = result.scalar_one_or_none()
        if discipline is None:
            return None

        ref = DisciplineRef(id=discipline.id, slug=discipline.slug, name=discipline.name)
        ReferenceDataService._discipline_cache[slug] = ref
        return ref

    @staticmethod
    def reset_cache() -> None:
        """Clear cached entries. Used by tests to avoid state leaking across test data."""
        ReferenceDataService._region_cache.clear()
        ReferenceDataService._discipline_cache.clear()
