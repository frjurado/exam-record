from limits import parse
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core import security


def client_address(request: Request) -> str:
    """The visitor's IP. Behind Fly's proxy the socket peer is the proxy itself, so every
    visitor would share one rate-limit bucket; Fly passes the real address in
    Fly-Client-IP (set by the proxy, not forwardable by clients)."""
    return request.headers.get("Fly-Client-IP") or get_remote_address(request)


def user_or_address(request: Request) -> str:
    """The signed-in user when there is one, otherwise the IP. A classroom shares one
    address, so per-IP limits on voting would let only the first few pupils through."""
    token = request.cookies.get("access_token")
    payload = security.verify_token(token, security.SESSION) if token else None
    if payload:
        return f"user:{payload['sub']}"
    return client_address(request)


limiter = Limiter(key_func=client_address)


def allow(limit: str, scope: str, key: str) -> bool:
    """Count one hit against a limit that cannot be expressed as a decorator (the key
    comes from the request body). False when the limit is already used up."""
    return bool(limiter.limiter.hit(parse(limit), scope, key))
