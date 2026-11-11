from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def client_address(request: Request) -> str:
    """The visitor's IP. Behind Fly's proxy the socket peer is the proxy itself, so every
    visitor would share one rate-limit bucket; Fly passes the real address in
    Fly-Client-IP (set by the proxy, not forwardable by clients)."""
    return request.headers.get("Fly-Client-IP") or get_remote_address(request)


limiter = Limiter(key_func=client_address)
