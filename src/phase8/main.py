"""
SoapVoice Phase 8 - 主整合模組

整合：
- 系統匣 (system_tray.py)
- 螢幕擷取 + OCR (capture_ocr.py)
- 語音錄製 + LLM SOAP (voice_recording.py)
- 結果浮動視窗 (results_window.py)
"""

import logging
import json
import time
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


class SoapVoiceApp:
    """SoapVoice 主應用程式"""

    def __init__(self):
        # 初始化各模組
        self._init_modules()

        # 狀態
        self.is_running = False
        self.current_session_id = ""

    def _init_modules(self):
        """初始化所有模組"""
        # 系統匣
        try:
            from src.system_tray import TrayIconManager

            self.tray = TrayIconManager(on_state_change=self._on_tray_action)
            logger.info("System tray initialized")
        except Exception as e:
            logger.warning(f"System tray init failed: {e}")
            self.tray = None

        # 擷取 + OCR
        try:
            from src.phase8.capture_ocr import CaptureWorkflow

            self.capture = CaptureWorkflow()
            logger.info("Capture OCR initialized")
        except Exception as e:
            logger.warning(f"Capture OCR init failed: {e}")
            self.capture = None

        # 語音錄製
        try:
            from src.phase8.voice_recording import VoiceRecordingWorkflow

            self.voice = VoiceRecordingWorkflow()
            logger.info("Voice recording initialized")
        except Exception as e:
            logger.warning(f"Voice recording init failed: {e}")
            self.voice = None

        # 結果視窗
        try:
            from src.phase8.results_window import ResultsWindow

            self.results_window = ResultsWindow(
                on_save_callback=self._on_save, on_export_callback=self._on_export
            )
            logger.info("Results window initialized")
        except Exception as e:
            logger.warning(f"Results window init failed: {e}")
            self.results_window = None

    def start(self):
        """啟動應用程式"""
        logger.info("Starting SoapVoice...")
        self.is_running = True

        # 啟動系統匣
        if self.tray:
            self.tray.start()

        # 啟動結果視窗（在背景）
        # self.results_window.run()  # 這會阻塞

        logger.info("SoapVoice started")

    def stop(self):
        """停止應用程式"""
        logger.info("Stopping SoapVoice...")
        self.is_running = False

        if self.tray:
            self.tray.stop()

        logger.info("SoapVoice stopped")

    def _on_tray_action(self, action: str):
        """處理系統匣動作"""
        logger.info(f"Tray action: {action}")

        if action == "capture":
            self._do_capture()
        elif action == "start_recording":
            self._start_recording()
        elif action == "stop_recording":
            self._stop_recording()
        elif action == "copy_soap":
            self._copy_soap()
        elif action == "copy_all":
            self._copy_all()
        elif action == "cloud_export":
            self._do_export()

    def _do_capture(self):
        """執行螢幕擷取 + OCR"""
        if not self.capture:
            logger.error("Capture not available")
            return

        logger.info("Starting screen capture...")

        if self.results_window:
            self.results_window.update_status("📸 擷取中...")

        # 在新執行緒執行
        threading.Thread(target=self._capture_thread, daemon=True).start()

    def _capture_thread(self):
        """擷取執行緒"""
        try:
            patient = self.capture.capture_and_extract()

            if self.results_window:
                self.results_window.update_data(
                    patient={
                        "name": patient.name,
                        "birthday": patient.birthday,
                        "id_number": patient.id_number,
                        "medical_record_number": patient.medical_record_number,
                        "doctor": patient.doctor,
                        "timestamp": patient.timestamp,
                    },
                    transcript="",
                    soap={},
                )
                self.results_window.update_status("✅ 擷取完成")

            logger.info(f"Captured: {patient.name}")

        except Exception as e:
            logger.error(f"Capture failed: {e}")
            if self.results_window:
                self.results_window.update_status("❌ 擷取失敗")

    def _start_recording(self):
        """開始錄音"""
        if not self.voice:
            logger.error("Voice recording not available")
            return

        logger.info("Starting recording...")

        if self.voice.start_recording():
            if self.results_window:
                self.results_window.update_status("🎤 錄音中...")

            if self.tray:
                from src.system_tray import RecordingState

                self.tray.update_state(RecordingState.RECORDING)
        else:
            logger.error("Failed to start recording")

    def _stop_recording(self):
        """停止錄音"""
        if not self.voice:
            return

        logger.info("Stopping recording...")

        if self.results_window:
            self.results_window.update_status("⏳ 處理中...")

        if self.tray:
            from src.system_tray import RecordingState

            self.tray.update_state(RecordingState.PROCESSING)

        # 在新執行緒執行處理
        threading.Thread(target=self._process_recording_thread, daemon=True).start()

    def _process_recording_thread(self):
        """處理錄音執行緒"""
        try:
            # 取得目前病患資訊
            patient_data = {}
            if self.results_window:
                patient_data = self.results_window.get_data().get("patient", {})

            result = self.voice.stop_and_process(patient_data)

            if result.success and self.results_window:
                self.results_window.update_data(
                    patient=patient_data,
                    transcript=result.transcript,
                    soap=result.soap,
                    audio_file=result.audio_file,
                )
                self.results_window.update_status("✅ 完成")

                if self.tray:
                    from src.system_tray import RecordingState

                    self.tray.update_state(RecordingState.COMPLETED)

            else:
                if self.results_window:
                    self.results_window.update_status("❌ 處理失敗")

                if self.tray:
                    from src.system_tray import RecordingState

                    self.tray.update_state(RecordingState.ERROR)

            logger.info("Recording processed")

        except Exception as e:
            logger.error(f"Process failed: {e}")
            if self.results_window:
                self.results_window.update_status("❌ 處理失敗")

    def _copy_soap(self):
        """複製 SOAP"""
        if self.results_window:
            self.results_window._copy_soap()

    def _copy_all(self):
        """複製全部"""
        if self.results_window:
            self.results_window._copy_all()

    def _do_export(self):
        """匯出"""
        if self.results_window:
            self.results_window._export()

    def _on_save(self, data: dict):
        """儲存回調"""
        logger.info("Saving data...")

        # 建立儲存目錄
        save_dir = Path("data/recordings")
        save_dir.mkdir(parents=True, exist_ok=True)

        # 建立儲存檔案
        session_id = time.strftime("%Y-%m-%d_%H%M%S")
        save_file = save_dir / f"session_{session_id}.json"

        with open(save_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved to: {save_file}")

    def _on_export(self, data: dict):
        """匯出回調"""
        logger.info("Exporting data...")

        # 先儲存
        self._on_save(data)

        # TODO: 未來可擴充為 Google Drive / SMB 匯出
        logger.info("Exported (local)")


def main():
    """主程式"""
    import argparse

    parser = argparse.ArgumentParser(description="SoapVoice Phase 8")
    parser.add_argument("--start", action="store_true", help="Start application")
    parser.add_argument("--test-ui", action="store_true", help="Test UI only")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    if args.test_ui:
        # 測試結果視窗
        from src.phase8.results_window import ResultsWindow

        window = ResultsWindow()
        window.run()

    elif args.start:
        app = SoapVoiceApp()
        app.start()

        print("SoapVoice 啟動中... 按 Enter 停止")
        input()

        app.stop()

    else:
        print("Usage:")
        print("  python -m src.phase8.main --start      # 啟動應用")
        print("  python -m src.phase8.main --test-ui  # 測試UI")


if __name__ == "__main__":
    main()
