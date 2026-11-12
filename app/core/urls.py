from urllib.parse import urlsplit

from starlette.requests import Request

from app.core.config import settings


def public_base_url(request: Request) -> str:
    """Base URL as seen by visitors. Fly terminates TLS and forwards plain HTTP, so the
    request's own scheme is http in production even though the site is https-only."""
    base_url = str(request.base_url).rstrip("/")
    if settings.ENVIRONMENT == "production" and base_url.startswith("http://"):
        base_url = "https://" + base_url.removeprefix("http://")
    return base_url


def canonical_redirect(request: Request) -> str | None:
    """Where to send a request that arrived at one of the site's other addresses (the
    www form, or Fly's own *.fly.dev name), or None when it is already in the right place.
    Only those two kinds of host are redirected, so health checks and internal calls
    addressed by IP or private name are left alone."""
    canonical = settings.CANONICAL_HOST
    host = (request.headers.get("host") or "").split(":")[0].lower()
    if not canonical or host == canonical:
        return None
    if host != f"www.{canonical}" and not host.endswith(".fly.dev"):
        return None
    target = f"https://{canonical}{request.url.path}"
    if request.url.query:
        target += "?" + request.url.query
    return target


def safe_next_path(target: str | None, request: Request) -> str:
    """Where to send the visitor after sign-in: always a path on this site.

    The browser sends the full address of the page it was on, so an absolute URL is
    accepted when its host is ours and reduced to its path. Anything else (another host,
    `//host`, backslash tricks, other schemes) falls back to the home page.
    """
    if not target:
        return "/"
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        if parts.scheme not in ("http", "https") or parts.netloc != request.url.netloc:
            return "/"
    path = parts.path or "/"
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/"
    if parts.query:
        path += "?" + parts.query
    return path
