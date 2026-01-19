import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services import wikidata

@pytest.mark.asyncio
async def test_search_composer():
    mock_response_data = {
        "search": [
            {
                "id": "Q255",
                "label": "Ludwig van Beethoven",
                "description": "German composer and pianist"
            }
        ]
    }
    
    # Mock the httpx.AsyncClient used in the module
    with patch("app.services.wikidata.httpx.AsyncClient") as mock_client_cls:
        # Create a mock client instance
        mock_client = AsyncMock()
        # Ensure __aenter__ returns this mock client
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        # Mock the get method of the client
        # Response object is synchronous, so use MagicMock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = lambda: None
        
        mock_client.get.return_value = mock_response
        
        results = await wikidata.search_composer("Beethoven")
        
        assert len(results) == 1
        assert results[0]["name"] == "Ludwig van Beethoven"
        assert results[0]["wikidata_id"] == "Q255"
        assert "German composer" in results[0]["description"]

@pytest.mark.asyncio
async def test_get_composer_by_id():
    mock_response_data = {
        "entities": {
            "Q255": {
                "labels": {
                    "en": {"value": "Ludwig van Beethoven"}
                },
                "claims": {}
            }
        }
    }
    
    with patch("app.services.wikidata.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = lambda: None
        
        mock_client.get.return_value = mock_response
        
        result = await wikidata.get_composer_by_id("Q255")
        
        assert result["name"] == "Ludwig van Beethoven"
        assert result["wikidata_id"] == "Q255"
