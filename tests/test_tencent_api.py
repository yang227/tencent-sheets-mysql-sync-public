import pytest
from unittest.mock import AsyncMock, patch
from app.services.tencent_api import TencentAPI, TencentAPIError, TokenExpiredError


def test_tencent_api_init():
    """Test TencentAPI initialization."""
    api = TencentAPI(app_id="test_id", app_secret="test_secret")
    
    assert api.app_id == "test_id"
    assert api.app_secret == "test_secret"
    assert api.retry_times == 3


def test_tencent_api_init_with_access_token():
    """Test TencentAPI with access token."""
    api = TencentAPI(access_token="test_token")
    
    assert api.access_token == "test_token"


def test_is_token_expired_no_token():
    """Test token expiration check when no token."""
    api = TencentAPI()
    
    assert api._is_token_expired() is True


def test_is_token_expired_with_token():
    """Test token expiration check with valid token."""
    import time
    api = TencentAPI(access_token="test_token")
    api._token_expires_at = time.time() + 3600  # 1 hour from now
    
    assert api._is_token_expired() is False


def test_is_token_expired_with_expired_token():
    """Test token expiration check with expired token."""
    import time
    api = TencentAPI(access_token="test_token")
    api._token_expires_at = time.time() - 60  # 1 minute ago
    
    assert api._is_token_expired() is True


def test_parse_spreadsheet_id_from_url():
    """Test extracting spreadsheet ID from URL."""
    api = TencentAPI()
    
    # Test various URL formats
    url1 = "https://docs.qq.com/spreadsheet/d/abc123xyz"
    assert api.parse_spreadsheet_id(url1) == "abc123xyz"
    
    url2 = "https://docs.qq.com/document/d/abc123xyz"
    assert api.parse_spreadsheet_id(url2) == "abc123xyz"


def test_parse_spreadsheet_id_direct():
    """Test parsing spreadsheet ID when already an ID."""
    api = TencentAPI()
    
    spreadsheet_id = "abc123xyz"
    assert api.parse_spreadsheet_id(spreadsheet_id) == "abc123xyz"


@pytest.mark.asyncio
async def test_refresh_access_token_success():
    """Test successful token refresh."""
    api = TencentAPI(app_id="test_id", app_secret="test_secret")
    
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = AsyncMock(return_value={
        "access_token": "new_token",
        "refresh_token": "new_refresh",
        "expires_in": 7200
    })
    
    with patch.object(api, '_ensure_client', new_callable=AsyncMock) as mock_client:
        mock_client.return_value.post = AsyncMock(return_value=mock_response)
        
        token = await api._refresh_access_token()
        
        assert token == "new_token"
        assert api.access_token == "new_token"
        assert api.refresh_token == "new_refresh"


@pytest.mark.asyncio
async def test_refresh_access_token_failure():
    """Test token refresh failure."""
    api = TencentAPI(app_id="test_id", app_secret="test_secret")
    
    mock_response = AsyncMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    
    with patch.object(api, '_ensure_client', new_callable=AsyncMock) as mock_client:
        mock_client.return_value.post = AsyncMock(return_value=mock_response)
        
        with pytest.raises(TencentAPIError):
            await api._refresh_access_token()


def test_tencent_api_error_init():
    """Test TencentAPIError initialization."""
    error = TencentAPIError(code=401, message="Unauthorized access")
    
    assert error.code == 401
    assert error.message == "Unauthorized access"
    assert "[401] Unauthorized access" in str(error)


def test_token_expired_error():
    """Test TokenExpiredError inheritance."""
    error = TokenExpiredError(code=401, message="Token expired")
    
    assert isinstance(error, TencentAPIError)
    assert error.code == 401


@pytest.mark.asyncio
async def test_close_client():
    """Test closing the HTTP client."""
    api = TencentAPI()
    api._client = AsyncMock()
    api._client.is_closed = False
    
    await api.close()
    
    assert api._client is None


@pytest.mark.asyncio
async def test_ensure_client():
    """Test ensuring HTTP client is created."""
    api = TencentAPI()
    
    client = await api._ensure_client()
    
    assert client is not None
    assert api._client is not None


def test_get_auth_headers():
    """Test getting authorization headers."""
    api = TencentAPI(
        app_id="test_id",
        open_id="test_open_id",
        access_token="test_token"
    )
    
    headers = api._get_auth_headers()
    
    assert headers["Access-Token"] == "test_token"
    assert headers["Client-Id"] == "test_id"
    assert headers["Open-Id"] == "test_open_id"
