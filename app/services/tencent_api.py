"""
Tencent Document API Client with automatic token refresh.
API Base: https://docs.tencent.com
"""
import asyncio
import os
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

# Canonical timeout for all httpx operations (seconds)
HTTPX_TIMEOUT = httpx.Timeout(connect=2.0, read=8.0, write=10.0, pool=5.0)

from app.config import get_settings

logger = logging.getLogger(__name__)


class TencentAPIError(Exception):
    """Tencent API error with code and message."""
    
    def __init__(self, code: int, message: str, response_data: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.response_data = response_data or {}
        super().__init__(f"[{code}] {message}")


class TokenExpiredError(TencentAPIError):
    """Token has expired, need to refresh."""
    pass


class DocumentNotFoundError(TencentAPIError):
    """Document does not exist or is not accessible (404)."""
    pass


class PermissionDeniedError(TencentAPIError):
    """No permission to access this document (403)."""
    pass


class DocumentTypeMismatchError(TencentAPIError):
    """Document type mismatch — smartcanvas doc vs xlsx sheet."""
    pass


class TencentAPI:
    """
    Async Tencent Document API client with automatic token management.

    Auth priority (highest → lowest):
    1. TENCENT_DOCS_ACCESS_TOKEN env var — JWT token for smart document API
       (set in .env: TENCENT_DOCS_ACCESS_TOKEN=eyJ...)
       When this is set, OAuth is skipped entirely and all requests go through
       the JWT-based API path. This is the preferred mode when app_secret is empty.
    2. config.yaml app_id + app_secret — OAuth 2.0 client_credentials flow.
       Token is auto-refreshed on 401 responses.

    Features:
    - Canonical httpx timeout: connect=2s, read=8s, write=10s, pool=5s
    - Automatic token refresh on 401 errors
    - Retry logic with configurable retry times
    - Precise error classification: 404→DocumentNotFound/DocumentTypeMismatch,
      403→PermissionDenied, 401→TokenExpired
    """

    BASE_URL = "https://docs.qq.com"
    TOKEN_URL = "https://docs.qq.com/oauth/v2/token"  # 腾讯文档 OAuth2 Token 端点
    AUTHORIZE_URL = "https://docs.qq.com/oauth/v2/authorize"  # 腾讯文档 OAuth2 授权端点

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        open_id: Optional[str] = None,
        retry_times: int = 3,
    ):
        # TENCENT_DOCS_ACCESS_TOKEN env var takes precedence (JWT mode)
        self.access_token = os.environ.get("TENCENT_DOCS_ACCESS_TOKEN", access_token)
        self.settings = get_settings()
        self.app_id = app_id or self.settings.tencent.app_id
        self.app_secret = app_secret or self.settings.tencent.app_secret
        self.open_id = open_id or self.settings.tencent.open_id
        self.refresh_token = refresh_token
        self.retry_times = retry_times

        self._token_expires_at: float = 0
        self._client: Optional[httpx.AsyncClient] = None

    @classmethod
    def from_env(cls) -> "TencentAPI":
        """
        Factory: create a TencentAPI instance preferring the JWT token from env.

        Checks TENCENT_DOCS_ACCESS_TOKEN first; falls back to config credentials.
        Use this when you want env-var JWT to always take priority without
        needing to check manually. Used by SyncEngine.tencent property.
        """
        token = os.environ.get("TENCENT_DOCS_ACCESS_TOKEN")
        if token:
            return cls(access_token=token)
        # Fallback: try OAuth with config credentials
        return cls()

    async def __aenter__(self):
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure we have an active HTTP client with canonical timeout."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=HTTPX_TIMEOUT,
                headers={"Content-Type": "application/json"},
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    def _is_token_expired(self) -> bool:
        """Check if current token is expired or about to expire."""
        if not self.access_token:
            return True
        # Refresh 60 seconds before actual expiry
        return time.time() >= (self._token_expires_at - 60)
    
    async def _refresh_access_token(self) -> str:
        """
        使用 Client Credentials 模式获取 App Access Token（用于发起授权流程）。
        注意：腾讯文档 OAuth2 支持 client_credentials 模式直接获取 app token，
        此 token 可用于调用部分不需要用户授权的 API。
        如需用户数据，需使用 authorization_code 流程。

        如果 TENCENT_DOCS_ACCESS_TOKEN 环境变量已设置，则跳过 OAuth 刷新。
        """
        # JWT token from env takes priority — skip OAuth entirely
        if os.environ.get("TENCENT_DOCS_ACCESS_TOKEN"):
            token = os.environ["TENCENT_DOCS_ACCESS_TOKEN"]
            self.access_token = token
            self._token_expires_at = time.time() + 7200
            logger.info("Using TENCENT_DOCS_ACCESS_TOKEN from environment (JWT mode)")
            return token

        if not self.app_id or not self.app_secret:
            logger.error("Missing app_id or app_secret for token refresh")
            raise ValueError("app_id and app_secret are required to refresh token")

        logger.info("Refreshing Tencent API access token")
        client = await self._ensure_client()

        response = await client.post(
            "/oauth/v2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=HTTPX_TIMEOUT,
        )
        
        if response.status_code != 200:
            logger.error(f"Token refresh failed with status {response.status_code}: {response.text}")
            raise TencentAPIError(
                code=response.status_code,
                message=f"Token refresh failed: {response.text}",
            )
        
        data = await response.json()
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        
        # Set expiry (腾讯文档 access_token 有效期通常为 7200 秒)
        expires_in = data.get("expires_in", 7200)
        self._token_expires_at = time.time() + expires_in
        
        if not self.access_token:
            logger.error("No access_token in refresh response")
            raise TencentAPIError(
                code=-1,
                message="No access_token in refresh response",
                response_data=data,
            )
        
        logger.info("Access token refreshed successfully, expires in %d seconds", expires_in)
        return self.access_token
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers with current token (V3 API)."""
        headers = {}
        if self.access_token:
            headers["Access-Token"] = self.access_token
        if self.app_id:
            headers["Client-Id"] = self.app_id
        if self.open_id:
            headers["Open-Id"] = self.open_id
        return headers
    
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Make an API request with automatic token refresh on 401.
        """
        client = await self._ensure_client()
        
        request_headers = self._get_auth_headers()
        if headers:
            request_headers.update(headers)
        
        try:
            response = await client.request(
                method=method,
                url=path,
                params=params,
                json=json,
                headers=request_headers,
            )
            
            if response.status_code == 401:
                if retry_count < self.retry_times:
                    await self._refresh_access_token()
                    return await self._request(
                        method, path, params, json, headers, retry_count + 1
                    )
                raise TokenExpiredError(401, "Token expired and refresh failed")
            
            if response.headers.get("content-type", "").startswith("application/json"):
                data = await response.json()
            else:
                data = {"raw": response.text}
            
            if response.status_code >= 400:
                error_code = data.get("code", response.status_code)
                error_msg = data.get("message", response.text)
                err_data = dict(data)
                if response.status_code == 404:
                    is_sheets_api = "/sheets/" in path or "/values/" in path
                    if is_sheets_api:
                        err_data["_err_type"] = "doc_type_mismatch"
                        raise DocumentTypeMismatchError(
                            error_code,
                            f"文档类型不匹配：此 ID 为智能文档（doc），不支持在线表格 API。"
                            f" 腾讯文档返回: {error_msg}",
                            err_data,
                        )
                    err_data["_err_type"] = "not_found"
                    raise DocumentNotFoundError(
                        error_code,
                        f"文档不存在或无权访问（404）。spreadsheetId 可能错误或文档已被删除。API返回: {error_msg}",
                        err_data,
                    )
                if response.status_code == 403:
                    err_data["_err_type"] = "access_denied"
                    raise PermissionDeniedError(
                        error_code,
                        f"无权访问该文档（403）。请检查 Access Token 是否对该文档有权限。API返回: {error_msg}",
                        err_data,
                    )
                if response.status_code == 401:
                    err_data["_err_type"] = "auth_failed"
                raise TencentAPIError(error_code, error_msg, err_data)
            
            return data
            
        except httpx.TimeoutException:
            if retry_count < self.retry_times:
                await asyncio.sleep(1 * (retry_count + 1))
                return await self._request(
                    method, path, params, json, headers, retry_count + 1
                )
            raise TencentAPIError(-1, "Request timeout")
        except httpx.HTTPError as e:
            if retry_count < self.retry_times:
                await asyncio.sleep(1 * (retry_count + 1))
                return await self._request(
                    method, path, params, json, headers, retry_count + 1
                )
            raise TencentAPIError(-1, f"HTTP error: {str(e)}")
    
    async def get_spreadsheet_info(self, spreadsheet_id: str) -> Dict[str, Any]:
        """Get spreadsheet metadata."""
        return await self._request(
            "GET",
            f"/open-api/sheets/v3/spreadsheet/{spreadsheet_id}",
        )
    
    async def get_sheet_info(
        self, spreadsheet_id: str, sheet_id: str
    ) -> Dict[str, Any]:
        """Get worksheet info."""
        return await self._request(
            "GET",
            f"/open-api/sheets/v3/spreadsheet/{spreadsheet_id}/sheets/{sheet_id}",
        )
    
    async def get_values(
        self,
        spreadsheet_id: str,
        range_str: str,
        value_render_option: str = "FormattedValue",
    ) -> Dict[str, Any]:
        """Read values from a range."""
        return await self._request(
            "GET",
            f"/open-api/sheets/v3/spreadsheet/{spreadsheet_id}/values/{range_str}",
            params={"valueRenderOption": value_render_option},
        )
    
    async def put_values(
        self,
        spreadsheet_id: str,
        range_str: str,
        values: List[List[Any]],
    ) -> Dict[str, Any]:
        """Write values to a range."""
        return await self._request(
            "PUT",
            f"/open-api/sheets/v3/spreadsheet/{spreadsheet_id}/values/{range_str}",
            json={"values": values},
        )
    
    async def batch_put_values(
        self,
        spreadsheet_id: str,
        data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Batch write values."""
        return await self._request(
            "PUT",
            f"/open-api/sheets/v3/spreadsheet/{spreadsheet_id}/values/batch",
            json={"data": data},
        )
    
    async def append_values(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        values: List[List[Any]],
    ) -> Dict[str, Any]:
        """Append values to a sheet."""
        range_str = f"{sheet_name}!A1"
        return await self._request(
            "POST",
            f"/open-api/sheets/v3/spreadsheet/{spreadsheet_id}/values/{range_str}:append",
            json={
                "values": values,
                "insertDataOption": "INSERT_ROWS",
            },
        )
    
    async def read_sheet_data(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        header_row: int = 1,
        data_start_row: int = 2,
    ) -> Tuple[List[str], List[List[Any]]]:
        """Read sheet data with headers."""
        sheet_info = await self.get_sheet_info(spreadsheet_id, sheet_name)
        last_row = sheet_info.get("rowCount", 1000)
        range_str = f"{sheet_name}!A{header_row}:ZZ{last_row}"
        
        result = await self.get_values(spreadsheet_id, range_str)
        values = result.get("values", [])
        
        if not values:
            return [], []
        
        headers = [str(v) if v else "" for v in values[0]]
        
        if data_start_row > 1 and data_start_row <= len(values):
            data_rows = values[data_start_row - 1:]
        else:
            data_rows = values[1:] if len(values) > 1 else []
        
        return headers, data_rows
    
    def parse_spreadsheet_id(self, url_or_id: str) -> str:
        """Extract spreadsheet ID from URL or return as-is if already an ID."""
        if "/" in url_or_id:
            parsed = urlparse(url_or_id)
            parts = parsed.path.strip("/").split("/")
            # Look for "d" followed by the actual ID
            for i, part in enumerate(parts):
                if part == "d" and i + 1 < len(parts):
                    return parts[i + 1]
            # Fallback: return last part if no "d" found
            return parts[-1] if parts else url_or_id
        return url_or_id
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test API connection by fetching token info."""
        try:
            if not self.access_token:
                await self._refresh_access_token()
            
            return {
                "connected": True,
                "app_id": self.app_id,
                "token_expires_in": int(self._token_expires_at - time.time())
                if self._token_expires_at > 0
                else 0,
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}
