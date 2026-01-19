import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_search_composers_endpoint():
    mock_results = [{"name": "Beethoven", "wikidata_id": "Q255"}]
    
    with patch("app.services.wikidata.search_composer", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_results
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/composers/search?q=Beethoven")
            
        assert response.status_code == 200
        assert response.json() == mock_results
        mock_search.assert_called_once_with("Beethoven")

@pytest.mark.asyncio
async def test_search_composers_missing_param_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/composers/search")
        
    assert response.status_code == 422 # My validation error

@pytest.mark.asyncio
async def test_search_composers_short_query():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/composers/search?q=a")
        
    assert response.status_code == 422 # Min length 2
