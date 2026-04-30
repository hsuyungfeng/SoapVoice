"""螢幕截圖模組

職責：
- 擷取主螢幕全螢幕影像
- 保存為 JPEG（quality=85，optimize=True，平衡檔案大小與可辨識度）
- Windows: 優先使用 PIL.ImageGrab（速度快、無 dependency 衝突）
- 其他平台: fallback 至 mss（pyproject 已含）

使用：
    >>> cap = ScreenshotCapture("./cache")
    >>> path = cap.capture()  # 回傳 .jpg 路徑或 None
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageGrab  # type: ignore
except ImportError:  # 測試環境可能無 Pillow（不太可能，pyproject 含 pillow）
    Image = None  # type: ignore
    ImageGrab = None  # type: ignore

try:
    import mss  # type: ignore
except ImportError:
    mss = None  # type: ignore

logger = logging.getLogger(__name__)


class ScreenshotCapture:
    """擷取螢幕並保存為 JPEG。

    JPEG 品質 85 / optimize=True：
    - 1080p 全螢幕 ≈ 200-400 KB（夠壓縮、肉眼幾乎無損）
    - 對應伺服器端 10 MB 上限尚有 25× 餘裕
    """

    def __init__(self, output_dir: str, jpeg_quality: int = 85):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.jpeg_quality = jpeg_quality

    def capture(self) -> Optional[str]:
        """擷取螢幕並保存。

        Returns:
            JPEG 完整路徑，失敗時 None。
        """
        try:
            img = self._grab_image()
            if img is None:
                return None

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = uuid.uuid4().hex[:8]
            filename = f"screenshot_{timestamp}_{session_id}.jpg"
            filepath = self.output_dir / filename

            # JPEG 不支援 alpha，需轉 RGB
            if hasattr(img, "mode") and img.mode != "RGB":
                img = img.convert("RGB")

            img.save(str(filepath), "JPEG", quality=self.jpeg_quality, optimize=True)
            logger.info("Screenshot saved: %s", filepath)
            return str(filepath)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Screenshot capture failed: %s", exc)
            return None

    def _grab_image(self):
        """選擇可用的後端擷取影像。"""
        # 1. 優先 PIL.ImageGrab（Windows / macOS 原生最快）
        if ImageGrab is not None:
            try:
                return ImageGrab.grab()
            except Exception as exc:  # noqa: BLE001 — Linux 無 ImageGrab，fallback
                logger.warning("ImageGrab failed (will try mss): %s", exc)

        # 2. fallback: mss（跨平台）
        if mss is not None and Image is not None:
            try:
                with mss.mss() as screenshotter:
                    if not screenshotter.monitors or len(screenshotter.monitors) < 2:
                        logger.error("mss reports no monitors available")
                        return None
                    monitor = screenshotter.monitors[1]  # [0] 是全部螢幕的 union
                    raw = screenshotter.grab(monitor)
                    return Image.frombytes("RGB", raw.size, raw.rgb)
            except Exception as exc:  # noqa: BLE001
                logger.exception("mss capture failed: %s", exc)
                return None

        logger.error("No screenshot backend available (neither PIL.ImageGrab nor mss)")
        return None
