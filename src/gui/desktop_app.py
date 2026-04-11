import os
import sys
import threading
import time
import logging
import requests
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 載入環境變數
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass  # dotenv 未安裝，使用系統環境變數

API_BASE_URL = "http://127.0.0.1:8010"

try:
    import pyaudio
except ImportError:
    pyaudio = None

import pyperclip  # noqa: E402
import tkinter as tk  # noqa: E402
import ttkbootstrap as ttk  # noqa: E402

from src.gui.config_manager import ConfigManager  # noqa: E402
from src.nlp.ocr_parser import OCRParser  # noqa: E402


class AudioRecorder:
    def __init__(self):
        self.is_recording = False
        self.frames = []
        self.p = None
        self.stream = None
        try:
            self.p = pyaudio.PyAudio()
        except Exception:
            self.p = None

    def start_recording(self):
        if self.p is None:
            return
        self.is_recording = True
        self.frames = []
        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024
            )
        except Exception:
            self.is_recording = False
            self.stream = None

    def stop_recording(self, output_filename="record.wav"):
        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass

        if self.frames and self.p:
            wf = wave.open(output_filename, "wb")
            wf.setnchannels(1)
            wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b"".join(self.frames))
            wf.close()

    def record_loop(self):
        while self.is_recording and self.stream:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                self.frames.append(data)
            except Exception:
                pass


class SoapVoiceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SoapVoice Sidebar")
        self.root.attributes("-topmost", True)

        # --- 尺寸優化 (Premium Dimensions) ---
        self.width = 420
        self.compact_height = 240
        self.expanded_height = 900

        # 計算靠右對齊位置
        try:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            self.expanded_height = min(900, screen_height - 60)
            x_pos = screen_width - self.width - 20
            y_pos = 30
            self.geometry_compact = f"{self.width}x{self.compact_height}+{x_pos}+{y_pos}"
            self.geometry_expanded = f"{self.width}x{self.expanded_height}+{x_pos}+{y_pos}"
        except Exception:
            self.geometry_compact = "420x240+1000+30"
            self.geometry_expanded = "420x900+1000+30"

        self.root.geometry(self.geometry_compact)
        self.root.resizable(False, False)

        self.config_manager = ConfigManager()
        self.ocr_parser = OCRParser()
        self.recorder = AudioRecorder()

        self.current_soap_text = ""
        self.result_popup = None
        self.is_processing = False

        self.setup_ui()
        self.update_ui_state("idle")
        self.start_backend_thread()

    def setup_ui(self):
        # 使用 Superhero 主題建立高級感 (由 ttk.Window 初始化)
        self.root.configure(bg="#0f1923")

        # --- 階段 1: 控制中心容器 (始終顯示) ---
        self.main_container = ttk.Frame(self.root, bootstyle="secondary")
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(self.main_container, bootstyle="primary")
        header_frame.pack(fill=tk.X)

        ttk.Label(
            header_frame,
            text=" 🎤 SOAPVOICE SIDEBAR ",
            font=("Segoe UI", 12, "bold"),
            bootstyle="inverse-primary",
            padding=(15, 10),
        ).pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="初始化中...")
        ttk.Label(
            header_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 10),
            bootstyle="inverse-primary",
            padding=10,
        ).pack(side=tk.RIGHT)

        # 控制按鈕區 (Horizontal Flex)
        self.btn_frame = ttk.Frame(self.main_container, padding=20)
        self.btn_frame.pack(fill=tk.X)

        self.btn_record = ttk.Button(
            self.btn_frame,
            text=" 🎤 開始錄製 ",
            bootstyle="danger",
            command=self.start_recording,
            width=15,
        )
        self.btn_record.pack(side=tk.LEFT, padx=8, ipady=10)

        self.btn_stop = ttk.Button(
            self.btn_frame,
            text=" ⏹ 停止 ",
            bootstyle="secondary-outline",
            command=self.stop_recording,
            width=8,
            state="disabled",
        )
        self.btn_stop.pack(side=tk.LEFT, padx=8, ipady=10)

        self.btn_process = ttk.Button(
            self.btn_frame,
            text=" ⚡ 處理 ",
            bootstyle="warning",
            command=self.process_recording,
            width=8,
            state="disabled",
        )
        self.btn_process.pack(side=tk.LEFT, padx=8, ipady=10)

        # 狀態指示圓點
        self.indicator_label = ttk.Label(
            self.main_container, text="● ACTIVE", font=("Segoe UI", 10, "bold"), bootstyle="success"
        )
        self.indicator_label.pack(pady=(0, 15))

        # --- 階段 2: 展開結果面板 (初始隱藏) ---
        self.result_frame = ttk.Frame(self.main_container, padding=10)

        # 患者資訊摘要 (OCR)
        self.patient_card = ttk.Labelframe(self.result_frame, text=" 🏥 PATIENT INFO (AI SCAN) ")
        self.patient_card.pack(fill=tk.X, padx=10, pady=10)

        self.lbl_patient_info = ttk.Label(
            self.patient_card,
            text="Waiting for OCR capture...",
            font=("Segoe UI", 10),
            wraplength=350,
            justify=tk.LEFT,
        )
        self.lbl_patient_info.pack(fill=tk.X)

        # SOAP 結果區域
        ttk.Label(
            self.result_frame,
            text=" 📋 CLINICAL SOAP REPORT ",
            font=("Segoe UI", 10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w", padx=10, pady=(15, 5))

        self.text_soap = tk.Text(
            self.result_frame,
            font=("Consolas", 10),
            bg="#1c2b36",
            fg="#dfe6e9",
            relief=tk.FLAT,
            padx=15,
            pady=15,
            height=25,
            insertbackground="white",
        )
        self.text_soap.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 操作按鈕
        action_frame = ttk.Frame(self.result_frame, padding=10)
        action_frame.pack(fill=tk.X)

        self.btn_copy = ttk.Button(
            action_frame,
            text=" 📋 COPY REPORT & SHRINK ",
            bootstyle="success",
            command=self.copy_and_shrink,
        )
        self.btn_copy.pack(fill=tk.X, ipady=12)

    def expand_view(self):
        """展開為大面板"""
        self.root.geometry(self.geometry_expanded)
        self.result_frame.pack(fill=tk.BOTH, expand=True)

    def shrink_view(self):
        """收合為控制條"""
        self.result_frame.pack_forget()
        self.root.geometry(self.geometry_compact)

    def get_current_doctor_name(self):
        return "醫師"

    def start_backend_thread(self):
        try:
            res = requests.get(f"{API_BASE_URL}/health", timeout=1)
            if res.status_code == 200:
                print("目前已有後端 API 運行中，將直接連線 (避免 Port 8010 衝突)。")
                self.check_api_ready()
                return
        except Exception:
            pass  # API 未啟動，走正常程序啟動

        def run_server():
            from src.offline_server import main as start_offline_server
            import sys

            sys.argv = ["offline_server.py"]
            start_offline_server()

        threading.Thread(target=run_server, daemon=True).start()
        self.check_api_ready()

    def check_api_ready(self):
        def ping():
            while True:
                try:
                    res = requests.get(f"{API_BASE_URL}/health", timeout=2)
                    if res.status_code == 200:
                        self.root.after(0, lambda: self.status_var.set("✅ 準備就緒"))
                        self.root.after(0, lambda: self.update_ui_state("idle"))
                        break
                except Exception:
                    time.sleep(2)

        threading.Thread(target=ping, daemon=True).start()

    def update_ui_state(self, state="idle"):
        if state == "idle":
            self.indicator_label.configure(bootstyle="success", text="● READY")
            self.btn_record.configure(state="normal", bootstyle="danger")
            self.btn_stop.configure(state="disabled", bootstyle="secondary-outline")
            self.btn_process.configure(state="disabled", bootstyle="secondary-outline")
            self.is_processing = False
        elif state == "recording":
            self.indicator_label.configure(bootstyle="danger", text="● RECORDING")
            self.btn_record.configure(state="disabled")
            self.btn_stop.configure(state="normal", bootstyle="danger")
            self.btn_process.configure(state="disabled")
        elif state == "processing":
            self.indicator_label.configure(bootstyle="warning", text="● GENERATING REPORT...")
            self.btn_record.configure(state="disabled")
            self.btn_stop.configure(state="disabled")
            self.btn_process.configure(state="disabled", bootstyle="warning")
            self.is_processing = True
        elif state == "result":
            self.indicator_label.configure(bootstyle="success", text="● DOCUMENTATION READY")
            self.btn_record.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.btn_process.configure(state="disabled")
            self.is_processing = False

    def start_recording(self):
        self.update_ui_state("recording")
        self.status_var.set("🎙️ 錄音中...")

        threading.Thread(target=self.run_ocr_and_match, daemon=True).start()

        self.recorder.start_recording()
        threading.Thread(target=self.recorder.record_loop, daemon=True).start()

    def stop_recording(self):
        self.update_ui_state("processing")
        self.status_var.set("⏹️ 錄音停止")

        wav_path = str(PROJECT_ROOT / "data" / "recordings" / "temp.wav")
        os.makedirs(os.path.dirname(wav_path), exist_ok=True)
        self.recorder.stop_recording(wav_path)

    def process_recording(self):
        self.update_ui_state("processing")
        self.status_var.set("⏳ 處理病歷中...")

        wav_path = str(PROJECT_ROOT / "data" / "recordings" / "temp.wav")
        if os.path.exists(wav_path):
            threading.Thread(target=self.process_audio_api, args=(wav_path,), daemon=True).start()
        else:
            self.status_var.set("❌ 無音檔")
            self.update_ui_state("idle")

    def run_test_audio(self):
        test_wav_path = str(PROJECT_ROOT / "tests" / "fixtures" / "scenarios" / "chest_pain.wav")
        if os.path.exists(test_wav_path):
            self.update_ui_state("processing")
            self.status_var.set("🧪 使用測試音檔處理中...")
            threading.Thread(
                target=self.process_audio_api, args=(test_wav_path,), daemon=True
            ).start()
        else:
            self.status_var.set("❌ 找不到測試音檔")
            self.update_ui_state("idle")

    def run_ocr_and_match(self):
        try:
            # 調試：記錄 OCR 解析器狀態
            logger = logging.getLogger(__name__)
            logger.debug(
                f"OCR 解析器狀態: HAS_OLLAMA_VISION={self.ocr_parser.HAS_OLLAMA_VISION}, HAS_PYTESSERACT={self.ocr_parser.HAS_PYTESSERACT}"
            )

            ocr_text = self.ocr_parser.capture_screen_to_text()

            # 使用主執行緒安全地更新 UI
            def update_ui():
                try:
                    if ocr_text and ocr_text.strip():
                        self.status_var.set("📸 OCR 擷取成功")
                        # 儲存 OCR 文字供後續使用
                        self.current_ocr_text = ocr_text
                        logger.debug(f"OCR 擷取成功，文字長度: {len(ocr_text)}")
                    else:
                        self.status_var.set("📸 無 OCR 文字")
                        self.current_ocr_text = ""
                        logger.debug("OCR 返回空文字")
                except Exception as e:
                    logger.warning(f"更新 OCR UI 失敗: {e}")

            # 在主執行緒中調度 UI 更新
            self.root.after(0, update_ui)

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"OCR 擷取失敗: {e}")

            def update_error():
                try:
                    self.status_var.set("📸 OCR 略過")
                    self.current_ocr_text = ""
                except Exception as e2:
                    logger.warning(f"更新錯誤 UI 失敗: {e2}")

            self.root.after(0, update_error)

    def process_audio_api(self, wav_path):
        try:
            with open(wav_path, "rb") as f:
                res = requests.post(
                    f"{API_BASE_URL}/api/v1/extended/transcribe", files={"audio": f}
                )
            data = res.json()
            transcript = data.get("transcript", "")

            if transcript:
                res_soap = requests.post(
                    f"{API_BASE_URL}/api/v1/extended/process",
                    json={"transcript": transcript, "model": "qwen2.5:7b"},
                )
                soap_data = res_soap.json()
                self.current_soap_text = soap_data.get("soap", "無生成內容")

                self.root.after(0, lambda: self.on_process_complete())
            else:
                self.root.after(0, lambda: self.show_error("轉錄失敗"))
        except Exception as e:
            self.root.after(0, lambda e=e: self.show_error(str(e)))

    def on_process_complete(self):
        self.update_ui_state("result")
        self.status_var.set("✅ 病歷生成完成")

        if self.current_soap_text:
            self.text_soap.config(state="normal")
            self.text_soap.delete("1.0", tk.END)
            self.text_soap.insert("1.0", self.current_soap_text)
            self.text_soap.config(state="disabled")

            # 顯示患者資訊 (如果有)
            if hasattr(self, "current_ocr_text") and self.current_ocr_text:
                # 簡單擷取姓名或 ID (模擬)
                self.lbl_patient_info.config(text=f"擷取內容: {self.current_ocr_text[:30]}...")

            self.expand_view()

    def copy_and_shrink(self):
        """複製內容並收合視窗"""
        pyperclip.copy(self.current_soap_text)
        self.status_var.set("✅ 已複製到剪貼簿")
        self.shrink_view()
        self.root.after(2000, self.reset_ui)

    def show_error(self, err_msg):
        self.status_var.set(f"❌ {err_msg[:20]}")
        self.root.after(2000, self.reset_ui)

    def reset_ui(self):
        self.update_ui_state("idle")
        self.status_var.set("✅ 準備就緒")

    def open_settings(self):
        pass


def main():
    # 使用 ttk.Window 代替 tk.Tk 確保 bootstyle 正確執行
    root = ttk.Window(title="SoapVoice Sidebar", themename="superhero", resizable=(False, False))
    root.attributes("-topmost", True)
    SoapVoiceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
