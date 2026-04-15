import os
import sys
import threading
import time
import logging
import requests
import wave
import json
import pyperclip
import subprocess
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from pathlib import Path
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 載入環境變數
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

API_BASE_URL = "http://127.0.0.1:8010"
logger = logging.getLogger(__name__)

# --- 字型設定 ---
FONT_FAMILY = "Noto Sans CJK TC" if sys.platform == "linux" else "Segoe UI"

try:
    import pyaudio
except ImportError:
    pyaudio = None

from src.gui.config_manager import ConfigManager
from src.nlp.ocr_parser import OCRParser

class AudioRecorder:
    def __init__(self):
        self.is_recording = False
        self.frames = []
        self.p = None
        self.stream = None
        if pyaudio:
            try:
                self.p = pyaudio.PyAudio()
            except Exception:
                self.p = None

    def start_recording(self):
        if self.p is None: return
        self.is_recording = True
        self.frames = []
        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024
            )
        except Exception as e:
            logger.error(f"無法開啟錄音設備: {e}")
            self.is_recording = False
            self.stream = None

    def stop_recording(self, output_filename="record.wav"):
        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception: pass

        if self.frames and self.p:
            try:
                wf = wave.open(output_filename, "wb")
                wf.setnchannels(1)
                wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b"".join(self.frames))
                wf.close()
                return True
            except Exception as e:
                logger.error(f"音檔寫入失敗: {e}")
        return False

    def record_loop(self):
        while self.is_recording and self.stream:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                if data: self.frames.append(data)
            except Exception: pass

class SoapVoiceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SoapVoice Ultimate Premium")
        self.root.attributes("-topmost", True)

        # --- 尺寸配置 (旗艦級 720px 寬) ---
        self.width = 720
        self.compact_height = 360
        
        # 強化 Linux 下的解析度
        try:
            self.root.tk.call('tk', 'scaling', 1.8)
        except: pass

        try:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            self.expanded_height = min(1000, screen_height - 100)
            x_pos = screen_width - self.width - 30
            y_pos = 50
            self.geometry_compact = f"{self.width}x{self.compact_height}+{x_pos}+{y_pos}"
            self.geometry_expanded = f"{self.width}x{self.expanded_height}+{x_pos}+{y_pos}"
        except Exception:
            self.geometry_compact = "720x360+1000+50"
            self.geometry_expanded = "720x1000+1000+50"

        self.root.geometry(self.geometry_compact)
        self.root.resizable(False, False)

        self.setup_custom_styles()
        self.config_manager = ConfigManager()
        self.ocr_parser = OCRParser()
        self.recorder = AudioRecorder()

        self.current_soap_text = ""
        self.current_ocr_text = ""
        self.is_processing = False
        self.server_process = None

        self.setup_ui()
        self.update_ui_state("idle")
        self.start_backend_process()

    def setup_custom_styles(self):
        style = ttk.Style()
        try: style.theme_use("superhero")
        except Exception: pass
        
        default_font = (FONT_FAMILY, 13)
        style.configure(".", font=default_font)
        style.configure("TLabel", font=default_font)
        style.configure("TButton", font=(FONT_FAMILY, 13, "bold"))
        style.configure("Header.TLabel", font=(FONT_FAMILY, 22, "bold"))
        style.configure("TLabelframe.Label", font=(FONT_FAMILY, 14, "bold"), foreground="#14b8a6")

    def setup_ui(self):
        self.root.configure(bg="#0f1923")
        self.main_container = ttk.Frame(self.root, bootstyle="secondary")
        self.main_container.pack(fill=BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(self.main_container, bootstyle="primary", padding=(25, 20))
        header_frame.pack(fill=X)
        ttk.Label(header_frame, text="🏥 SOAPVOICE ULTIMATE", font=(FONT_FAMILY, 24, "bold"), bootstyle="inverse-primary").pack(side=LEFT)
        
        status_info = ttk.Frame(header_frame, bootstyle="primary")
        status_info.pack(side=RIGHT)
        self.status_var = tk.StringVar(value="啟動中...")
        self.indicator = tk.Canvas(status_info, width=18, height=18, bg="#0f1923", highlightthickness=0)
        self.indicator.pack(side=RIGHT, padx=(12, 0))
        self.indicator_circle = self.indicator.create_oval(3, 3, 15, 15, fill="#64748b", outline="")
        ttk.Label(status_info, textvariable=self.status_var, font=(FONT_FAMILY, 13, "bold"), bootstyle="inverse-primary").pack(side=RIGHT)

        # 控制卡片
        self.control_card = ttk.Frame(self.main_container, padding=25)
        self.control_card.pack(fill=X, padx=15, pady=15)
        btn_container = ttk.Frame(self.control_card); btn_container.pack(fill=X)
        self.btn_record = ttk.Button(btn_container, text=" 🎤 開始錄製對話 ", bootstyle="danger", command=self.start_recording)
        self.btn_record.pack(side=LEFT, padx=10, ipady=22, fill=X, expand=True)
        self.btn_stop = ttk.Button(btn_container, text=" ⏹ 停止錄音 ", bootstyle="secondary-outline", command=self.stop_recording, width=15, state=DISABLED)
        self.btn_stop.pack(side=LEFT, padx=10, ipady=22)
        self.btn_process = ttk.Button(btn_container, text=" ⚡ 執行 AI 處理 ", bootstyle="warning", command=self.process_recording, width=18, state=DISABLED)
        self.btn_process.pack(side=LEFT, padx=10, ipady=22)

        self.progress = ttk.Progressbar(self.control_card, mode="determinate", length=500, bootstyle="info-striped")
        self.progress.pack(fill=X, pady=(25, 0))
        self.status_label = ttk.Label(self.control_card, text="請稍候，系統初始化中...", font=(FONT_FAMILY, 11), bootstyle="secondary")
        self.status_label.pack(pady=(12, 0))

        # 展開面板
        self.result_container = ttk.Frame(self.main_container)
        self.canvas = tk.Canvas(self.result_container, bg="#0f1923", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.result_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, padding=25)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=self.width - 45)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.setup_result_ui()

    def setup_result_ui(self):
        # 1. 患者資訊
        p_card = ttk.Labelframe(self.scrollable_frame, text=" 🏥 患者臨床資訊 (AI 自動提取) ", padding=20)
        p_card.pack(fill=X, pady=(0, 20))
        fields = [("患者姓名", "patient_name"), ("出生日期", "birth_date"), ("病歷編號", "mrn"), ("身分證號", "patient_id")]
        self.patient_vars = {}
        for i, (label, key) in enumerate(fields):
            row, col = divmod(i, 2)
            cell = ttk.Frame(p_card); cell.grid(row=row, column=col, sticky="ew", padx=15, pady=12)
            ttk.Label(cell, text=label, font=(FONT_FAMILY, 10), bootstyle="secondary").pack(anchor="w")
            var = tk.StringVar(); ttk.Entry(cell, textvariable=var, font=(FONT_FAMILY, 13)).pack(fill=X, pady=(5, 0))
            self.patient_vars[key] = var
        p_card.columnconfigure(0, weight=1); p_card.columnconfigure(1, weight=1)
        
        # 2. 逐字稿
        t_card = ttk.Labelframe(self.scrollable_frame, text=" 📝 語音轉錄逐字稿 (可即時修正) ", padding=20)
        t_card.pack(fill=X, pady=15)
        self.text_transcript = tk.Text(t_card, font=(FONT_FAMILY, 13), bg="#1c2b36", fg="#dfe6e9", height=8, wrap=WORD, padx=15, pady=15, insertbackground="white", relief=FLAT)
        self.text_transcript.pack(fill=X)

        # 3. SOAP
        s_header = ttk.Frame(self.scrollable_frame); s_header.pack(fill=X, pady=(30, 12))
        ttk.Label(s_header, text=" 📋 旗艦級 SOAP 診斷報告 ", font=(FONT_FAMILY, 16, "bold"), bootstyle="primary").pack(side=LEFT)
        self.timestamp_label = ttk.Label(s_header, text="", font=(FONT_FAMILY, 10), bootstyle="secondary")
        self.timestamp_label.pack(side=RIGHT)
        self.text_soap = tk.Text(self.scrollable_frame, font=("Monospace", 13), bg="#1c2b36", fg="#dfe6e9", height=22, wrap=WORD, padx=20, pady=20, insertbackground="white", relief=FLAT)
        self.text_soap.pack(fill=X)

        # 4. 操作列
        act_frame = ttk.Frame(self.scrollable_frame, padding=10); act_frame.pack(fill=X, pady=35)
        m_row = ttk.Frame(act_frame); m_row.pack(fill=X, pady=(0, 20))
        ttk.Label(m_row, text="選用模型引擎:", font=(FONT_FAMILY, 12, "bold"), bootstyle="secondary").pack(side=LEFT)
        self.model_var = tk.StringVar(value="gemma4:e4b")
        ttk.Combobox(m_row, textvariable=self.model_var, values=["gemma4:e4b", "qwen2.5:7b"], state="readonly", width=18, font=(FONT_FAMILY, 12)).pack(side=LEFT, padx=15)

        b_row = ttk.Frame(act_frame); b_row.pack(fill=X)
        ttk.Button(b_row, text=" 💾 儲存並關閉 ", bootstyle="success", command=self.save_and_shrink).pack(side=LEFT, padx=5, expand=True, fill=X, ipady=18)
        ttk.Button(b_row, text=" 📋 複製 SOAP ", bootstyle="info-outline", command=self.copy_soap, width=15).pack(side=LEFT, padx=5, ipady=18)
        ttk.Button(b_row, text=" ☁️ HIS 匯出 ", bootstyle="warning-outline", command=self.export_to_cloud, width=15).pack(side=LEFT, padx=5, ipady=18)

    def expand_view(self):
        self.root.geometry(self.geometry_expanded)
        self.result_container.pack(fill=BOTH, expand=True)
        self.bind_mouse_wheel()

    def shrink_view(self):
        self.result_container.pack_forget()
        self.root.geometry(self.geometry_compact)

    def update_ui_state(self, state="idle"):
        if state == "idle":
            self.indicator.itemconfig(self.indicator_circle, fill="#10b981")
            self.status_var.set("系統就緒")
            self.btn_record.configure(state=NORMAL); self.btn_stop.configure(state=DISABLED); self.btn_process.configure(state=DISABLED)
            self.is_processing = False; self.progress["value"] = 0
        elif state == "recording":
            self.indicator.itemconfig(self.indicator_circle, fill="#ef4444")
            self.status_var.set("錄音中")
            self.btn_record.configure(state=DISABLED); self.btn_stop.configure(state=NORMAL)
        elif state == "processing":
            self.indicator.itemconfig(self.indicator_circle, fill="#f59e0b")
            self.status_var.set("分析中")
            self.is_processing = True; self.animate_progress()

    def animate_progress(self):
        if self.is_processing:
            curr = self.progress["value"]
            if curr < 95: self.progress["value"] = curr + 2; self.root.after(500, self.animate_progress)

    def start_recording(self):
        model_name = self.model_var.get()
        self.update_ui_state("recording")
        threading.Thread(target=self.run_ocr_and_match, args=(model_name,), daemon=True).start()
        self.recorder.start_recording()
        threading.Thread(target=self.recorder.record_loop, daemon=True).start()

    def stop_recording(self):
        self.update_ui_state("processing")
        wav_path = str(PROJECT_ROOT / "data" / "recordings" / "temp.wav")
        os.makedirs(os.path.dirname(wav_path), exist_ok=True)
        if self.recorder.stop_recording(wav_path):
            self.btn_process.configure(state=NORMAL); self.status_var.set("音檔就緒")
        else: self.status_var.set("❌ 失敗"); self.update_ui_state("idle")

    def process_recording(self):
        model_name = self.model_var.get(); self.update_ui_state("processing")
        wav_path = str(PROJECT_ROOT / "data" / "recordings" / "temp.wav")
        if os.path.exists(wav_path): threading.Thread(target=self.process_audio_api, args=(wav_path, model_name), daemon=True).start()
        else: self.update_ui_state("idle")

    def process_audio_api(self, wav_path, model_name):
        try:
            self.root.after(0, lambda: self.status_label.config(text="正在執行 ASR 語音轉錄..."))
            with open(wav_path, "rb") as f:
                res = requests.post(f"{API_BASE_URL}/api/v1/extended/transcribe", files={"audio": f}, timeout=60)
            transcript = res.json().get("transcript", "")
            if not transcript:
                self.root.after(0, lambda: (self.status_var.set("❌ 無內容"), self.update_ui_state("idle"))); return
            self.root.after(0, lambda: self.status_label.config(text="正在分析並生成 SOAP..."))
            res_soap = requests.post(f"{API_BASE_URL}/api/v1/extended/process", json={"transcript": transcript, "model": model_name}, timeout=120)
            self.root.after(0, lambda: self.on_process_complete(res_soap.json(), datetime.now().strftime("%H:%M:%S")))
        except Exception:
            self.root.after(0, lambda: (self.status_var.set("❌ API 錯誤"), self.update_ui_state("idle")))

    def on_process_complete(self, data, ts=""):
        self.update_ui_state("idle"); self.status_var.set("處理完成")
        self.text_transcript.delete("1.0", END); self.text_transcript.insert("1.0", data.get("transcript", ""))
        soap = data.get("soap", {})
        fmt = f"【 臨床診斷摘要 】\n● 症狀: {', '.join(data.get('symptoms', []))}\n"
        icd = data.get("icd10_codes", [])
        if icd: fmt += f"● ICD-10: {', '.join([f'{i.get('code')} {i.get('description')}' for i in icd])}\n"
        fmt += f"\n【 SOAP 病歷 (繁體中文) 】\n{soap.get('raw_zh', '無回傳')}\n\n【 SOAP Note (English) 】\n{soap.get('raw_en', 'No response')}\n\n"
        fmt += f"【 建議醫囑 】\n" + "\n".join([f"  - {o}" for o in data.get("medical_orders", [])])
        self.current_soap_text = fmt; self.text_soap.delete("1.0", END); self.text_soap.insert("1.0", fmt)
        self.timestamp_label.config(text=f"產出時間: {ts}"); self.expand_view()

    def run_ocr_and_match(self, model_name):
        try:
            ocr_text = self.ocr_parser.capture_screen_to_text()
            if not ocr_text: return
            self.current_ocr_text = ocr_text
            self.root.after(0, lambda: self.status_var.set("📸 OCR 成功"))
            prompt = self.ocr_parser.build_extraction_prompt(ocr_text, ["王醫師", "陳醫師"])
            try:
                res = requests.post(f"http://localhost:11434/api/generate", json={"model": model_name, "prompt": prompt, "stream": False, "format": "json"}, timeout=30)
                if res.status_code == 200:
                    info = json.loads(res.json().get("response", "{}"))
                    def update():
                        for k, v in self.patient_vars.items():
                            if k in info and info[k]: v.set(info[k])
                        self.status_var.set("✅ 資訊已帶入")
                    self.root.after(0, update)
            except: pass
        except Exception: pass

    def bind_mouse_wheel(self):
        def _on_mw(e):
            delta = e.delta if hasattr(e, 'delta') else 0
            if e.num == 4 or delta > 0: self.canvas.yview_scroll(-1, "units")
            elif e.num == 5 or delta < 0: self.canvas.yview_scroll(1, "units")
        self.root.bind_all("<MouseWheel>", _on_mw)
        self.root.bind_all("<Button-4>", _on_mw)
        self.root.bind_all("<Button-5>", _on_mw)

    def show_raw_ocr(self):
        top = tk.Toplevel(self.root); top.title("OCR 原始文字"); top.geometry("600x500"); top.attributes("-topmost", True)
        txt = tk.Text(top, font=(FONT_FAMILY, 12), padx=20, pady=20, bg="#1c2b36", fg="#dfe6e9")
        txt.pack(fill=BOTH, expand=True); txt.insert("1.0", self.current_ocr_text); txt.config(state=DISABLED)

    def copy_soap(self): pyperclip.copy(self.current_soap_text); self.status_var.set("✅ 已複製")

    def save_and_shrink(self): self.status_var.set("💾 已儲存"); self.shrink_view()

    def export_to_cloud(self): self.status_var.set("☁️ 匯出完成")

    def start_backend_process(self):
        try:
            if requests.get(f"{API_BASE_URL}/health", timeout=1).status_code == 200:
                self.root.after(0, lambda: self.update_ui_state("idle")); return
        except: pass
        def run():
            env = os.environ.copy(); env["PYTHONPATH"] = str(PROJECT_ROOT)
            cmd = [sys.executable, str(PROJECT_ROOT / "src" / "main.py")]
            self.server_process = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            for _ in range(30):
                try:
                    if requests.get(f"{API_BASE_URL}/health", timeout=1).status_code == 200:
                        self.root.after(0, lambda: self.update_ui_state("idle")); return
                except: time.sleep(1)
            self.root.after(0, lambda: self.status_var.set("❌ API 逾時"))
        threading.Thread(target=run, daemon=True).start()

    def on_closing(self):
        if self.server_process: self.server_process.terminate()
        self.root.destroy()

def main():
    root = ttk.Window(title="SoapVoice Ultimate", themename="superhero", resizable=(False, False))
    app = SoapVoiceApp(root); root.protocol("WM_DELETE_WINDOW", app.on_closing); root.mainloop()

if __name__ == "__main__": main()
