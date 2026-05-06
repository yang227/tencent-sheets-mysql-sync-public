"""
Comprehensive tests for TencentAPI.
Tests all API methods, error handling, and edge cases.
"""
import os
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.services.tencent_api import (
    TencentAPI, TencentAPIError, TokenExpiredError,
    DocumentNotFoundError, PermissionDeniedError, DocumentTypeMismatchError
)


# ─── Fixtures ─────────────────────────────────────────────

@pytest.fixture
def api():
    """Create a TencentAPI instance with test credentials."""
    return TencentAPI(
        app_id="test_app_id",
        app_secret="test_app_secret",
        retry_times=2,
    )


@pytest.fixture
def api_with_token():
    """Create a TencentAPI instance with access token."""
    return TencentAPI(
        access_token="test_token_123",
        app_id="test_app_id",
    )


@pytest.fixture
def mock_client():
    """Create a mock httpx AsyncClient."""
    client = AsyncMock()
    client.is_closed = False
    client.close = AsyncMock()
    return client


@pytest.fixture(autouse=True)
def clean_env():
    """Clean up environment variables before each test."""
    # Remove env var if present
    if "TENCENT_DOCS_ACCESS_TOKEN" in os.environ:
        del os.environ["TENCENT_DOCS_ACCESS_TOKEN"]
    yield
    if "TENCENT_DOCS_ACCESS_TOKEN" in os.environ:
        del os.environ["TENCENT_DOCS_ACCESS_TOKEN"]


# ─── Initialization Tests ─────────────────────────────────────

class TestTencentAPIInit:
    def test_init_with_credentials(self):
        """Test initialization with credentials."""
        api = TencentAPI(
            app_id="my_app",
            app_secret="my_secret",
            access_token="my_token",
            refresh_token="my_refresh",
            open_id="my_open_id",
            retry_times=5,
        )
        
        assert api.app_id == "my_app"
        assert api.app_secret == "my_secret"
        assert api.access_token == "my_token"
        assert api.refresh_token == "my_refresh"
        assert api.open_id == "my_open_id"
        assert api.retry_times == 5

    def test_init_from_env_var(self):
        """Test initialization with env var token."""
        os.environ["TENCENT_DOCS_ACCESS_TOKEN"] = "env_token_123"
        
        api = TencentAPI()
        
        assert api.access_token == "env_token_123"

    def test_init_default_retry_times(self):
        """Test default retry times."""
        api = TencentAPI()
        assert api.retry_times == 3


# ─── from_env Factory Tests ─────────────────────────────────

class TestFromEnv:
    def test_from_env_with_token(self):
        """Test from_env with env var token."""
        os.environ["TENCENT_DOCS_ACCESS_TOKEN"] = "env_token"
        
        api = TencentAPI.from_env()
        
        assert api.access_token == "env_token"

    def test_from_env_without_token(self):
        """Test from_env without env var token."""
        if "TENCENT_DOCS_ACCESS_TOKEN" in os.environ:
            del os.environ["TENCENT_DOCS_ACCESS_TOKEN"]
        
        api = TencentAPI.from_env()
        
        # Should create instance with config credentials
        assert api is not None


# ─── Token Management Tests ──────────────────────────────────

class TestTokenManagement:
    def test_is_token_expired_no_token(self, api):
        """Test token expired when no token."""
        api.access_token = None
        assert api._is_token_expired() is True

    def test_is_token_expired_valid_token(self, api):
        """Test token not expired with valid token."""
        api.access_token = "test_token"
        api._token_expires_at = time.time() + 3600  # 1 hour
        
        assert api._is_token_expired() is False

    def test_is_token_expired_token_expiring_soon(self, api):
        """Test token expiring within 60 seconds."""
        api._token_expires_at = time.time() + 30  # 30 seconds
        
        assert api._is_token_expired() is True

    def test_is_token_expired_token_already_expired(self, api):
        """Test token already expired."""
        api._token_expires_at = time.time() - 100
        
        assert api._is_token_expired() is True

    @pytest.mark.asyncio
    async def test_refresh_access_token_env_token(self, api):
        """Test refresh with env var token (JWT mode)."""
        os.environ["TENCENT_DOCS_ACCESS_TOKEN"] = "jwt_token"
        
        result = await api._refresh_access_token()
        
        assert result == "jwt_token"
        assert api._token_expires_at > time.time()

    @pytest.mark.asyncio
    async def test_refresh_access_token_success(self, api, mock_client):
        """Test successful token refresh."""
        api._ensure_client = AsyncMock(return_value=mock_client)
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={
            "access_token": "new_token",
            "refresh_token": "new_refresh",
            "expires_in": 7200,
        })
        mock_client.post = AsyncMock(return_value=mock_response)
        
        result = await api._refresh_access_token()
        
        assert result == "new_token"
        assert api.access_token == "new_token"
        assert api.refresh_token == "new_refresh"

    @pytest.mark.asyncio
    async def test_refresh_access_token_no_credentials(self, api):
        """Test refresh fails without credentials."""
        api.app_id = None
        api.app_secret = None
        
        with pytest.raises(ValueError) as exc_info:
            await api._refresh_access_token()
        
        assert "app_id and app_secret" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_refresh_access_token_api_error(self, api, mock_client):
        """Test refresh with API error."""
        api._ensure_client = AsyncMock(return_value=mock_client)
        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_client.post = AsyncMock(return_value=mock_response)
        
        with pytest.raises(TencentAPIError) as exc_info:
            await api._refresh_access_token()
        
        assert exc_info.value.code == 401

    @pytest.mark.asyncio
    async def test_refresh_access_token_no_token_in_response(self, api, mock_client):
        """Test refresh with missing access_token in response."""
        api._ensure_client = AsyncMock(return_value=mock_client)
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"expires_in": 7200})
        mock_client.post = AsyncMock(return_value=mock_response)
        
        with pytest.raises(TencentAPIError) as exc_info:
            await api._refresh_access_token()
        
        assert "No access_token" in str(exc_info.value)


# ─── Auth Headers Tests ──────────────────────────────────────

class TestAuthHeaders:
    def test_get_auth_headers_with_token(self, api_with_token):
        """Test auth headers with access token."""
        headers = api_with_token._get_auth_headers()
        
        assert headers["Access-Token"] == "test_token_123"
        assert headers["Client-Id"] == "test_app_id"

    def test_get_auth_headers_with_open_id(self):
        """Test auth headers with open_id."""
        api = TencentAPI(
            access_token="token",
            app_id="app_id",
            open_id="user_open_id",
        )
        
        headers = api._get_auth_headers()
        
        assert headers["Open-Id"] == "user_open_id"

    def test_get_auth_headers_no_token(self, api):
        """Test auth headers without token."""
        api.access_token = None
        
        headers = api._get_auth_headers()
        
        assert "Access-Token" not in headers


# ─── Request Method Tests ────────────────────────────────────

class TestRequestMethod:
    @pytest.mark.asyncio
    async def test_request_success(self, api, mock_client):
        """Test successful API request."""
        api._ensure_client = AsyncMock(return_value=mock_client)
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json = AsyncMock(return_value={"code": 0, "data": {}})
        mock_client.request = AsyncMock(return_value=mock_response)
        
        result = await api._request("GET", "/test")
        
        assert result["code"] == 0

    @pytest.mark.asyncio
    async def test_request_401_retry(self, api, mock_client):
        """Test request with 401 retry and token refresh."""
        api._ensure_client = AsyncMock(return_value=mock_client)
        
        # First call returns 401, second returns 200
        mock_response_401 = AsyncMock()
        mock_response_401.status_code = 401
        mock_response_401.headers = {"content-type": "application/json"}
        mock_response_401.json = AsyncMock(return_value={"code": 401})
        
        mock_response_200 = AsyncMock()
        mock_response_200.status_code = 200
        mock_response_200.headers = {"content-type": "application/json"}
        mock_response_200.json = AsyncMock(return_value={"code": 0})
        
        mock_client.request.side_effect = [mock_response_401, mock_response_200]
        
        with patch.object(api, '_refresh_access_token', new_callable=AsyncMock):
            result = await api._request("GET", "/test")
        
        assert result["code"] == 0

    @pytest.mark.asyncio
    async def test_request_404_doc_type_mismatch(self, api, mock_client):
        """Test request with 404 on sheets API - doc type mismatch."""
        api._ensure_client = AsyncMock(return_value=mock_client)
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json = AsyncMock(return_value={"code": 404, "message": "Not found"})
        mock_client.request = AsyncMock(return_value=mock_response)
        
        with pytest.raises(DocumentTypeMismatchError) as exc_info:
            await api._request("GET", "/open-api/sheets/v3/spreadsheet/abc123")
        
        assert "文档类型不匹配" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_404_document_not_found(self, api, mock_client):
        """Test request with 404 - document not found (non-sheets API)."""
        api._ensure_client = AsyncMock(return_value=mock_client)
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json = AsyncMock(return_value={"code": 404, "message": "Not found"})
        mock_client.request = AsyncMock(return_value=mock_response)
        
        with pytest.raises(DocumentNotFoundError) as exc_info:
            await api._request("GET", "/open-api/doc/v3/abc123")
        
        assert exc_info.value.code == 404

    @pytest.mark.asyncio
    async def test_request_403_permission_denied(self, api, mock_client):
        """Test request with 403 - permission denied."""
        api._ensure_client = AsyncMock(return_value=mock_client)
        mock_response = AsyncMock()
        mock_response.status_code = 403
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json = AsyncMock(return_value={"code": 403, "message": "Forbidden"})
        mock_client.request = AsyncMock(return_value=mock_response)
        
        with pytest.raises(PermissionDeniedError) as exc_info:
            await api._request("GET", "/test")
        
        assert exc_info.value.code == 403

    @pytest.mark.asyncio
    async def test_request_timeout_retry(self, api, mock_client):
        """Test request with timeout and retry."""
        api._ensure_client = AsyncMock(return_value=mock_client)
        mock_client.request.side_effect = httpx.TimeoutException("Request timeout")
        
        with pytest.raises(TencentAPIError) as exc_info:
            await api._request("GET", "/test")
        
        assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_request_http_error_retry(self, api, mock_client):
        """Test request with HTTP error and retry."""
        api._ensure_client = AsyncMock(return_value=mock_client)
        mock_client.request.side_effect = httpx.HTTPError("Connection error")
        
        with pytest.raises(TencentAPIError) as exc_info:
            await api._request("GET", "/test")
        
        assert "HTTP error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_non_json_response(self, api, mock_client):
        """Test request with non-JSON response."""
        api._ensure_client = AsyncMock(return_value=mock_client)
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "Plain text response"
        mock_client.request = AsyncMock(return_value=mock_response)
        
        result = await api._request("GET", "/test")
        
        assert "raw" in result


# ─── API Methods Tests ───────────────────────────────────────

class TestAPIMethods:
    @pytest.mark.asyncio
    async def test_get_spreadsheet_info(self, api):
        """Test get_spreadsheet_info method."""
        with patch.object(api, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"code": 0, "data": {"title": "Test"}}
            
            result = await api.get_spreadsheet_info("sheet123")
            
            mock_request.assert_called_once_with(
                "GET",
                "/open-api/sheets/v3/spreadsheet/sheet123"
            )
            assert result["code"] == 0

    @pytest.mark.asyncio
    async def test_get_sheet_info(self, api):
        """Test get_sheet_info method."""
        with patch.object(api, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"code": 0, "data": {"rowCount": 100}}
            
            result = await api.get_sheet_info("sheet123", "sh_abc")
            
            mock_request.assert_called_once_with(
                "GET",
                "/open-api/sheets/v3/spreadsheet/sheet123/sheets/sh_abc"
            )

    @pytest.mark.asyncio
    async def test_get_values(self, api):
        """Test get_values method."""
        with patch.object(api, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"values": []}
            
            result = await api.get_values("sheet123", "Sheet1!A1:C10")
            
            mock_request.assert_called_once()
            # Check that params include valueRenderOption
            args, kwargs = mock_request.call_args
            assert kwargs.get("params", {}).get("valueRenderOption") == "FormattedValue"

    @pytest.mark.asyncio
    async def test_put_values(self, api):
        """Test put_values method."""
        with patch.object(api, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"code": 0}
            
            await api.put_values("sheet123", "Sheet1!A1:B2", [["a", "b"]])
            
            mock_request.assert_called_once()
            call_kwargs = mock_request.call_args
            assert call_kwargs[1]["json"]["values"] == [["a", "b"]]

    @pytest.mark.asyncio
    async def test_batch_put_values(self, api):
        """Test batch_put_values method."""
        with patch.object(api, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"code": 0}
            
            data = [{"range": "Sheet1!A1", "values": [["a"]]}]
            await api.batch_put_values("sheet123", data)
            
            mock_request.assert_called_once()
            call_kwargs = mock_request.call_args
            assert call_kwargs[1]["json"]["data"] == data

    @pytest.mark.asyncio
    async def test_append_values(self, api):
        """Test append_values method."""
        with patch.object(api, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"code": 0}
            
            await api.append_values("sheet123", "Sheet1", [["new", "row"]])
            
            mock_request.assert_called_once()
            call_kwargs = mock_request.call_args
            assert call_kwargs[1]["json"]["insertDataOption"] == "INSERT_ROWS"

    @pytest.mark.asyncio
    async def test_read_sheet_data(self, api):
        """Test read_sheet_data method."""
        with patch.object(api, 'get_sheet_info', new_callable=AsyncMock) as mock_info, \
             patch.object(api, 'get_values', new_callable=AsyncMock) as mock_values:
            mock_info.return_value = {"rowCount": 100}
            mock_values.return_value = {
                "values": [
                    ["Header1", "Header2"],
                    ["Row1Col1", "Row1Col2"],
                ]
            }
            
            headers, data_rows = await api.read_sheet_data("sheet123", "Sheet1")
            
            assert headers == ["Header1", "Header2"]
            assert len(data_rows) == 1

    @pytest.mark.asyncio
    async def test_read_sheet_data_empty(self, api):
        """Test read_sheet_data with empty sheet."""
        with patch.object(api, 'get_sheet_info', new_callable=AsyncMock) as mock_info, \
             patch.object(api, 'get_values', new_callable=AsyncMock) as mock_values:
            mock_info.return_value = {"rowCount": 0}
            mock_values.return_value = {"values": []}
            
            headers, data_rows = await api.read_sheet_data("sheet123", "Sheet1")
            
            assert headers == []
            assert data_rows == []


# ─── Parse Spreadsheet ID Tests ────────────────────────────

class TestParseSpreadsheetID:
    def test_parse_from_url_with_d(self, api):
        """Test parsing from URL with /d/ pattern."""
        url = "https://docs.qq.com/spreadsheet/d/abc123xyz"
        result = api.parse_spreadsheet_id(url)
        assert result == "abc123xyz"

    def test_parse_from_url_document(self, api):
        """Test parsing from document URL."""
        url = "https://docs.qq.com/document/d/doc123"
        result = api.parse_spreadsheet_id(url)
        assert result == "doc123"

    def test_parse_direct_id(self, api):
        """Test parsing direct spreadsheet ID."""
        result = api.parse_spreadsheet_id("abc123xyz")
        assert result == "abc123xyz"

    def test_parse_url_no_d_pattern(self, api):
        """Test parsing URL without /d/ pattern."""
        url = "https://docs.qq.com/sheet/abc123"
        result = api.parse_spreadsheet_id(url)
        # Falls back to last part
        assert result == "abc123"


# ─── Test Connection Tests ───────────────────────────────────

class TestTestConnection:
    @pytest.mark.asyncio
    async def test_test_connection_success(self, api):
        """Test successful connection test."""
        api.access_token = "valid_token"
        api._token_expires_at = time.time() + 3600
        
        result = await api.test_connection()
        
        assert result["connected"] is True
        assert "token_expires_in" in result

    @pytest.mark.asyncio
    async def test_test_connection_no_token(self, api):
        """Test connection test with no token."""
        api.access_token = None
        
        with patch.object(api, '_refresh_access_token', new_callable=AsyncMock):
            result = await api.test_connection()
            
            assert result["connected"] is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, api):
        """Test connection test failure."""
        with patch.object(api, '_refresh_access_token', new_callable=AsyncMock) as mock_refresh:
            mock_refresh.side_effect = Exception("Connection failed")
            
            result = await api.test_connection()
            
            assert result["connected"] is False
            assert "Connection failed" in result["error"]


# ─── Context Manager Tests ──────────────────────────────────

class TestContextManager:
    @pytest.mark.asyncio
    async def test_context_manager_enter(self, api):
        """Test async context manager enter."""
        with patch.object(api, '_ensure_client', new_callable=AsyncMock):
            result = await api.__aenter__()
            assert result is api

    @pytest.mark.asyncio
    async def test_context_manager_exit(self, api):
        """Test async context manager exit."""
        api._client = AsyncMock()
        api._client.is_closed = False
        
        await api.__aexit__(None, None, None)
        
        assert api._client is None


# ─── Close Method Tests ─────────────────────────────────────

class TestCloseMethod:
    @pytest.mark.asyncio
    async def test_close_with_client(self, api):
        """Test close method with active client."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        api._client = mock_client
        
        await api.close()
        
        mock_client.aclose.assert_called_once()
        assert api._client is None

    @pytest.mark.asyncio
    async def test_close_no_client(self, api):
        """Test close method without client."""
        api._client = None
        
        # Should not raise
        await api.close()

    @pytest.mark.asyncio
    async def test_close_client_already_closed(self, api):
        """Test close when client already closed."""
        mock_client = AsyncMock()
        mock_client.is_closed = True
        api._client = mock_client
        
        await api.close()
        
        mock_client.aclose.assert_not_called()


# ─── Error Classes Tests ────────────────────────────────────

class TestErrorClasses:
    def test_tencent_api_error(self):
        """Test TencentAPIError initialization."""
        error = TencentAPIError(code=500, message="Internal error")
        
        assert error.code == 500
        assert error.message == "Internal error"
        assert "[500] Internal error" in str(error)

    def test_token_expired_error(self):
        """Test TokenExpiredError inheritance."""
        error = TokenExpiredError(code=401, message="Token expired")
        
        assert isinstance(error, TencentAPIError)
        assert isinstance(error, TokenExpiredError)

    def test_document_not_found_error(self):
        """Test DocumentNotFoundError inheritance."""
        error = DocumentNotFoundError(code=404, message="Not found")
        
        assert isinstance(error, TencentAPIError)
        assert isinstance(error, DocumentNotFoundError)

    def test_permission_denied_error(self):
        """Test PermissionDeniedError inheritance."""
        error = PermissionDeniedError(code=403, message="Forbidden")
        
        assert isinstance(error, TencentAPIError)
        assert isinstance(error, PermissionDeniedError)

    def test_document_type_mismatch_error(self):
        """Test DocumentTypeMismatchError inheritance."""
        error = DocumentTypeMismatchError(code=404, message="Wrong type")
        
        assert isinstance(error, TencentAPIError)
        assert isinstance(error, DocumentTypeMismatchError)
