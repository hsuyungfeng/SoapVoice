"""非同步 HTTP 客戶端（httpx + tenacity 重試）

封裝 httpx.AsyncClient，提供：
- async context manager（自動建立/關閉連線池）
- GET（含指數退避重試）
- POST multipart/form-data（含指數退避重試）
- 結構化錯誤（HTTPClientError 包裝 httpx 例外）

使用：
    >>> async with AsyncHTTPClient("http://192.168.1.100:8010") as c:
    ...     result = await c.get("api/v1/health")
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


# multipart 檔案 tuple：(filename, file_bytes, content_type)
MultipartFile = Tuple[str, bytes, str]


class HTTPClientError(Exception):
    """HTTP 客戶端錯誤的統一包裝。"""

    def __init__(self, message: str, *, status_code: Optional[int] = None, original: Optional[BaseException] = None):
        super().__init__(message)
        self.status_code = status_code
        self.original = original


class AsyncHTTPClient:
    """非同步 HTTP 客戶端，含 tenacity 重試。

    Attributes:
        base_url: 伺服器基礎 URL
        timeout: 請求總逾時
        max_retries: 重試上限（含首次嘗試之外的次數）
        retry_min_wait: 退避最短秒數
        retry_max_wait: 退避最長秒數
    """

    # 觸發重試的網路類例外
    _RETRY_EXCEPTIONS = (
        httpx.RequestError,
        httpx.HTTPStatusError,
    )

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_min_wait: float = 2.0,
        retry_max_wait: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout)
        self.max_retries = max_retries
        self.retry_min_wait = retry_min_wait
        self.retry_max_wait = retry_max_wait
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "AsyncHTTPClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_url(self, endpoint: str) -> str:
        """組合完整 URL。endpoint 可帶或不帶前置斜線。"""
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def _retrying(self) -> AsyncRetrying:
        """建立 tenacity AsyncRetrying 物件，可重複建構供每次呼叫使用。"""
        return AsyncRetrying(
            stop=stop_after_attempt(max(1, self.max_retries)),
            wait=wait_exponential(multiplier=1, min=self.retry_min_wait, max=self.retry_max_wait),
            retry=retry_if_exception_type(self._RETRY_EXCEPTIONS),
            reraise=True,
        )

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """GET 請求，回傳 JSON dict。

        Raises:
            HTTPClientError: 重試耗盡或非網路類錯誤。
        """
        url = self._build_url(endpoint)

        async def _do_get() -> Dict[str, Any]:
            client = self._client or httpx.AsyncClient(timeout=self.timeout)
            owned = self._client is None
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            finally:
                if owned:
                    await client.aclose()

        try:
            async for attempt in self._retrying():
                with attempt:
                    return await _do_get()
        except RetryError as exc:
            last = exc.last_attempt.exception() if exc.last_attempt else None
            raise HTTPClientError(
                f"GET {url} failed after retries: {last}",
                original=last,
            ) from exc
        except self._RETRY_EXCEPTIONS as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            raise HTTPClientError(
                f"GET {url} failed: {exc}",
                status_code=status,
                original=exc,
            ) from exc
        # 不應抵達此處（async for 必有 yield 或 raise）
        raise HTTPClientError(f"GET {url} unexpected control flow")

    async def post_multipart(
        self,
        endpoint: str,
        files: Dict[str, MultipartFile],
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST multipart/form-data，回傳 JSON dict。

        Args:
            files: {"audio_file": (filename, bytes, "audio/wav"), ...}
            data: 純文字表單欄位

        Raises:
            HTTPClientError: 重試耗盡或非網路類錯誤。
        """
        url = self._build_url(endpoint)

        async def _do_post() -> Dict[str, Any]:
            client = self._client or httpx.AsyncClient(timeout=self.timeout)
            owned = self._client is None
            try:
                response = await client.post(url, files=files, data=data or {})
                response.raise_for_status()
                return response.json()
            finally:
                if owned:
                    await client.aclose()

        try:
            async for attempt in self._retrying():
                with attempt:
                    return await _do_post()
        except RetryError as exc:
            last = exc.last_attempt.exception() if exc.last_attempt else None
            raise HTTPClientError(
                f"POST {url} failed after retries: {last}",
                original=last,
            ) from exc
        except self._RETRY_EXCEPTIONS as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            raise HTTPClientError(
                f"POST {url} failed: {exc}",
                status_code=status,
                original=exc,
            ) from exc
        raise HTTPClientError(f"POST {url} unexpected control flow")
