"""Unit tests for WorkService — no DB required."""

from types import SimpleNamespace

from app.services.work_service import WorkService


def _make_work(title: str, imslp_url: str | None, composer_name: str | None) -> SimpleNamespace:
    composer = SimpleNamespace(name=composer_name) if composer_name is not None else None
    return SimpleNamespace(title=title, imslp_url=imslp_url, composer=composer)


def test_get_score_url_returns_imslp_url_when_set():
    work = _make_work("Prelude", "https://imslp.org/wiki/Prelude_(Bach)", "Bach")
    assert WorkService.get_score_url(work) == "https://imslp.org/wiki/Prelude_(Bach)"


def test_get_score_url_fallback_contains_composer_and_title():
    work = _make_work("Sonata No. 1", None, "Beethoven")
    url = WorkService.get_score_url(work)
    assert "duckduckgo.com" in url
    assert "Beethoven" in url
    assert "Sonata" in url


def test_get_score_url_fallback_no_composer():
    work = _make_work("Unknown Piece", None, None)
    url = WorkService.get_score_url(work)
    assert "duckduckgo.com" in url
    assert "Unknown+Piece" in url or "Unknown%20Piece" in url or "Unknown" in url


def test_get_score_url_fallback_is_valid_url():
    work = _make_work("Nocturne Op.9", None, "Chopin")
    url = WorkService.get_score_url(work)
    assert url.startswith("https://")
