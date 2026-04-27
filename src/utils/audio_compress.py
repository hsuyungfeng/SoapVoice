"""
音訊壓縮工具（Phase 11-01）

提供 WAV → Opus 32kbps 編碼功能，配合 LAN 客戶端上傳節省頻寬與儲存。

設計考量：
- 使用系統 ffmpeg（含 libopus）執行壓縮，避免 Python-side opus binding（不一致的安裝體驗）
- ffmpeg 不可用時 graceful degradation：記 warning 並回傳原始 bytes
- 全程透過 subprocess + 暫存檔操作，避免 ffmpeg-python 的相依問題
- 透過 stdin/stdout pipe 處理 bytes，不污染 cwd

Opus 編碼選擇：
- 32 kbps：Opus 的「broad voice」品質，相對 16kHz 16-bit PCM (256 kbps) 約 8-10x 壓縮
- VBR：保持音質穩定，犧牲少量壓縮比
- application=voip：針對人聲優化（提升 SOAP 轉錄品質）

註：此模組於 LAN 上傳前**伺服器側**執行第二次壓縮（即使客戶端已壓縮，也統一格式）。
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ── ffmpeg 可用性檢查 ─────────────────────────────────────────────


def _ffmpeg_available() -> bool:
    """檢查 ffmpeg 是否在 PATH 中可用"""
    return shutil.which("ffmpeg") is not None


def is_compression_available() -> bool:
    """公開 API：客戶端可呼叫以決定是否需要 client-side fallback"""
    return _ffmpeg_available()


# ── 主壓縮函式 ────────────────────────────────────────────────


def compress_audio_to_opus(
    input_audio: bytes,
    target_kbps: int = 32,
    input_ext: str = ".wav",
) -> bytes:
    """將音訊 bytes 壓縮為 Opus 編碼（容器：.opus / Ogg）

    使用 ffmpeg 執行轉碼，目標 bitrate 預設 32kbps（VoIP 級人聲品質，~10:1 壓縮）。
    若 ffmpeg 不可用或執行失敗，記 warning 並回傳原始 bytes（graceful degradation）。

    Args:
        input_audio: 輸入音訊 bytes（WAV / MP3 / M4A / FLAC）
        target_kbps: 目標 bitrate（預設 32 kbps）
        input_ext: 輸入副檔名（含 dot，例如 '.wav'），ffmpeg 用於格式偵測

    Returns:
        Opus 編碼 bytes（成功）或原始 input_audio（fallback）

    Raises:
        ValueError — input_audio 為空或 target_kbps 不合法
    """
    if not input_audio:
        raise ValueError("input_audio 不可為空")
    if target_kbps <= 0 or target_kbps > 510:
        # Opus 規格限制：6-510 kbps
        raise ValueError(f"target_kbps={target_kbps} 超出 Opus 範圍 (6-510)")

    if not _ffmpeg_available():
        logger.warning("ffmpeg 不可用，跳過 Opus 壓縮（fallback 至原始 bytes）")
        return input_audio

    # 透過暫存檔操作（ffmpeg pipe 對部分容器不穩定）
    with tempfile.NamedTemporaryFile(suffix=input_ext, delete=False) as in_f:
        in_path = Path(in_f.name)
        in_f.write(input_audio)

    out_path = in_path.with_suffix(".opus")

    try:
        cmd = [
            "ffmpeg",
            "-y",  # 覆寫輸出
            "-loglevel", "error",
            "-i", str(in_path),
            "-c:a", "libopus",
            "-b:a", f"{target_kbps}k",
            "-vbr", "on",
            "-application", "voip",  # 針對人聲優化
            "-ac", "1",  # 強制單聲道（醫療對話無需立體聲）
            "-ar", "16000",  # 16kHz 取樣率（與 ASR 相容）
            str(out_path),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=60,  # 1 分鐘超時保護（threat_model T-11-05）
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="ignore")[:500]
            logger.warning(f"ffmpeg 壓縮失敗（returncode={result.returncode}）：{stderr}")
            return input_audio
        if not out_path.exists() or out_path.stat().st_size == 0:
            logger.warning("ffmpeg 輸出檔不存在或為空")
            return input_audio
        return out_path.read_bytes()
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg 壓縮超時（>60s）")
        return input_audio
    except Exception as e:
        logger.warning(f"Opus 壓縮例外：{e}")
        return input_audio
    finally:
        # 清理暫存檔
        try:
            in_path.unlink(missing_ok=True)
            out_path.unlink(missing_ok=True)
        except Exception:
            pass


def get_audio_compression_ratio(original_size: int, compressed_size: int) -> float:
    """計算壓縮比（原始 / 壓縮後）

    Args:
        original_size: 原始 bytes
        compressed_size: 壓縮後 bytes

    Returns:
        壓縮倍數（例如 10.0 表示 10:1）；若 compressed_size 為 0 則回傳 0.0
    """
    if compressed_size <= 0:
        return 0.0
    return float(original_size) / float(compressed_size)


def generate_test_wav_bytes(
    duration_sec: float = 2.0,
    sample_rate: int = 16000,
    frequency: float = 440.0,
) -> bytes:
    """產生測試用 WAV bytes（440Hz 純音）

    供測試 fixture 使用，避免依賴外部音檔。

    Args:
        duration_sec: 音訊長度（秒）
        sample_rate: 取樣率（預設 16kHz，與 ASR 對齊）
        frequency: 正弦波頻率（Hz）

    Returns:
        WAV 檔 bytes（PCM16 單聲道）
    """
    import io
    import math
    import struct
    import wave

    n_samples = int(duration_sec * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        # 用 list+struct 產生 sine wave；振幅 16384 (50% 滿格)
        amp = 16384
        frames = bytearray()
        for i in range(n_samples):
            sample = int(amp * math.sin(2 * math.pi * frequency * i / sample_rate))
            frames.extend(struct.pack("<h", sample))
        wav.writeframes(bytes(frames))
    return buf.getvalue()


__all__ = [
    "compress_audio_to_opus",
    "get_audio_compression_ratio",
    "is_compression_available",
    "generate_test_wav_bytes",
]
