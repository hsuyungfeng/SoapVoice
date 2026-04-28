"""重試管理與指數退避邏輯

職責：
- 計算指數退避延遲時間（base × multiplier^retry_count）
- 判斷是否應重試（retry_count < max_retries）
- 提供非同步等待接口（await wait_before_retry）
- 追蹤每個 session 的重試狀態（next_retry_at, last_attempt_at）

設計原則：
1. 純粹計算與狀態追蹤，不持有上傳邏輯（由 LANClient 整合）
2. session_id 為任意字串，呼叫方自行管理唯一性
3. 預設值 base=2.0, max_retries=3, multiplier=2.0 → 2/4/8 秒退避

使用：
    >>> rm = RetryManager(base_delay_sec=2.0, max_retries=3)
    >>> rm.get_retry_delay(0)
    2.0
    >>> rm.get_retry_delay(1)
    4.0
    >>> rm.should_retry("session-x", 3)
    False
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# 預設參數
DEFAULT_BASE_DELAY_SEC = 2.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_MULTIPLIER = 2.0


class RetryManager:
    """重試管理器：指數退避 + 最多 N 次重試。

    Attributes:
        base_delay_sec: 第一次退避秒數（retry_count=0 時的延遲）
        max_retries: 最多重試次數（含第一次嘗試外的重試）
        backoff_multiplier: 每次退避倍率（指數底）
        retry_state: dict[session_id → {count, next_retry_at, last_attempt_at}]
    """

    def __init__(
        self,
        base_delay_sec: float = DEFAULT_BASE_DELAY_SEC,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    ):
        if base_delay_sec < 0:
            raise ValueError(f"base_delay_sec must be >= 0, got {base_delay_sec}")
        if max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {max_retries}")
        if backoff_multiplier < 1.0:
            raise ValueError(
                f"backoff_multiplier must be >= 1.0, got {backoff_multiplier}"
            )

        self.base_delay_sec = base_delay_sec
        self.max_retries = max_retries
        self.backoff_multiplier = backoff_multiplier

        # 重試狀態追蹤：session_id → {"count", "next_retry_at", "last_attempt_at"}
        self.retry_state: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # 計算
    # ------------------------------------------------------------------

    def get_retry_delay(self, retry_count: int) -> float:
        """計算指數退避延遲時間（秒）。

        Args:
            retry_count: 已嘗試的重試次數（從 0 起算）

        Returns:
            退避秒數。負值 retry_count 回 0（防呆）。

        Examples:
            base=2.0, multiplier=2.0
            retry_count=0 → 2.0
            retry_count=1 → 4.0
            retry_count=2 → 8.0
        """
        if retry_count < 0:
            return 0.0
        return self.base_delay_sec * math.pow(self.backoff_multiplier, retry_count)

    def should_retry(self, session_id: str, current_retry_count: int) -> bool:
        """檢查是否應進行重試。

        Args:
            session_id: 識別字串（保留供未來擴充：可依 session 設不同上限）
            current_retry_count: 該 session 已重試次數

        Returns:
            True 若 current_retry_count < max_retries；否則 False。
        """
        del session_id  # 目前未用，保留供未來擴充
        return current_retry_count < self.max_retries

    def get_next_retry_delay(self, current_retry_count: int) -> float:
        """取得下次重試的延遲時間。

        Returns:
            退避秒數；若已達 max_retries 則回 -1（標記不應重試）。
        """
        if not self.should_retry("", current_retry_count):
            return -1.0
        return self.get_retry_delay(current_retry_count)

    # ------------------------------------------------------------------
    # 非同步等待
    # ------------------------------------------------------------------

    async def wait_before_retry(self, retry_count: int) -> bool:
        """等待指數退避延遲後再進行重試。

        Args:
            retry_count: 已嘗試的重試次數（從 0 起算）

        Returns:
            True 表示已等待完成可繼續重試；
            False 表示已達 max_retries，不應再重試（亦不會 sleep）。
        """
        if not self.should_retry("", retry_count):
            logger.info(
                "Max retries (%d) reached, aborting retry", self.max_retries
            )
            return False

        delay = self.get_retry_delay(retry_count)
        logger.info(
            "Waiting %.2fs before retry #%d (max=%d)",
            delay,
            retry_count + 1,
            self.max_retries,
        )
        if delay > 0:
            await asyncio.sleep(delay)
        return True

    # ------------------------------------------------------------------
    # 狀態追蹤
    # ------------------------------------------------------------------

    def mark_retry_scheduled(self, session_id: str, retry_count: int) -> None:
        """標記重試已排程（追蹤下次重試時間）。

        Args:
            session_id: 該重試屬於哪個 session
            retry_count: 該次重試的編號（已加上即將進行的這次）
        """
        next_delay = self.get_retry_delay(retry_count)
        now = datetime.now()
        self.retry_state[session_id] = {
            "count": retry_count,
            "next_retry_at": now + timedelta(seconds=next_delay),
            "last_attempt_at": now,
        }
        logger.debug(
            "Marked retry scheduled: session_id=%s count=%d next_in=%.1fs",
            session_id,
            retry_count,
            next_delay,
        )

    def reset_state(self, session_id: str) -> None:
        """重置特定 session 的重試狀態（成功上傳或放棄時呼叫）。"""
        self.retry_state.pop(session_id, None)

    def get_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """取得重試狀態。找不到回傳 None。"""
        return self.retry_state.get(session_id)

    def clear_all_state(self) -> None:
        """清空所有重試狀態。"""
        self.retry_state.clear()


__all__ = [
    "RetryManager",
    "DEFAULT_BASE_DELAY_SEC",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_BACKOFF_MULTIPLIER",
]
