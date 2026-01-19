import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_search_works_endpoint():
    mock_results = [{"title": "Moonlight Sonata", "id": "123"}]
    
    with patch("app.services.openopus.search_work", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_results
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/works/search?q=Moonlight&composer_id=145")
            
        assert response.status_code == 200
        assert response.json() == mock_results
        mock_search.assert_called_once_with("Moonlight", composer_id="145")

@pytest.mark.asyncio
async def test_search_works_missing_composer_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/works/search?q=Moonlight")
        
    assert response.status_code == 422 # Missing required param
