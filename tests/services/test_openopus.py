import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services import openopus

@pytest.mark.asyncio
async def test_get_popular_composers():
    mock_response_data = {
        "status": "success",
        "composers": [
            {"name": "Bach", "id": "87"},
            {"name": "Mozart", "id": "140"}
        ]
    }
    
    with patch("app.services.openopus.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = lambda: None
        
        mock_client.get.return_value = mock_response
        
        results = await openopus.get_popular_composers()
        
        assert len(results) == 2
        assert results[0]["name"] == "Bach"

@pytest.mark.asyncio
async def test_search_work():
    # Mocking the response for "list all works"
    mock_response_data = {
        "status": "success",
        "works": [
            {"title": "Moonlight Sonata", "id": "123", "nickname": "Moonlight"},
            {"title": "Symphony No. 5", "id": "124", "nickname": ""},
        ]
    }
    
    with patch("app.services.openopus.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = lambda: None
        
        mock_client.get.return_value = mock_response
        
        # We must provide a composer_id now
        results = await openopus.search_work("Moonlight", composer_id="145")
        
        assert len(results) == 1
        assert results[0]["title"] == "Moonlight Sonata"
        
        # Verify it filters correctly
        results_empty = await openopus.search_work("NonExistent", composer_id="145")
        assert len(results_empty) == 0
