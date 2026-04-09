import urllib.parse

from app.models import Work


class WorkService:
    @staticmethod
    def get_score_url(work: Work) -> str:
        """Return the best available score URL for a work.

        Prefers the stored IMSLP URL; falls back to a DuckDuckGo
        "I'm Feeling Lucky" search scoped to imslp.org.
        """
        if work.imslp_url:
            return work.imslp_url  # type: ignore[return-value]

        composer_name = work.composer.name if work.composer else ""
        query_str = f"\\ site:imslp.org {composer_name} {work.title}"
        return f"https://duckduckgo.com/?q={urllib.parse.quote(query_str)}"
