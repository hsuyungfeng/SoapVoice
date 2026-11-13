"""SoapVoice 本機循環工作階段控制器 (Phase 31 契約 §1, D-31-01 ~ D-31-03, D-31-21 ~ D-31-23, D-31-30 ~ D-31-33).

職責：
1. 統籌 AudioRecorder、SegmentStore、ChunkUploader、CyclePipeline。
2. 提供 start、stop、status、archived 方法供 ControlServer 呼叫。
3. 執行緒安全與 command_id 冪等性保障。
4. 重啟自癒：偵測未 stop 循環標記 recording_interrupted，伺服器 ABANDONED 後回到待命。
5. 嚴格脫敏：status 絕不外洩病人姓名或病歷資料，僅揭露 patient_bound 布林值。
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Callable, Dict, Optional

from client.audio_recorder import AudioRecorder, recover_partial
from client.chunk_uploader import ChunkUploader
from client.cycle_pipeline import CyclePipeline
from client.segment_store import SegmentStore

logger = logging.getLogger("cycle_session")

_HEX32_RE = re.compile(r"^[0-9a-fA-F]{32}$")


class CycleSessionError(Exception):
    """循環工作階段錯誤，可映射為 IPC HTTP 回應。"""

    def __init__(self, error: str, message: str, status: int = 400):
        super().__init__(message)
        self.error = error
        self.message = message
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        return {"error": self.error, "message": self.message}


class CycleSession:
    """管理本機單一錄音循環的生命週期與狀態切換。"""

    def __init__(
        self,
        recorder: AudioRecorder,
        store: SegmentStore,
        uploader: Optional[ChunkUploader] = None,
        pipeline: Optional[CyclePipeline] = None,
        *,
        capture_patient: Optional[Callable[[], Dict[str, Any]]] = None,
        server_check: Optional[Callable[[str], Optional[str]]] = None,
        cleanup: Optional[Callable[[], None]] = None,
    ):
        self.recorder = recorder
        self.store = store
        self.uploader = uploader
        self.pipeline = pipeline
        self.capture_patient = capture_patient
        self.server_check = server_check
        self.cleanup = cleanup

        self._lock = threading.RLock()
        self._active_cycle_id: Optional[str] = None
        self._active_start_command: Optional[str] = None
        self._start_time: float = 0.0
        self._command_cache: Dict[str, Dict[str, Any]] = {}

        self._bg_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start_background(self) -> None:
        """啟動背景推進執行緒（每 2 秒輪詢 unfinished_cycles）。"""
        if self._bg_thread and self._bg_thread.is_alive():
            return
        self._stop_event.clear()
        self._bg_thread = threading.Thread(target=self._background_loop, daemon=True, name="cycle-session-bg")
        self._bg_thread.start()

    def stop_background(self, timeout: float = 3.0) -> None:
        """停止背景推進執行緒。"""
        self._stop_event.set()
        if self._bg_thread and self._bg_thread.is_alive():
            self._bg_thread.join(timeout=timeout)
        self._bg_thread = None

    def recover_on_startup(self) -> None:
        """啟動時檢查殘留循環並進行自癒處理。"""
        with self._lock:
            for c in self.store.unfinished_cycles():
                if c.total_chunks is None:
                    c_dir = self.store._cycle_dir(c.cycle_id)
                    try:
                        recover_partial(c_dir)
                    except Exception as exc:
                        logger.warning("recover_partial failed for %s: %s", c.cycle_id, exc)
                    self.store.set_error(c.cycle_id, "recording_interrupted")

    def _background_loop(self) -> None:
        """背景輪詢：推進未完成循環或偵測伺服器 ABANDONED。"""
        while not self._stop_event.is_set():
            try:
                self.advance_unfinished()
            except Exception as exc:
                logger.debug("advance_unfinished error: %s", exc)
            self._stop_event.wait(timeout=2.0)

    def advance_unfinished(self) -> None:
        """對所有未完成循環推進管線或檢查伺服器放棄狀態。"""
        unfinished = self.store.unfinished_cycles()
        for c in unfinished:
            if c.last_error == "recording_interrupted":
                if self.server_check:
                    try:
                        s_state = self.server_check(c.cycle_id)
                        if s_state == "ABANDONED":
                            # 伺服器已放棄，本機標記封存使狀態重回 IDLE；檔案完整保留 (D-31-33)
                            self.store.mark_archived(c.cycle_id)
                            logger.info("Cycle %s was ABANDONED on server, local cycle marked archived", c.cycle_id)
                    except Exception as exc:
                        logger.debug("server_check failed for %s: %s", c.cycle_id, exc)
            else:
                if self.pipeline:
                    try:
                        self.pipeline.advance(c.cycle_id)
                    except Exception as exc:
                        logger.debug("pipeline advance failed for %s: %s", c.cycle_id, exc)

    def start(self, command_id: str, cycle_id: str) -> Dict[str, Any]:
        """POST /control/v1/start - 開始錄音 (契約 §1)."""
        if not _HEX32_RE.match(command_id):
            raise CycleSessionError("invalid_field", "command_id 必須為 32 位 hex", status=422)
        if not _HEX32_RE.match(cycle_id):
            raise CycleSessionError("invalid_field", "cycle_id 必須為 32 位 hex", status=422)

        with self._lock:
            # 冪等性快取檢查
            if command_id in self._command_cache:
                return self._command_cache[command_id]

            # 錄音中檢查
            if self._active_cycle_id is not None and self.recorder.is_recording:
                if self._active_cycle_id == cycle_id:
                    # 相同 cycle_id 重送
                    res = self.status(target_cycle_id=cycle_id)
                    self._command_cache[command_id] = res
                    return res
                # 不同 cycle_id 呼叫 → 409 busy，絕不重設錄音 (Pitfall 5)
                raise CycleSessionError("busy", "錄音進行中，無法開始新循環", status=409)

            if self.recorder.is_recording:
                raise CycleSessionError("busy", "錄音進行中，無法開始新循環", status=409)

            # 檢查是否有未完成之循環（狀態為 UPLOADING 或 GENERATING）且非同一 cycle_id
            unfinished = self.store.unfinished_cycles()
            for u in unfinished:
                if u.cycle_id != cycle_id and u.last_error != "recording_interrupted" and not u.draft_submitted:
                    raise CycleSessionError("busy", f"前次循環 {u.cycle_id} 仍在處理中，無法開始新循環", status=409)

            # 擷取病人資訊
            ctx = {}
            if self.capture_patient:
                try:
                    ctx = self.capture_patient() or {}
                except Exception as exc:
                    logger.warning("capture_patient failed: %s", exc)
                    ctx = {}

            # 開啟本機循環目錄與紀錄 context
            c_dir = self.store.open_cycle(cycle_id)
            if ctx:
                self.store.set_context(cycle_id, ctx)

            # 啟動錄音器
            started = self.recorder.start_cycle(c_dir)
            if not started:
                raise CycleSessionError("recorder_unavailable", "麥克風無法開啟", status=503)

            self._active_cycle_id = cycle_id
            self._active_start_command = command_id
            self._start_time = time.time()

            res = self.status(target_cycle_id=cycle_id)
            self._command_cache[command_id] = res
            return res

    def stop(self, command_id: str, cycle_id: str) -> Dict[str, Any]:
        """POST /control/v1/stop - 停止錄音 (契約 §1)."""
        if not _HEX32_RE.match(command_id):
            raise CycleSessionError("invalid_field", "command_id 必須為 32 位 hex", status=422)
        if not _HEX32_RE.match(cycle_id):
            raise CycleSessionError("invalid_field", "cycle_id 必須為 32 位 hex", status=422)

        with self._lock:
            # 冪等性快取檢查
            if command_id in self._command_cache:
                return self._command_cache[command_id]

            if self._active_cycle_id is None or not self.recorder.is_recording:
                # 檢查是否為先前已停止的循環
                manifest = self.store.load(cycle_id)
                if manifest and manifest.total_chunks is not None:
                    res = self.status(target_cycle_id=cycle_id)
                    self._command_cache[command_id] = res
                    return res
                raise CycleSessionError("not_recording", "目前不在錄音狀態", status=409)

            if self._active_cycle_id != cycle_id:
                raise CycleSessionError("cycle_mismatch", "循環識別不符", status=409)

            # 停止錄音
            self.recorder.stop()

            # 設定總分段數
            manifest = self.store.load(cycle_id)
            total = len(manifest.chunks) if manifest else 0
            self.store.set_total(cycle_id, total)

            self._active_cycle_id = None

            # 喚醒上傳器
            if self.uploader:
                self.uploader.notify(cycle_id)

            res = self.status(target_cycle_id=cycle_id)
            self._command_cache[command_id] = res
            return res

    def status(self, target_cycle_id: Optional[str] = None) -> Dict[str, Any]:
        """GET /control/v1/status - 查詢當前狀態 (契約 §1)."""
        with self._lock:
            active_id = self._active_cycle_id
            is_rec = self.recorder.is_recording and active_id is not None
            start_t = self._start_time

        cid = target_cycle_id or active_id
        if is_rec and (target_cycle_id is None or target_cycle_id == active_id):
            st = "RECORDING"
            cid = active_id
            elapsed = round(max(0.0, time.time() - start_t), 1)
        elif cid:
            manifest = self.store.load(cid)
            elapsed = 0.0
            if manifest and manifest.last_error == "recording_interrupted":
                st = "ERROR"
            elif manifest and manifest.draft_submitted:
                st = "SUBMITTED"
            elif manifest and manifest.finalized:
                st = "GENERATING"
            elif manifest and manifest.total_chunks is not None:
                st = "UPLOADING"
            else:
                st = "IDLE"
        else:
            unfinished = self.store.unfinished_cycles()
            if unfinished:
                u = unfinished[0]
                cid = u.cycle_id
                elapsed = 0.0
                if u.last_error == "recording_interrupted":
                    st = "ERROR"
                elif u.draft_submitted:
                    st = "SUBMITTED"
                elif u.finalized:
                    st = "GENERATING"
                elif u.total_chunks is not None:
                    st = "UPLOADING"
                else:
                    st = "ERROR"
            else:
                cid = None
                st = "IDLE"
                elapsed = 0.0

        chunks_total = 0
        chunks_acked = 0
        chunks_pending = 0
        draft_submitted = False
        last_error = None
        patient_bound = False

        if cid:
            manifest = self.store.load(cid)
            if manifest:
                chunks_total = manifest.total_chunks if manifest.total_chunks is not None else len(manifest.chunks)
                chunks_acked = sum(1 for c in manifest.chunks if c.get("acked"))
                chunks_pending = len(self.store.pending_chunks(cid))
                draft_submitted = bool(manifest.draft_submitted)
                last_error = manifest.last_error
            try:
                ctx = self.store.get_context(cid)
                patient_bound = bool(
                    ctx.get("patient_name")
                    or ctx.get("screenshot_path")
                    or ctx.get("patient_ref")
                    or ctx.get("case_id")
                )
            except Exception:
                patient_bound = False

        return {
            "contract": "elc-p31-ipc/1",
            "state": st,
            "cycle_id": cid,
            "elapsed_seconds": float(elapsed),
            "patient_bound": bool(patient_bound),
            "chunks_total": int(chunks_total),
            "chunks_acked": int(chunks_acked),
            "chunks_pending": int(chunks_pending),
            "draft_submitted": bool(draft_submitted),
            "last_error": last_error,
        }

    def archived(self, cycle_id: str) -> Dict[str, Any]:
        """POST /control/v1/archived - 通知已封存 (契約 §1)."""
        if not _HEX32_RE.match(cycle_id):
            raise CycleSessionError("invalid_field", "cycle_id 必須為 32 位 hex", status=422)

        if not self.server_check:
            raise CycleSessionError("server_unavailable", "無法連線至伺服器驗證封存狀態", status=503)

        try:
            s_state = self.server_check(cycle_id)
        except Exception as exc:
            raise CycleSessionError("server_unavailable", f"伺服器連線異常: {exc}", status=503)

        if s_state is None:
            raise CycleSessionError("server_unavailable", "無法連線至伺服器驗證封存狀態", status=503)

        if s_state != "ARCHIVED":
            raise CycleSessionError("not_archived_on_server", f"伺服器循環尚未封存（當前狀態：{s_state}）", status=409)

        with self._lock:
            self.store.mark_archived(cycle_id)
            if self.cleanup:
                try:
                    self.cleanup()
                except Exception as exc:
                    logger.warning("cleanup error during archived: %s", exc)

        return {"cycle_id": cycle_id, "cleanup_eligible": True}
