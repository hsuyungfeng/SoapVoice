"""Phase 31: SoapVoice 串流分段背景上傳器 (D-31-20, D-31-22, D-31-27, D-31-30).

功能：
- 背景依序上傳未 acked 分段至 elc server POST /api/cycles/{cycle_id}/chunks
- 比對 server 回應之 sha256，相符才標記 acked (D-31-30)
- 409/422 記錄錯誤並中止該循環上傳（不刪檔）
- 5xx/連線錯誤進行指數退避重試，錄音與分段切檔不受阻塞 (D-31-22)
"""

from __future__ import annotations

import logging
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

import httpx

from client.segment_store import SegmentStore

logger = logging.getLogger("soapvoice.chunk_uploader")


class ChunkUploader:
    """背景分段上傳器。"""

    def __init__(
        self,
        store: SegmentStore,
        *,
        base_url: str,
        api_key: str,
        http: Optional[httpx.Client] = None,
        sleep: Callable[[float], None] = time.sleep,
        max_backoff: float = 30.0,
    ):
        self.store = store
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._http = http
        self.sleep = sleep
        self.max_backoff = float(max_backoff)
        self._backoff = 1.0

        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """啟動背景上傳執行緒。"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="ChunkUploaderWorker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止背景上傳執行緒。"""
        self._stop_event.set()
        self._wake_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def notify(self, cycle_id: Optional[str] = None) -> None:
        """喚醒背景上傳執行緒。"""
        self._wake_event.set()

    def progress(self, cycle_id: str) -> Tuple[int, int, int]:
        """取得特定循環之上傳進度：(total, acked, pending)。"""
        m = self.store.load(cycle_id)
        if not m:
            return 0, 0, 0
        total = m.total_chunks if m.total_chunks is not None else len(m.chunks)
        acked = sum(1 for c in m.chunks.values() if c.get("acked"))
        pending = len(m.chunks) - acked
        return total, acked, pending

    def _get_client(self) -> httpx.Client:
        if self._http is not None:
            return self._http
        return httpx.Client(timeout=10.0)

    def process_once(self, cycle_id: str) -> int:
        """同步執行單一循環之一輪未完成分段上傳 (供測試與內部迴圈呼叫)。

        回傳本輪成功 acked 之分段數量。
        """
        pending_seqs = self.store.pending_chunks(cycle_id)
        if not pending_seqs:
            return 0

        m = self.store.load(cycle_id)
        if not m or m.last_error:
            return 0

        client = self._get_client()
        should_close = self._http is None
        acked_count = 0
        c_dir = self.store.open_cycle(cycle_id)

        try:
            for seq in pending_seqs:
                chunk = m.chunks.get(str(seq))
                if not chunk:
                    continue

                chunk_path = Path(chunk["path"])
                if not chunk_path.is_absolute():
                    chunk_path = c_dir / chunk_path
                if not chunk_path.is_file():
                    self.store.set_error(cycle_id, f"音檔分段不存在: {chunk_path}")
                    break

                audio_bytes = chunk_path.read_bytes()
                local_sha = chunk["sha256"]

                url = f"{self.base_url}/api/cycles/{cycle_id}/chunks"
                files = {"audio": (chunk_path.name, audio_bytes, "audio/wav")}
                data = {"seq": str(seq), "sha256": local_sha}
                headers = {"X-API-Key": self.api_key}

                try:
                    resp = client.post(url, data=data, files=files, headers=headers)
                except (httpx.RequestError, OSError) as exc:
                    logger.warning("上傳分段連線失敗 (cycle=%s, seq=%d): %s", cycle_id, seq, exc)
                    self.sleep(self._backoff)
                    self._backoff = min(self._backoff * 2.0, self.max_backoff)
                    break

                if resp.status_code in (200, 201):
                    try:
                        resp_json = resp.json()
                        server_sha = str(resp_json.get("sha256") or "")
                    except Exception:
                        server_sha = ""

                    acked = self.store.mark_acked(cycle_id, seq, server_sha)
                    if acked:
                        self._backoff = 1.0
                        acked_count += 1
                        logger.info("分段上傳已確認 (cycle=%s, seq=%d)", cycle_id, seq)
                    else:
                        logger.warning("分段 SHA256 不符，未確認 (cycle=%s, seq=%d)", cycle_id, seq)
                elif resp.status_code in (409, 422):
                    try:
                        resp_json = resp.json()
                        err_msg = resp_json.get("error") or resp_json.get("message") or f"HTTP {resp.status_code}"
                    except Exception:
                        err_msg = f"HTTP {resp.status_code}"
                    self.store.set_error(cycle_id, f"Upload rejected ({resp.status_code}): {err_msg}")
                    break
                elif resp.status_code in (401, 403):
                    self.store.set_error(cycle_id, "API key 無效")
                    break
                elif resp.status_code >= 500:
                    logger.warning("Server 回應 5xx (cycle=%s, seq=%d): %s", cycle_id, seq, resp.status_code)
                    self.sleep(self._backoff)
                    self._backoff = min(self._backoff * 2.0, self.max_backoff)
                    break
                else:
                    logger.warning("未預期狀態碼: %s", resp.status_code)
                    break
        finally:
            if should_close:
                client.close()

        return acked_count

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            unfinished = self.store.unfinished_cycles()
            for m in unfinished:
                if self._stop_event.is_set():
                    break
                if not m.finalized and not m.last_error:
                    try:
                        self.process_once(m.cycle_id)
                    except Exception as exc:
                        logger.debug("上傳迴圈異常 (cycle=%s): %s", m.cycle_id, exc)

            self._wake_event.wait(timeout=1.0)
            self._wake_event.clear()
