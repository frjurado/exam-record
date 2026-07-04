from unittest.mock import AsyncMock, patch

import pytest

from app.core.constants import RateLimit


def _limit_count(limit_string: str) -> int:
    return int(limit_string.split("/")[0])


@pytest.mark.asyncio
async def test_magic_link_rate_limit_returns_429_after_threshold(client):
    limit = _limit_count(RateLimit.MAGIC_LINK_REQUEST)

    with patch("app.services.email.email_service.send_magic_link", new_callable=AsyncMock):
        for _ in range(limit):
            response = await client.post(
                "/api/auth/magic-link", json={"email": "rate-limit@test.com"}
            )
            assert response.status_code == 200

        response = await client.post("/api/auth/magic-link", json={"email": "rate-limit@test.com"})

    assert response.status_code == 429
