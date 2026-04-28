"""LAN 客戶端 GUI（Tkinter）

職責：
- 主視窗 SOAPVoiceGUI（錄音、截圖、連線指示燈、SOAP 面板）
- ConnectionIndicator：以 Canvas 畫圓表示綠/黃/紅
- SOAPPanel：以 ttk.Notebook 分頁顯示 S/O/A/P + 摘要

設計重點：
1. GUI 與業務邏輯（LANClient/AudioRecorder/ScreenshotCapture）解耦
2. 連線狀態回調支援 async（測試以 run_until_complete 驗證）
3. asyncio 事件迴圈於 mainloop 之外的 thread 執行（main.py 啟動）
4. tkinter 在無顯示伺服器時無法實例化，測試自動 skip

模組為「視圖層」：所有副作用（錄音、上傳）由控制器（main.py）銜接
"""

from __future__ import annotations

import asyncio
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


# 連線狀態列舉（與 client.lan_client 一致，避免循環依賴不直接 import）
_VALID_STATUSES = ("unknown", "healthy", "degraded", "offline")
_STATUS_COLORS = {
    "healthy": "#2ecc71",   # 綠
    "degraded": "#f1c40f",  # 黃
    "offline": "#e74c3c",   # 紅
    "unknown": "#95a5a6",   # 灰
}
_STATUS_TEXTS = {
    "healthy": "連線正常",
    "degraded": "服務降級",
    "offline": "離線",
    "unknown": "未知",
}


class ConnectionIndicator(tk.Canvas):
    """連線狀態指示燈（綠/黃/紅 圓燈）。

    使用 Canvas 直接繪圓，避免外部圖示資源依賴。
    GUI 端只關心字串狀態，不直接 import lan_client 常數。

    Public API:
        set_status(status: str) → None  # 更新顏色，未知狀態 fallback 至 "unknown"
        status: str                     # 當前狀態（屬性，便於測試斷言）
    """

    SIZE = 30
    PADDING = 5

    def __init__(self, parent: tk.Misc, **kwargs: Any):
        kwargs.setdefault("width", self.SIZE)
        kwargs.setdefault("height", self.SIZE)
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("bg", "white")
        super().__init__(parent, **kwargs)
        self._status: str = "unknown"
        self._draw()

    @property
    def status(self) -> str:
        return self._status

    def set_status(self, status: str) -> None:
        """更新指示燈顏色。未知狀態自動 fallback 至 'unknown'（灰）。"""
        if status not in _VALID_STATUSES:
            logger.debug("Unknown indicator status %r; using 'unknown'", status)
            status = "unknown"
        self._status = status
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        color = _STATUS_COLORS.get(self._status, _STATUS_COLORS["unknown"])
        x0 = self.PADDING
        y0 = self.PADDING
        x1 = self.SIZE - self.PADDING
        y1 = self.SIZE - self.PADDING
        self.create_oval(x0, y0, x1, y1, fill=color, outline="#34495e", width=2)


class SOAPPanel(tk.Frame):
    """SOAP 結構化展示面板（S/O/A/P + 摘要 共 5 分頁）。

    Notebook 分頁設計便於醫師快速切換、複製貼上。
    `display_soap()` 接受 dict（伺服器回應的 soap 欄位）。

    Public API:
        display_soap(soap: dict) → None
        soap_sections: dict[str, tk.Text]   # 給測試直接讀取顯示內容
    """

    SECTION_KEYS = ("S", "O", "A", "P", "summary")
    SECTION_LABELS = {
        "S": "S (主訴)",
        "O": "O (客觀)",
        "A": "A (評估)",
        "P": "P (計畫)",
        "summary": "摘要",
    }

    def __init__(self, parent: tk.Misc, **kwargs: Any):
        super().__init__(parent, **kwargs)

        title = tk.Label(self, text="SOAP 結果", font=("TkDefaultFont", 14, "bold"))
        title.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(10, 5))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)

        # soap_sections: { "S (主訴)": Text, ... }（測試以中文 key 索引）
        self.soap_sections: Dict[str, tk.Text] = {}
        for key in self.SECTION_KEYS:
            label = self.SECTION_LABELS[key]
            frame = ttk.Frame(self.notebook)
            text_widget = tk.Text(frame, height=10, width=60, wrap=tk.WORD)
            text_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
            self.notebook.add(frame, text=label)
            self.soap_sections[label] = text_widget

    def display_soap(self, soap_data: Dict[str, Any]) -> None:
        """填入 SOAP 資料。空欄位顯示空字串而非 'None'。"""
        if not isinstance(soap_data, dict):
            logger.warning("display_soap called with non-dict: %r", type(soap_data))
            return

        for key in self.SECTION_KEYS:
            label = self.SECTION_LABELS[key]
            widget = self.soap_sections.get(label)
            if widget is None:
                continue
            value = soap_data.get(key) or ""
            try:
                widget.delete("1.0", tk.END)
                widget.insert("1.0", str(value))
            except tk.TclError as exc:  # noqa: PERF203 — Tk 異常需個別捕獲
                logger.warning("Failed to update SOAP section %s: %s", label, exc)

        # 自動切到「S (主訴)」分頁，方便醫師閱讀
        try:
            self.notebook.select(0)
        except tk.TclError:
            pass


class SOAPVoiceGUI(tk.Tk):
    """LAN 客戶端主視窗。

    元件：
        - ConnectionIndicator + 文字標籤
        - 錄音按鈕、截圖按鈕（綁定外部 callback）
        - SOAPPanel
        - 狀態列（顯示錯誤訊息或操作提示）

    重要設計：
    1. 不直接持有 audio_recorder / screenshot_capture（由 main.py 透過
       `set_recording_callbacks()` 綁定，避免 GUI 模組依賴 PyAudio）
    2. `update_connection_status()` / `display_soap_result()` 為 async，
       便於從 asyncio 事件迴圈呼叫；內部使用 `after()` 排程到 Tk 主執行緒
    3. 自動把 `lan_client.connection_status_callback` 接到自己

    Public API（測試使用）:
        connection_indicator: ConnectionIndicator
        soap_panel: SOAPPanel
        async update_connection_status(status: str) → None
        async display_soap_result(result: dict) → None
        set_recording_callbacks(on_record, on_screenshot)
    """

    def __init__(self, lan_client: Any):
        super().__init__()
        self.lan_client = lan_client
        self.is_recording: bool = False
        self._record_callback: Optional[Callable[[bool], None]] = None
        self._screenshot_callback: Optional[Callable[[], None]] = None

        self.title("SoapVoice LAN 瘦客戶端")
        self.geometry("900x650")
        self.minsize(700, 500)

        self._build_top_bar()
        self._build_soap_area()
        self._build_status_bar()

        # 將連線狀態與結果回調掛到 LANClient（lan_client 為 Any，避免硬綁型別）
        try:
            self.lan_client.connection_status_callback = self._sync_status_callback
            self.lan_client.result_callback = self._sync_result_callback
        except AttributeError:
            logger.warning("lan_client does not expose status/result callbacks")

        # 視窗關閉鉤子
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # 介面組裝
    # ------------------------------------------------------------------

    def _build_top_bar(self) -> None:
        top_frame = tk.Frame(self, padx=10, pady=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        # 連線指示燈
        self.connection_indicator = ConnectionIndicator(top_frame)
        self.connection_indicator.pack(side=tk.LEFT, padx=(0, 5))

        self.connection_label = tk.Label(top_frame, text="連線狀態：未知", font=("TkDefaultFont", 10))
        self.connection_label.pack(side=tk.LEFT, padx=(0, 20))

        # 錄音按鈕
        self.record_button = tk.Button(
            top_frame,
            text="● 開始錄音",
            font=("TkDefaultFont", 12, "bold"),
            bg="#3498db",
            fg="white",
            activebackground="#2980b9",
            activeforeground="white",
            padx=15,
            pady=6,
            command=self._on_record_click,
        )
        self.record_button.pack(side=tk.LEFT, padx=5)

        # 截圖按鈕
        self.screenshot_button = tk.Button(
            top_frame,
            text="📷 立即截圖",
            font=("TkDefaultFont", 11),
            padx=12,
            pady=6,
            command=self._on_screenshot_click,
        )
        self.screenshot_button.pack(side=tk.LEFT, padx=5)

        # 病患/醫師資訊（簡易表單）
        info_frame = tk.Frame(top_frame)
        info_frame.pack(side=tk.LEFT, padx=20)

        tk.Label(info_frame, text="病患:").grid(row=0, column=0, sticky="e", padx=2)
        self.patient_var = tk.StringVar()
        tk.Entry(info_frame, textvariable=self.patient_var, width=12).grid(row=0, column=1, padx=2)

        tk.Label(info_frame, text="醫師:").grid(row=0, column=2, sticky="e", padx=2)
        self.doctor_var = tk.StringVar()
        tk.Entry(info_frame, textvariable=self.doctor_var, width=12).grid(row=0, column=3, padx=2)

    def _build_soap_area(self) -> None:
        self.soap_panel = SOAPPanel(self)
        self.soap_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

    def _build_status_bar(self) -> None:
        self._status_var = tk.StringVar(value="就緒")
        status_bar = tk.Label(
            self,
            textvariable=self._status_var,
            anchor="w",
            relief=tk.SUNKEN,
            padx=8,
            pady=4,
            bg="#ecf0f1",
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------------------
    # 公開 API（async）— 為了相容測試 run_until_complete 呼叫
    # ------------------------------------------------------------------

    async def update_connection_status(self, status: str) -> None:
        """async 介面：更新連線指示燈與標籤。

        測試會以 `asyncio.run_until_complete(app.update_connection_status(...))` 呼叫。
        """
        self._apply_status(status)

    async def display_soap_result(self, result: Dict[str, Any]) -> None:
        """async 介面：當 LANClient 接收 SOAP 回應時被呼叫。"""
        self._apply_soap_result(result)

    # ------------------------------------------------------------------
    # 同步包裝（給 LANClient 的 callback；可被同步或非同步呼叫端使用）
    # ------------------------------------------------------------------

    def _sync_status_callback(self, status: str) -> None:
        """同步 callback：以 Tk after() 排程到主執行緒，避免跨 thread 操作 widget。"""
        try:
            self.after(0, lambda: self._apply_status(status))
        except (tk.TclError, RuntimeError) as exc:
            logger.debug("Status callback during shutdown: %s", exc)

    def _sync_result_callback(self, result: Dict[str, Any]) -> None:
        try:
            self.after(0, lambda: self._apply_soap_result(result))
        except (tk.TclError, RuntimeError) as exc:
            logger.debug("Result callback during shutdown: %s", exc)

    # ------------------------------------------------------------------
    # 真實渲染
    # ------------------------------------------------------------------

    def _apply_status(self, status: str) -> None:
        self.connection_indicator.set_status(status)
        text = _STATUS_TEXTS.get(self.connection_indicator.status, str(status))
        self.connection_label.config(text=f"連線狀態：{text}")

        # 離線/降級時降級錄音按鈕（不可上傳）
        if status in ("offline", "degraded"):
            self.record_button.config(state=tk.DISABLED)
            error = getattr(self.lan_client, "last_health_error", None)
            if error:
                self._set_status_message(f"⚠ {text}：{error}")
            else:
                self._set_status_message(f"⚠ {text}")
        else:
            self.record_button.config(state=tk.NORMAL)
            if status == "healthy":
                self._set_status_message("就緒")

    def _apply_soap_result(self, result: Dict[str, Any]) -> None:
        if not isinstance(result, dict):
            logger.warning("display_soap_result got non-dict: %r", type(result))
            return

        soap = result.get("soap")
        session_id = result.get("session_id", "<unknown>")
        if isinstance(soap, dict):
            self.soap_panel.display_soap(soap)
            self._set_status_message(f"✓ SOAP 已生成（session_id={session_id}）")
        else:
            status = result.get("status", "unknown")
            self._set_status_message(f"上傳完成但未生成 SOAP（status={status}）")

    def _set_status_message(self, message: str) -> None:
        try:
            self._status_var.set(message)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # 按鈕事件
    # ------------------------------------------------------------------

    def _on_record_click(self) -> None:
        """切換錄音狀態，呼叫外部 callback。"""
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.record_button.config(text="■ 停止錄音", bg="#e74c3c", activebackground="#c0392b")
            self._set_status_message("錄音中...")
        else:
            self.record_button.config(text="● 開始錄音", bg="#3498db", activebackground="#2980b9")
            self._set_status_message("錄音結束，準備上傳...")

        if self._record_callback is not None:
            try:
                self._record_callback(self.is_recording)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Record callback failed: %s", exc)
                messagebox.showerror("錄音錯誤", str(exc))

    def _on_screenshot_click(self) -> None:
        if self._screenshot_callback is None:
            self._set_status_message("截圖功能未綁定")
            return
        try:
            self._screenshot_callback()
            self._set_status_message("已截圖")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Screenshot callback failed: %s", exc)
            messagebox.showerror("截圖錯誤", str(exc))

    # ------------------------------------------------------------------
    # 控制器整合 API
    # ------------------------------------------------------------------

    def set_recording_callbacks(
        self,
        on_record: Optional[Callable[[bool], None]] = None,
        on_screenshot: Optional[Callable[[], None]] = None,
    ) -> None:
        """由 main.py 綁定錄音/截圖實作（避免 GUI 模組依賴 PyAudio）。"""
        self._record_callback = on_record
        self._screenshot_callback = on_screenshot

    def get_patient_doctor(self) -> tuple[str, str]:
        """回傳目前輸入欄的（病患, 醫師）名稱。"""
        return self.patient_var.get().strip(), self.doctor_var.get().strip()

    def show_version_mismatch(self, server_version: str, required_version: str) -> None:
        """啟動時版本不相容彈窗。"""
        messagebox.showwarning(
            "版本不相容",
            f"伺服器版本 {server_version} 低於客戶端要求版本 {required_version}。\n"
            "請更新伺服器或聯絡管理員。",
        )

    # ------------------------------------------------------------------
    # 生命週期
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        """視窗關閉前停止 LANClient 後台監控。"""
        try:
            if hasattr(self.lan_client, "stop"):
                self.lan_client.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass


__all__ = ["SOAPVoiceGUI", "ConnectionIndicator", "SOAPPanel"]
