"""
SoapVoice 系統匣模組 - 完整版

功能：
- 系統匣常駐
- 右鍵選單（含自動功能）
- 狀態圖示更新
- 快捷鍵監聽
- 病患資訊儲存
"""

import os
import sys
import threading
import time
import logging
import json
import shutil
from pathlib import Path
from typing import Optional, Callable, Dict
from enum import Enum
import pyperclip
import datetime
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


class RecordingState(Enum):
    """錄音狀態"""

    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class RecordingSession:
    """錄音會話資料"""

    def __init__(self):
        self.id = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.timestamp = datetime.datetime.now().isoformat()
        self.patient = {
            "name": "",
            "birthday": "",
            "id_number": "",
            "medical_record_number": "",
            "doctor": "",
        }
        self.transcript = ""
        self.soap = {"subjective": "", "objective": "", "assessment": "", "plan": ""}
        self.audio_file = ""

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "patient": self.patient,
            "transcript": self.transcript,
            "soap": self.soap,
            "audio_file": self.audio_file,
        }

    def get_soap_text(self) -> str:
        """取得 SOAP 純文字格式"""
        return f"""S: {self.soap.get("subjective", "")}
O: {self.soap.get("objective", "")}
A: {self.soap.get("assessment", "")}
P: {self.soap.get("plan", "")}"""

    def get_all_text(self) -> str:
        """取得全部文字（病患+逐字稿+SOAP）"""
        patient_info = f"""病患資訊：
姓名: {self.patient.get("name", "")}
生日: {self.patient.get("birthday", "")}
身份證: {self.patient.get("id_number", "")}
病歷號: {self.patient.get("medical_record_number", "")}
醫師: {self.patient.get("doctor", "")}
時間: {self.timestamp}

逐字稿：
{self.transcript}

SOAP 病歷：
{self.get_soap_text()}"""
        return patient_info


class TrayIconManager:
    """系統匣圖示管理器"""

    def __init__(self, on_state_change: Optional[Callable] = None):
        self.state = RecordingState.IDLE
        self.on_state_change = on_state_change
        self.current_session = RecordingSession()
        self._icon = None
        self._menu = None
        self._running = False
        self._data_dir = Path("data/recordings")

    def _get_icon_for_state(self):
        """根據狀態取得不同顏色的圖示"""
        try:
            width = 32
            height = 32
            # 使用 RGB 並確保背景不透明，對 Linux 相容性較佳
            image = Image.new("RGB", (width, height), color=(44, 62, 80))
            draw = ImageDraw.Draw(image)

            colors = {
                RecordingState.IDLE: (149, 165, 166),      # Gray
                RecordingState.RECORDING: (231, 76, 60),   # Red
                RecordingState.PROCESSING: (243, 156, 18), # Orange
                RecordingState.COMPLETED: (39, 174, 96),  # Green
                RecordingState.ERROR: (231, 76, 60),       # Red
            }

            color = colors.get(self.state, (149, 165, 166))
            # 畫一個實心圓
            draw.ellipse([4, 4, 28, 28], fill=color, outline=(255, 255, 255), width=1)
            
            return image
        except Exception as e:
            logger.error(f"建立狀態圖示失敗: {e}")
            return Image.new("RGB", (32, 32), color=(149, 165, 166))

    def create_menu(self):
        """建立右鍵選單"""
        try:
            import pystray

            return pystray.Menu(
                pystray.MenuItem("🪟 開啟視窗", self._on_restore, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("📸 擷取病患資訊", self._on_capture),
                pystray.MenuItem("🎤 開始錄音", self._on_start_recording),
                pystray.MenuItem("⏹ 停止錄音", self._on_stop_recording),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("📋 複製 SOAP", self._on_copy_soap),
                pystray.MenuItem("📋 複製全部 (自動)", self._on_copy_all),
                pystray.MenuItem("📋 貼上至 HIS (自動)", self._on_paste_his),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("📁 開啟記錄資料夾 (自動)", self._on_open_folder),
                pystray.MenuItem("☁️ 雲端匯出 (自動)", self._on_cloud_export),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("⚙️ 設定", self._on_settings),
                pystray.MenuItem("🚪 結束程式", self._on_exit_app),
            )
        except ImportError:
            return None

    def start(self):
        """啟動系統匣"""
        try:
            import pystray

            # 建立初始圖示
            image = self._get_icon_for_state()
            if image is None:
                logger.error("無法建立初始圖示")
                return

            self._icon = pystray.Icon(
                "SoapVoice",
                image=image,
                menu=self.create_menu(),
                title="SoapVoice",
            )
            
            # 再次確保 image 已設定
            if not self._icon.icon:
                self._icon.icon = image

            self._running = True
            # 使用 daemon=True 確保主程式結束時執行緒也會結束
            tray_thread = threading.Thread(target=self._icon.run, daemon=True)
            tray_thread.start()
            
            logger.info("System tray initialized and starting...")
        except ImportError as e:
            logger.error(f"pystray not installed: {e}")
        except Exception as e:
            logger.error(f"System tray start failed: {e}")

    def stop(self):
        if self._icon:
            self._icon.stop()
            self._running = False

    def update_state(self, new_state: RecordingState):
        self.state = new_state
        if self._icon and self._running:
            try:
                self._icon.image = self._get_icon_for_state()
                self._icon.title = f"SoapVoice - {new_state.value}"
            except:
                pass

    # ============ 自動功能實作 ============

    def _on_copy_all(self, icon, item):
        """📋 複製全部 - 自動複製病患+逐字稿+SOAP"""
        try:
            # 產生模擬資料（實際應從 current_session 取得）
            all_text = self.current_session.get_all_text()
            pyperclip.copy(all_text)
            self._show_notification("已複製全部到剪貼簿")
            logger.info("Copied all to clipboard")
        except Exception as e:
            logger.error(f"Copy failed: {e}")

    def _on_paste_his(self, icon, item):
        """📋 貼上至 HIS - 自動貼上到作用中視窗"""
        try:
            soap_text = self.current_session.get_soap_text()
            pyperclip.copy(soap_text)
            time.sleep(0.3)

            # 模擬貼上 (Ctrl+V)
            import keyboard

            keyboard.send("ctrl+v")
            self._show_notification("已貼上 SOAP 到 HIS")
            logger.info("Pasted to HIS")
        except Exception as e:
            logger.error(f"Paste failed: {e}")

    def _on_open_folder(self, icon, item):
        """📁 開啟記錄資料夾 - 自動開啟"""
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)

            # Windows
            if sys.platform == "win32":
                os.startfile(str(self._data_dir))
            # macOS
            elif sys.platform == "darwin":
                os.system(f'open "{self._data_dir}"')
            # Linux
            else:
                os.system(f'xdg-open "{self._data_dir}"')

            self._show_notification(f"已開啟資料夾: {self._data_dir}")
            logger.info(f"Opened folder: {self._data_dir}")
        except Exception as e:
            logger.error(f"Open folder failed: {e}")

    def _on_cloud_export(self, icon, item):
        """☁️ 雲端匯出 - 自動匯出"""
        try:
            # 確保資料夾存在
            self._data_dir.mkdir(parents=True, exist_ok=True)

            # 建立匯出資料
            export_data = self.current_session.to_json()
            export_file = self._data_dir / f"export_{self.current_session.id}.json"

            with open(export_file, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            # 檢查是否有音訊檔案
            audio_files = list(self._data_dir.glob(f"*.wav"))
            if audio_files:
                logger.info(f"Found {len(audio_files)} audio files for export")

            self._show_notification(f"已匯出至: {export_file}")
            logger.info(f"Exported to: {export_file}")

            # TODO: 未來可擴充為 Google Drive / SMB 匯出
            # 目前先儲存到本地，未來可加入：
            # - Google Drive API
            # - SMB/網路芳鄰
            # - FTP/SFTP

        except Exception as e:
            logger.error(f"Cloud export failed: {e}")

    def _show_notification(self, message: str):
        """顯示系統通知"""
        if self._icon:
            try:
                self._icon.notify(message, "SoapVoice")
            except (NotImplementedError, Exception) as e:
                logger.warning(f"無法顯示系統通知: {e}")

    # ============ 其他選單回調 ============

    def _on_capture(self, icon, item):
        logger.info("Menu: 擷取病患資訊")
        if self.on_state_change:
            self.on_state_change("capture")

    def _on_start_recording(self, icon, item):
        logger.info("Menu: 開始錄音")
        self.update_state(RecordingState.RECORDING)
        if self.on_state_change:
            self.on_state_change("start_recording")

    def _on_stop_recording(self, icon, item):
        logger.info("Menu: 停止錄音")
        self.update_state(RecordingState.PROCESSING)
        if self.on_state_change:
            self.on_state_change("stop_recording")

    def _on_copy_soap(self, icon, item):
        """複製 SOAP"""
        try:
            soap_text = self.current_session.get_soap_text()
            pyperclip.copy(soap_text)
            self._show_notification("已複製 SOAP")
        except Exception as e:
            logger.error(f"Copy failed: {e}")

    def _on_restore(self, icon, item):
        if self.on_state_change:
            self.on_state_change("restore")

    def _on_settings(self, icon, item):
        if self.on_state_change:
            self.on_state_change("settings")

    def _on_exit_app(self, icon, item):
        if self.on_state_change:
            self.on_state_change("exit")

    def _on_exit(self, icon, item):
        self.stop()
        sys.exit(0)


def main():
    """測試系統匣"""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.start:
        manager = TrayIconManager()
        manager.start()
        print("系統匣已啟動")
        input()
        manager.stop()


if __name__ == "__main__":
    main()
