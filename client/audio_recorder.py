"""語音錄製模組（PyAudio / 分段落地串流）

Phase 31 (D-31-01, D-31-19, D-31-21, D-31-22, D-31-24):
- 邊錄邊落地：每讀到一批 frames 即寫入 chunk_{seq:06d}.pcm.part 並 flush
- 定長切段：每滿 frames_per_segment（預設 20 秒，15–30 秒夾取）封段為 chunk_{seq:06d}.wav
- 封段回呼：觸發 on_segment(seq, wav_path)，例外隔離不中斷錄音
- 崩潰恢復：recover_partial 將未封段之 .pcm.part 轉為完整 WAV
- 舊介面相容：start() / stop() 自動建立臨時子目錄並串接為單一 WAV
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
import threading
import uuid
import wave
from datetime import datetime
from typing import Any, Callable, List, Optional, Union

try:
    import pyaudio  # type: ignore
except ImportError:  # 測試/開發環境可能無 PyAudio
    pyaudio = None  # type: ignore

logger = logging.getLogger(__name__)


def pcm_sha256(paths: list[Union[Path, str]]) -> str:
    """依契約 §2 audio_sha256 計算所有分段 WAV 原始 PCM 資料之 SHA-256。"""
    hasher = hashlib.sha256()
    for p in paths:
        path = Path(p)
        with wave.open(str(path), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            hasher.update(frames)
    return hasher.hexdigest()


def concat_segments(cycle_dir: Union[Path, str], out_path: Union[Path, str]) -> Path:
    """依 seq 順序將 cycle_dir 內的所有 chunk_*.wav 串接為單一 WAV 檔案。"""
    c_dir = Path(cycle_dir)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    wav_files = sorted(
        c_dir.glob("chunk_*.wav"),
        key=lambda p: int(p.stem.split("_")[1]) if "_" in p.stem and p.stem.split("_")[1].isdigit() else 0,
    )

    if not wav_files:
        with wave.open(str(out), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"")
        return out

    # 以第一個檔案之格式為準
    with wave.open(str(wav_files[0]), "rb") as first_wf:
        nchannels = first_wf.getnchannels()
        sampwidth = first_wf.getsampwidth()
        framerate = first_wf.getframerate()

    with wave.open(str(out), "wb") as out_wf:
        out_wf.setnchannels(nchannels)
        out_wf.setsampwidth(sampwidth)
        out_wf.setframerate(framerate)
        for wav_path in wav_files:
            with wave.open(str(wav_path), "rb") as in_wf:
                out_wf.writeframes(in_wf.readframes(in_wf.getnframes()))

    with open(out, "rb") as f:
        os.fsync(f.fileno())

    return out


def recover_partial(cycle_dir: Union[Path, str]) -> list[int]:
    """將殘留的 chunk_*.pcm.part 轉為 chunk_*.wav，空檔直接刪除。回傳已恢復之 seq 清單。"""
    c_dir = Path(cycle_dir)
    part_files = sorted(c_dir.glob("chunk_*.pcm.part"))
    recovered: list[int] = []

    for part_file in part_files:
        try:
            stem_parts = part_file.stem.split(".")  # chunk_000000.pcm
            seq_part = stem_parts[0].split("_")[1]
            seq = int(seq_part)
        except (IndexError, ValueError):
            seq = 0

        raw_data = part_file.read_bytes()
        if not raw_data:
            part_file.unlink(missing_ok=True)
            continue

        wav_tmp = c_dir / f"chunk_{seq:06d}.wav.tmp"
        wav_target = c_dir / f"chunk_{seq:06d}.wav"

        with wave.open(str(wav_tmp), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(raw_data)

        with open(wav_tmp, "rb") as f:
            os.fsync(f.fileno())

        os.replace(wav_tmp, wav_target)
        part_file.unlink(missing_ok=True)
        recovered.append(seq)
        logger.info("Recovered partial segment chunk_%06d.wav (%d bytes)", seq, len(raw_data))

    return recovered


class AudioRecorder:
    """以 PyAudio 錄製 16 kHz 單聲道 WAV，支援邊錄邊落地與定長切段。"""

    CHUNK = 1024
    CHANNELS = 1  # mono
    RATE = 16000  # 16 kHz

    def __init__(
        self,
        output_dir: Union[str, Path],
        *,
        segment_seconds: float = 20.0,
        frames_per_segment: Optional[int] = None,
        stream_factory: Optional[Callable[[], Any]] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # segment_seconds 夾在 15.0–30.0 (D-31-19)
        self.segment_seconds = max(15.0, min(30.0, float(segment_seconds)))
        if frames_per_segment is not None:
            self.frames_per_segment = int(frames_per_segment)
        else:
            self.frames_per_segment = int(self.RATE * self.segment_seconds)

        self.stream_factory = stream_factory

        self.is_recording = False
        # D-31-21: 保留屬性供相容，但長度恆為 0，不得 append 累積 frames
        self.audio_frames: list[bytes] = []
        self.stream = None
        self.audio = None
        self.thread: Optional[threading.Thread] = None
        self._sample_size = 2  # 16-bit PCM 預設

        self.on_start: Optional[Callable[[], None]] = None
        self.on_stop: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_segment: Optional[Callable[[int, str], None]] = None

        self._cycle_mode = False
        self._cycle_dir: Optional[Path] = None
        self._current_seq = 0
        self.last_total_segments = 0
        self._legacy_out_name = ""

    @property
    def _format(self):
        """PyAudio 格式（16-bit PCM）。"""
        if pyaudio is None:
            raise RuntimeError("PyAudio not available")
        return pyaudio.paInt16

    def start_cycle(self, cycle_dir: Union[Path, str]) -> bool:
        """在指定的 cycle_dir 目錄啟動分段錄音。若已有分段，接續最大 seq + 1。"""
        if self.is_recording:
            logger.warning("Already recording, ignoring start_cycle()")
            return False

        c_dir = Path(cycle_dir)
        c_dir.mkdir(parents=True, exist_ok=True)

        # 啟動前先檢查有無殘留 .pcm.part 需恢復
        recover_partial(c_dir)

        # 計算接續 seq
        existing_wavs = c_dir.glob("chunk_*.wav")
        max_seq = -1
        for w in existing_wavs:
            try:
                seq = int(w.stem.split("_")[1])
                if seq > max_seq:
                    max_seq = seq
            except (IndexError, ValueError):
                continue

        self._cycle_mode = True
        self._cycle_dir = c_dir
        self._current_seq = max_seq + 1

        return self._start_stream_and_thread()

    def start(self) -> bool:
        """相容舊介面啟動錄音：於 output_dir 建立臨時子目錄。"""
        if self.is_recording:
            logger.warning("Already recording, ignoring start()")
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = uuid.uuid4().hex[:8]
        sub_dir = self.output_dir / f"audio_{timestamp}_{session_id}"
        sub_dir.mkdir(parents=True, exist_ok=True)

        self._cycle_mode = False
        self._cycle_dir = sub_dir
        self._current_seq = 0
        self._legacy_out_name = f"audio_{timestamp}_{session_id}.wav"

        return self._start_stream_and_thread()

    def _start_stream_and_thread(self) -> bool:
        try:
            if self.stream_factory is not None:
                self.audio = None
                self.stream = self.stream_factory()
                self._sample_size = 2
            else:
                if pyaudio is None:
                    msg = "PyAudio not installed; recording unavailable"
                    logger.error(msg)
                    if self.on_error:
                        self.on_error(msg)
                    return False
                self.audio = pyaudio.PyAudio()
                self._sample_size = self.audio.get_sample_size(self._format)
                self.stream = self.audio.open(
                    format=self._format,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    frames_per_buffer=self.CHUNK,
                )

            self.is_recording = True
            self.thread = threading.Thread(target=self._record_loop, daemon=True)
            self.thread.start()

            logger.info("Recording started @ %d Hz mono (cycle_dir=%s)", self.RATE, self._cycle_dir)
            if self.on_start:
                try:
                    self.on_start()
                except Exception:  # noqa: BLE001
                    logger.exception("on_start callback raised")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to start recording: %s", exc)
            self.is_recording = False
            if self.on_error:
                self.on_error(str(exc))
            return False

    def _record_loop(self) -> None:
        """背景錄製迴圈：邊錄邊寫入磁碟，定長原子封段。"""
        assert self._cycle_dir is not None
        current_part_file = self._cycle_dir / f"chunk_{self._current_seq:06d}.pcm.part"
        part_handle = None
        frames_in_curr_segment = 0

        try:
            part_handle = open(current_part_file, "ab")
            while self.is_recording:
                data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                if not data:
                    continue

                try:
                    part_handle.write(data)
                    part_handle.flush()
                    os.fsync(part_handle.fileno())
                except OSError as exc:
                    logger.exception("Disk write error during recording: %s", exc)
                    if self.on_error:
                        self.on_error(f"Disk write error: {exc}")
                    self.is_recording = False
                    break

                frames_in_curr_segment += len(data) // (self.CHANNELS * self._sample_size)

                if frames_in_curr_segment >= self.frames_per_segment:
                    part_handle.close()
                    part_handle = None
                    self._seal_segment(self._current_seq, current_part_file)
                    self._current_seq += 1
                    frames_in_curr_segment = 0
                    current_part_file = self._cycle_dir / f"chunk_{self._current_seq:06d}.pcm.part"
                    part_handle = open(current_part_file, "ab")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Recording loop unexpected error: %s", exc)
            if self.on_error:
                self.on_error(str(exc))
        finally:
            if part_handle is not None:
                try:
                    part_handle.close()
                except Exception:
                    pass

    def _seal_segment(self, seq: int, part_file: Path) -> Optional[Path]:
        """將 .pcm.part 封為 chunk_{seq:06d}.wav 並觸發 on_segment。"""
        if not part_file.exists():
            return None

        raw_pcm = part_file.read_bytes()
        if not raw_pcm:
            try:
                part_file.unlink(missing_ok=True)
            except Exception:
                pass
            return None

        assert self._cycle_dir is not None
        wav_tmp = self._cycle_dir / f"chunk_{seq:06d}.wav.tmp"
        wav_final = self._cycle_dir / f"chunk_{seq:06d}.wav"

        with wave.open(str(wav_tmp), "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self._sample_size)
            wf.setframerate(self.RATE)
            wf.writeframes(raw_pcm)

        with open(wav_tmp, "rb") as f:
            os.fsync(f.fileno())

        os.replace(wav_tmp, wav_final)
        try:
            part_file.unlink(missing_ok=True)
        except Exception:
            pass

        logger.info("Segment %06d sealed: %s (%d bytes)", seq, wav_final.name, len(raw_pcm))

        if self.on_segment:
            try:
                self.on_segment(seq, str(wav_final))
            except Exception as exc:  # noqa: BLE001
                logger.exception("on_segment callback raised for seq %d: %s", seq, exc)
                if self.on_error:
                    self.on_error(f"on_segment error (seq {seq}): {exc}")

        return wav_final

    def stop(self) -> Optional[str]:
        """停止錄製並返回成果路徑。

        cycle 模式：封最後一段，設定 last_total_segments，回傳 cycle_dir 路徑。
        舊模式：串接各分段產生單一 WAV 檔回傳。
        """
        if not self.is_recording:
            logger.warning("Not currently recording")
            return None

        self.is_recording = False

        if self.thread is not None:
            self.thread.join(timeout=2.0)
            self.thread = None

        try:
            if self.stream is not None:
                try:
                    self.stream.stop_stream()
                except Exception:
                    pass
                try:
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None

            if self.audio is not None:
                try:
                    self.audio.terminate()
                except Exception:
                    pass
                self.audio = None

            # 封存最後一段殘留的 .pcm.part
            if self._cycle_dir is not None:
                last_part = self._cycle_dir / f"chunk_{self._current_seq:06d}.pcm.part"
                if last_part.exists():
                    self._seal_segment(self._current_seq, last_part)

                wavs = sorted(self._cycle_dir.glob("chunk_*.wav"))
                self.last_total_segments = len(wavs)

                if self._cycle_mode:
                    result_path = str(self._cycle_dir)
                    if self.on_stop:
                        try:
                            self.on_stop(result_path)
                        except Exception:
                            logger.exception("on_stop callback raised")
                    return result_path

                # 舊模式：串接為單一 WAV
                out_wav = self.output_dir / self._legacy_out_name
                concat_segments(self._cycle_dir, out_wav)
                logger.info("Legacy recording saved: %s (%d segments)", out_wav, self.last_total_segments)
                if self.on_stop:
                    try:
                        self.on_stop(str(out_wav))
                    except Exception:
                        logger.exception("on_stop callback raised")
                return str(out_wav)

            return None
        except Exception as exc:  # noqa: BLE001
            logger.exception("Save/stop error: %s", exc)
            if self.on_error:
                self.on_error(str(exc))
            return None
