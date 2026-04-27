"""SoapVoice LAN 瘦客戶端套件

模組：
- lan_config: 客戶端設定
- http_client: 非同步 HTTP 客戶端（httpx + tenacity 重試）
- lan_client: LAN 客戶端核心邏輯（健康檢查、上傳、本機暫存）
- audio_recorder: 語音錄製（PyAudio）
- screenshot_capture: 螢幕截圖（PIL/mss）
- gui: Tkinter GUI 元件
- main: 應用程式入口

入口點：執行 `python -m client.main` 或 `from client.main import main`。
"""

__version__ = "1.1.0"
