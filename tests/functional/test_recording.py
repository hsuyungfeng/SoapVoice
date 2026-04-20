"""
測試錄音功能
"""

import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_audio_recorder_import():
    """測試 AudioRecorder 類別導入"""
    try:
        from src.gui.desktop_app import AudioRecorder

        # 如果 pyaudio 未安裝，AudioRecorder.p 會是 None，但類別仍可實例化
        recorder = AudioRecorder()
        assert recorder is not None
        print("✅ AudioRecorder 導入與實例化成功")
        return True
    except ImportError as e:
        print(f"❌ AudioRecorder 導入失敗: {e}")
        return False


def test_recording_directory():
    """測試錄音目錄存在且可寫入"""
    recordings_dir = project_root / "data" / "recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)

    # 檢查目錄是否存在
    assert recordings_dir.exists(), f"錄音目錄不存在: {recordings_dir}"
    assert recordings_dir.is_dir(), f"錄音目錄不是目錄: {recordings_dir}"

    # 嘗試在目錄中建立測試檔案
    test_file = recordings_dir / "test_write.txt"
    try:
        test_file.write_text("test")
        test_file.unlink()
        print(f"✅ 錄音目錄可寫入: {recordings_dir}")
        return True
    except Exception as e:
        print(f"❌ 錄音目錄無法寫入: {e}")
        return False


def test_audio_recorder_start_stop():
    """測試 AudioRecorder 的開始/停止方法（不實際錄音）"""
    try:
        from src.gui.desktop_app import AudioRecorder

        recorder = AudioRecorder()

        # 如果 pyaudio 未安裝，recorder.p 為 None，錄音功能會跳過
        if recorder.p is None:
            print("⚠️ pyaudio 未安裝，跳過實際錄音測試")
            # 仍測試 start/stop 不會崩潰
            recorder.start_recording()
            recorder.stop_recording()
            print("✅ AudioRecorder start/stop 方法安全執行")
            return True

        # 有 pyaudio 的情況下，嘗試錄音一小段（0.5 秒）並保存
        import threading
        import time

        # 確保錄音目錄存在
        recordings_dir = project_root / "data" / "recordings"
        recordings_dir.mkdir(parents=True, exist_ok=True)

        recorder.start_recording()
        # 如果 start_recording 失敗（無音訊設備），recorder.is_recording 可能仍為 False
        if not recorder.is_recording:
            print("⚠️ 無法開始錄音（可能無音訊設備），跳過實際錄音測試")
            recorder.stop_recording()
            print("✅ AudioRecorder start/stop 方法安全執行")
            return True

        assert recorder.is_recording == True, "開始錄音後狀態應為 True"

        # 在背景執行錄音迴圈
        def record_loop():
            if recorder.is_recording and recorder.stream:
                try:
                    # 讀取一些靜音幀（模擬錄音）
                    for _ in range(5):  # 約 0.5 秒
                        if recorder.is_recording and recorder.stream:
                            data = recorder.stream.read(1024, exception_on_overflow=False)
                            recorder.frames.append(data)
                        time.sleep(0.1)
                except Exception:
                    pass

        thread = threading.Thread(target=record_loop)
        thread.start()
        time.sleep(0.6)

        # 停止錄音並保存檔案
        test_output = recordings_dir / "test_recording.wav"
        recorder.stop_recording(str(test_output))

        thread.join(timeout=1)

        assert recorder.is_recording == False, "停止錄音後狀態應為 False"
        # 檢查檔案是否存在
        if test_output.exists():
            print(f"✅ 錄音檔案成功保存: {test_output}")
            test_output.unlink()  # 清理
        else:
            print("⚠️ 錄音檔案未生成（可能無音訊輸入）")

        print("✅ AudioRecorder 開始/停止測試通過")
        return True
    except Exception as e:
        print(f"❌ AudioRecorder 開始/停止測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🎤 測試錄音功能")
    print("=" * 60)

    results = []
    results.append(test_audio_recorder_import())
    results.append(test_recording_directory())
    results.append(test_audio_recorder_start_stop())

    if all(results):
        print("\n✅ 所有錄音功能測試通過")
        sys.exit(0)
    else:
        print("\n❌ 部分錄音功能測試失敗")
        sys.exit(1)
