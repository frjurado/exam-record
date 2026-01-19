import pytest
from unittest.mock import AsyncMock, patch, mock_open, Mock
from scripts.import_csv import import_csv_data
from app.models import Composer

@pytest.mark.asyncio
async def test_import_csv():
    # Mock CSV content
    csv_content = "composer_name,work_title\nTest Composer,Test Work\n"
    
    with patch("builtins.open", mock_open(read_data=csv_content)), \
         patch("scripts.import_csv.AsyncSessionLocal") as mock_session_factory:
        
        mock_db = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_db
        
        # KEY FIX: scalar_one_or_none must be a Mock, not AsyncMock (which is default child of AsyncMock)
        # Because in the code we call it synchronously: result.scalar_one_or_none()
        mock_result = Mock()
        mock_result.scalar_one_or_none.side_effect = [None, None]
        
        mock_db.execute.return_value = mock_result
        
        await import_csv_data()
        
        # Verify db.add called for composer and work
        assert mock_db.add.call_count == 2
