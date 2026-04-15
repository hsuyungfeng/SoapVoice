"""
SoapVoice Phase 8.4 - 結果浮動視窗

功能：
- 右側浮動視窗
- 顯示病患資訊（可編輯）
- 顯示逐字稿
- 顯示 SOAP 病歷
- 一鍵複製功能
"""

import os
import sys
import logging
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Optional, Dict, Callable
import pyperclip
import threading

logger = logging.getLogger(__name__)


class ResultsWindow:
    """結果浮動視窗"""

    def __init__(
        self,
        on_save_callback: Optional[Callable] = None,
        on_export_callback: Optional[Callable] = None,
    ):
        self.on_save_callback = on_save_callback
        self.on_export_callback = on_export_callback

        self.window = None
        self._setup_window()
        self._create_widgets()

        # 資料
        self.patient_data = {
            "name": "",
            "birthday": "",
            "id_number": "",
            "medical_record_number": "",
            "doctor": "",
            "timestamp": "",
        }
        self.transcript = ""
        self.soap = {"subjective": "", "objective": "", "assessment": "", "plan": ""}
        self.audio_file = ""

    def _setup_window(self):
        """設定視窗"""
        self.window = tk.Tk()
        self.window.title("📋 SoapVoice 錄音結果")

        # 取得螢幕尺寸
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()

        # 視窗大小：寬度 = 螢幕 1/4，高度 = 滿版
        width = screen_width // 4
        height = screen_height

        # 位置：右側
        x = screen_width - width
        y = 0

        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.attributes("-topmost", True)  # 永遠在最上層
        self.window.attributes("-alpha", 0.95)  # 稍微透明

        # 關閉時隱藏而非銷毀
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        # 樣式
        self.window.configure(bg="#ECF0F1")

    def _create_widgets(self):
        """建立元件"""

        # 標題列
        title_frame = tk.Frame(self.window, bg="#2C3E50", height=40)
        title_frame.pack(fill="x", padx=0, pady=0)

        title_label = tk.Label(
            title_frame,
            text="📋 SoapVoice 錄音結果",
            bg="#2C3E50",
            fg="white",
            font=("Microsoft JhengHei", 12, "bold"),
        )
        title_label.pack(pady=8)

        # 狀態列
        self.status_label = tk.Label(
            self.window,
            text="狀態: 待機中",
            bg="#ECF0F1",
            fg="#34495E",
            font=("Microsoft JhengHei", 9),
        )
        self.status_label.pack(pady=5)

        # 病患資訊區
        self._create_patient_section()

        # 逐字稿區
        self._create_transcript_section()

        # SOAP 區
        self._create_soap_section()

        # 按鈕區
        self._create_button_section()

    def _create_patient_section(self):
        """病患資訊區"""
        frame = tk.LabelFrame(
            self.window, text="【病患資訊】", bg="#ECF0F1", font=("Microsoft JhengHei", 10, "bold")
        )
        frame.pack(fill="x", padx=10, pady=5)

        # 姓名
        tk.Label(frame, text="姓名:", bg="#ECF0F1").grid(row=0, column=0, sticky="w", padx=5)
        self.name_entry = tk.Entry(frame, width=20)
        self.name_entry.grid(row=0, column=1, padx=5, pady=2)

        # 生日
        tk.Label(frame, text="生日:", bg="#ECF0F1").grid(row=1, column=0, sticky="w", padx=5)
        self.birthday_entry = tk.Entry(frame, width=20)
        self.birthday_entry.grid(row=1, column=1, padx=5, pady=2)

        # 身份證
        tk.Label(frame, text="身份證:", bg="#ECF0F1").grid(row=2, column=0, sticky="w", padx=5)
        self.id_entry = tk.Entry(frame, width=20)
        self.id_entry.grid(row=2, column=1, padx=5, pady=2)

        # 病歷號
        tk.Label(frame, text="病歷號:", bg="#ECF0F1").grid(row=3, column=0, sticky="w", padx=5)
        self.mrn_entry = tk.Entry(frame, width=20)
        self.mrn_entry.grid(row=3, column=1, padx=5, pady=2)

        # 醫師
        tk.Label(frame, text="醫師:", bg="#ECF0F1").grid(row=4, column=0, sticky="w", padx=5)
        self.doctor_entry = tk.Entry(frame, width=20)
        self.doctor_entry.grid(row=4, column=1, padx=5, pady=2)

        # 時間
        tk.Label(frame, text="時間:", bg="#ECF0F1").grid(row=5, column=0, sticky="w", padx=5)
        self.time_label = tk.Label(frame, text="", bg="#ECF0F1", fg="#7F8C8D")
        self.time_label.grid(row=5, column=1, sticky="w", padx=5)

    def _create_transcript_section(self):
        """逐字稿區"""
        frame = tk.LabelFrame(
            self.window, text="【逐字稿】", bg="#ECF0F1", font=("Microsoft JhengHei", 10, "bold")
        )
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.transcript_text = scrolledtext.ScrolledText(
            frame, height=5, width=40, font=("Microsoft JhengHei", 9), wrap="word"
        )
        self.transcript_text.pack(padx=5, pady=5, fill="both", expand=True)

    def _create_soap_section(self):
        """SOAP 區"""
        frame = tk.LabelFrame(
            self.window, text="【SOAP 病歷】", bg="#ECF0F1", font=("Microsoft JhengHei", 10, "bold")
        )
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        # S
        tk.Label(frame, text="S:", bg="#ECF0F1", fg="#3498DB", font=("", 9, "bold")).grid(
            row=0, column=0, sticky="nw", padx=5
        )
        self.soap_s = tk.Text(frame, height=2, width=35, font=("", 9))
        self.soap_s.grid(row=0, column=1, padx=5, pady=2)

        # O
        tk.Label(frame, text="O:", bg="#ECF0F1", fg="#27AE60", font=("", 9, "bold")).grid(
            row=1, column=0, sticky="nw", padx=5
        )
        self.soap_o = tk.Text(frame, height=2, width=35, font=("", 9))
        self.soap_o.grid(row=1, column=1, padx=5, pady=2)

        # A
        tk.Label(frame, text="A:", bg="#ECF0F1", fg="#E67E22", font=("", 9, "bold")).grid(
            row=2, column=0, sticky="nw", padx=5
        )
        self.soap_a = tk.Text(frame, height=2, width=35, font=("", 9))
        self.soap_a.grid(row=2, column=1, padx=5, pady=2)

        # P
        tk.Label(frame, text="P:", bg="#ECF0F1", fg="#9B59B6", font=("", 9, "bold")).grid(
            row=3, column=0, sticky="nw", padx=5
        )
        self.soap_p = tk.Text(frame, height=2, width=35, font=("", 9))
        self.soap_p.grid(row=3, column=1, padx=5, pady=2)

    def _create_button_section(self):
        """按鈕區"""
        frame = tk.Frame(self.window, bg="#ECF0F1")
        frame.pack(fill="x", padx=10, pady=10)

        # 複製 SOAP
        btn_copy = tk.Button(
            frame,
            text="📋 複製 SOAP",
            command=self._copy_soap,
            bg="#3498DB",
            fg="white",
            font=("Microsoft JhengHei", 9),
            width=12,
        )
        btn_copy.pack(side="left", padx=3)

        # 複製全部
        btn_copy_all = tk.Button(
            frame,
            text="📋 複製全部",
            command=self._copy_all,
            bg="#9B59B6",
            fg="white",
            font=("Microsoft JhengHei", 9),
            width=12,
        )
        btn_copy_all.pack(side="left", padx=3)

        # 儲存
        btn_save = tk.Button(
            frame,
            text="💾 儲存",
            command=self._save,
            bg="#27AE60",
            fg="white",
            font=("Microsoft JhengHeI", 9),
            width=10,
        )
        btn_save.pack(side="left", padx=3)

        # 雲端匯出
        btn_export = tk.Button(
            frame,
            text="☁️ 匯出",
            command=self._export,
            bg="#F39C12",
            fg="white",
            font=("Microsoft JhengHei", 9),
            width=10,
        )
        btn_export.pack(side="left", padx=3)

    def _copy_soap(self):
        """複製 SOAP 並自動關閉視窗"""
        soap_text = f"S: {self.soap_s.get('1.0', 'end').strip()}\n"
        soap_text += f"O: {self.soap_o.get('1.0', 'end').strip()}\n"
        soap_text += f"A: {self.soap_a.get('1.0', 'end').strip()}\n"
        soap_text += f"P: {self.soap_p.get('1.0', 'end').strip()}"

        pyperclip.copy(soap_text)
        messagebox.showinfo("複製成功", "SOAP 已複製到剪貼簿")

        # 自動儲存
        self._auto_save()

        # 自動關閉視窗
        self._auto_close()

    def _auto_save(self):
        """自動儲存到本地"""
        try:
            import json
            from pathlib import Path
            import datetime

            save_dir = Path("data/recordings")
            save_dir.mkdir(parents=True, exist_ok=True)

            session_id = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
            save_file = save_dir / f"session_{session_id}.json"

            data = self.get_data()

            with open(save_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Auto-saved: {save_file}")
            self.update_status("💾 已儲存")

            # 自動匯出到雲端（本地）
            self._auto_export()

        except Exception as e:
            logger.error(f"Auto-save failed: {e}")

    def _auto_export(self):
        """自動匯出到雲端（本地資料夾）"""
        try:
            import json
            from pathlib import Path
            import datetime
            import shutil

            # 建立匯出資料夾
            export_base = Path("data/cloud_export")
            export_base.mkdir(parents=True, exist_ok=True)

            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            export_dir = export_base / date_str
            export_dir.mkdir(parents=True, exist_ok=True)

            # 複製最新儲存的 session
            recordings = sorted(Path("data/recordings").glob("session_*.json"))
            if recordings:
                latest = recordings[-1]
                dest = export_dir / latest.name
                shutil.copy2(latest, dest)
                logger.info(f"Auto-exported: {dest}")
                self.update_status("☁️ 已匯出")

        except Exception as e:
            logger.error(f"Auto-export failed: {e}")

    def _auto_close(self):
        """自動關閉視窗"""
        self.window.withdraw()
        logger.info("Window auto-closed after copy")

    def _copy_all(self):
        """複製全部"""
        all_text = f"""病患資訊：
姓名: {self.name_entry.get()}
生日: {self.birthday_entry.get()}
身份證: {self.id_entry.get()}
病歷號: {self.mrn_entry.get()}
醫師: {self.doctor_entry.get()}
時間: {self.time_label.cget("text")}

逐字稿：
{self.transcript_text.get("1.0", "end").strip()}

SOAP 病歷：
S: {self.soap_s.get("1.0", "end").strip()}
O: {self.soap_o.get("1.0", "end").strip()}
A: {self.soap_a.get("1.0", "end").strip()}
P: {self.soap_p.get("1.0", "end").strip()}"""

        pyperclip.copy(all_text)
        messagebox.showinfo("複製成功", "全部資料已複製到剪貼簿")

    def _save(self):
        """儲存"""
        if self.on_save_callback:
            self.on_save_callback(self.get_data())
        else:
            messagebox.showinfo("儲存", "儲存功能")

    def _export(self):
        """雲端匯出"""
        if self.on_export_callback:
            self.on_export_callback(self.get_data())
        else:
            messagebox.showinfo("雲端匯出", "雲端匯出功能")

    def _on_close(self):
        """關閉視窗"""
        self.window.withdraw()

    def show(self):
        """顯示視窗"""
        self.window.deiconify()
        self.window.lift()

    def hide(self):
        """隱藏視窗"""
        self.window.withdraw()

    def update_data(self, patient: dict, transcript: str, soap: dict, audio_file: str = ""):
        """更新資料並顯示"""
        # 更新病患資訊
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, patient.get("name", ""))

        self.birthday_entry.delete(0, "end")
        self.birthday_entry.insert(0, patient.get("birthday", ""))

        self.id_entry.delete(0, "end")
        self.id_entry.insert(0, patient.get("id_number", ""))

        self.mrn_entry.delete(0, "end")
        self.mrn_entry.insert(0, patient.get("medical_record_number", ""))

        self.doctor_entry.delete(0, "end")
        self.doctor_entry.insert(0, patient.get("doctor", ""))

        self.time_label.config(text=patient.get("timestamp", ""))

        # 更新逐字稿
        self.transcript_text.delete("1.0", "end")
        self.transcript_text.insert("1.0", transcript)

        # 更新 SOAP
        self.soap_s.delete("1.0", "end")
        self.soap_s.insert("1.0", soap.get("subjective", ""))

        self.soap_o.delete("1.0", "end")
        self.soap_o.insert("1.0", soap.get("objective", ""))

        self.soap_a.delete("1.0", "end")
        self.soap_a.insert("1.0", soap.get("assessment", ""))

        self.soap_p.delete("1.0", "end")
        self.soap_p.insert("1.0", soap.get("plan", ""))

        # 儲存
        self.patient_data = patient
        self.transcript = transcript
        self.soap = soap
        self.audio_file = audio_file

        # 顯示
        self.show()

    def update_status(self, status: str):
        """更新狀態"""
        self.status_label.config(text=f"狀態: {status}")

    def get_data(self) -> dict:
        """取得目前資料"""
        return {
            "patient": {
                "name": self.name_entry.get(),
                "birthday": self.birthday_entry.get(),
                "id_number": self.id_entry.get(),
                "medical_record_number": self.mrn_entry.get(),
                "doctor": self.doctor_entry.get(),
                "timestamp": self.time_label.cget("text"),
            },
            "transcript": self.transcript_text.get("1.0", "end").strip(),
            "soap": {
                "subjective": self.soap_s.get("1.0", "end").strip(),
                "objective": self.soap_o.get("1.0", "end").strip(),
                "assessment": self.soap_a.get("1.0", "end").strip(),
                "plan": self.soap_p.get("1.0", "end").strip(),
            },
            "audio_file": self.audio_file,
        }

    def run(self):
        """執行視窗"""
        self.window.mainloop()


def main():
    """測試結果視窗"""
    window = ResultsWindow()

    # 模擬資料
    test_patient = {
        "name": "王小明",
        "birthday": "1980-01-15",
        "id_number": "A123456789",
        "medical_record_number": "MRN123456",
        "doctor": "林醫師",
        "timestamp": "2026-04-09 14:30:22",
    }

    test_transcript = """病人主訴胸悶兩天，伴隨呼吸困難。
無發燒或咳嗽。
過去有心臟病史。
理學檢查：胸部無異常發現。"""

    test_soap = {
        "subjective": "Patient reports chest tightness for two days with dyspnea.",
        "objective": "No specific abnormal findings on physical examination.",
        "assessment": "R07.89 - Chest discomfort, R06.02 - Shortness of breath",
        "plan": "ECG recommended. Follow-up in 1 week.",
    }

    window.update_data(test_patient, test_transcript, test_soap)
    window.run()


if __name__ == "__main__":
    main()
