import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_search_composers_endpoint(client):
    mock_results = [{"name": "Beethoven", "wikidata_id": "Q255"}]
    
    with patch("app.services.wikidata.search_composer", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_results
        
        # We must request source=wikidata now to trigger external search
        response = await client.get("/api/composers/search?q=Beethoven&source=wikidata")
            
        assert response.status_code == 200
        assert response.json() == mock_results
        mock_search.assert_called_once_with("Beethoven")

@pytest.mark.asyncio
async def test_search_composers_missing_param_endpoint(client):
    response = await client.get("/api/composers/search")
    assert response.status_code == 422 # My validation error

@pytest.mark.asyncio
async def test_search_composers_short_query(client):
    response = await client.get("/api/composers/search?q=a")
    assert response.status_code == 422 # Min length 2
