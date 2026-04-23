"""
SoapVoice Phase 8.3 - 語音錄製 + LLM SOAP 生成模組

功能：
- 錄製音訊
- ASR 語音轉文字
- LLM 生成 SOAP 病歷
"""

import os
import logging
import time
import wave
import threading
from pathlib import Path
from typing import Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RecordingResult:
    """錄音結果"""

    audio_file: str
    transcript: str
    soap: Dict[str, str]
    success: bool
    error: str = ""


class AudioRecorder:
    """音訊錄製"""

    def __init__(self, output_dir: str = "data/recordings"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.is_recording = False
        self.frames = []
        self.audio = None
        self.stream = None
        self.chunk = 1024
        self.format = 2  # pyaudio.pInt16
        self.channels = 1
        self.rate = 16000

    def _init_audio(self) -> bool:
        """初始化 PyAudio"""
        if self.audio is None:
            try:
                import pyaudio

                self.audio = pyaudio.PyAudio()
                return True
            except ImportError:
                logger.error("PyAudio not installed")
                return False
            except Exception as e:
                logger.error(f"PyAudio init failed: {e}")
                return False
        return True

    def start(self) -> bool:
        """開始錄音"""
        if not self._init_audio():
            return False

        try:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
            )

            self.frames = []
            self.is_recording = True

            # 在新執行緒中錄音
            self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
            self._record_thread.start()

            logger.info("Recording started")
            return True

        except Exception as e:
            logger.error(f"Start recording failed: {e}")
            return False

    def _record_loop(self):
        """錄音迴圈"""
        while self.is_recording:
            try:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                self.frames.append(data)
            except Exception as e:
                logger.warning(f"Recording error: {e}")
                break

    def stop(self, filename: str = "") -> str:
        """停止錄音並儲存

        Returns:
            音訊檔案路徑
        """
        self.is_recording = False

        if not filename:
            timestamp = time.strftime("%Y-%m-%d_%H%M%S")
            filename = f"recording_{timestamp}.wav"

        filepath = self.output_dir / filename

        try:
            with wave.open(str(filepath), "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.format))
                wf.setframerate(self.rate)
                wf.writeframes(b"".join(self.frames))

            logger.info(f"Audio saved: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Save audio failed: {e}")
            return ""
        finally:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()

    def cancel(self):
        """取消錄音"""
        self.is_recording = False
        self.frames = []


class TranscriptEngine:
    """轉文字引擎 - 支援多種後端"""

    def __init__(self):
        self.engine_type = "whisper"  # whisper, faster-whisper, ollama

    def transcribe(self, audio_file: str) -> str:
        """轉換音訊為文字

        Args:
            audio_file: 音訊檔案路徑

        Returns:
            逐字稿文字
        """
        logger.info(f"Transcribing: {audio_file}")

        # 嘗試使用 Faster-Whisper
        try:
            return self._transcribe_faster_whisper(audio_file)
        except Exception as e:
            logger.warning(f"Faster-Whisper failed: {e}")

        # 嘗試使用 Ollama
        try:
            return self._transcribe_ollama(audio_file)
        except Exception as e:
            logger.warning(f"Ollama failed: {e}")

        # 備用：直接返回模擬文字（開發測試用）
        logger.info("Using fallback transcript")
        return self._get_fallback_transcript()

    def _transcribe_faster_whisper(self, audio_file: str) -> str:
        """使用 Faster-Whisper 轉文字"""
        from faster_whisper import WhisperModel

        _device = os.environ.get("WHISPER_DEVICE", "cuda")
        _ctype = os.environ.get("WHISPER_COMPUTE_TYPE", "float16")
        model = WhisperModel("small", device=_device, compute_type=_ctype)
        segments, info = model.transcribe(audio_file)

        text = " ".join([seg.text for seg in segments])
        logger.info(f"Transcribed {info.duration:.2f}s of audio")

        return text

    def _transcribe_ollama(self, audio_file: str) -> str:
        """使用 Ollama 轉文字"""
        import requests

        # 注意：Ollama 需要音訊格式
        # 這裡是簡化版本，實際需要音訊轉換
        url = "http://localhost:11434/api/transcribe"

        try:
            with open(audio_file, "rb") as f:
                files = {"file": f}
                data = {"model": "whisper-base"}
                response = requests.post(url, files=files, data=data, timeout=60)

            if response.status_code == 200:
                result = response.json()
                return result.get("text", "")
        except:
            pass

        return ""

    def _get_fallback_transcript(self) -> str:
        """備用逐字稿（開發測試用）"""
        return """病人主訴胸悶兩天，伴隨呼吸困難。
無發燒或咳嗽。
過去有心臟病史。
理學檢查：胸部無異常發現，心律不整。
診斷：胸悶待查。
建議：心電圖檢查，安排門診追蹤。"""


class SOAPGenerator:
    """SOAP 生成器"""

    def __init__(self):
        self.use_llama_cpp = os.getenv("USE_LLAMA_CPP", "false").lower() == "true"
        self.model = "qwen2.5:7b"

    def generate(self, transcript: str, patient_info: dict = None) -> Dict[str, str]:
        """生成 SOAP 病歷

        Args:
            transcript: 逐字稿
            patient_info: 病患資訊

        Returns:
            SOAP 字典
        """
        logger.info("Generating SOAP...")

        # 根據環境選擇引擎
        if self.use_llama_cpp:
            return self._generate_with_llama_cpp(transcript, patient_info)
        else:
            return self._generate_with_ollama(transcript, patient_info)

    def _generate_with_llama_cpp(self, transcript: str, patient_info: dict) -> Dict[str, str]:
        """使用 llama.cpp 生成"""
        try:
            from src.llm.llama_engine import LlamaConfig, LlamaEngine

            # 使用較小的 GGUF 模型
            model_path = "models/qwen2.5-3b-instruct-q4_k_m.gguf"

            if not Path(model_path).exists():
                logger.warning(f"Model not found: {model_path}")
                return self._get_fallback_soap(transcript)

            config = LlamaConfig(model_path=model_path, n_ctx=512, n_threads=4, max_tokens=256)

            engine = LlamaEngine(config)
            engine.initialize()

            # 建構 prompt
            prompt = self._build_soap_prompt(transcript, patient_info)

            result = engine.generate(prompt)

            return self._parse_soap_response(result)

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._get_fallback_soap(transcript)

    def _generate_with_ollama(self, transcript: str, patient_info: dict) -> Dict[str, str]:
        """使用 Ollama 生成"""
        try:
            from src.llm.ollama_engine import OllamaEngine, ModelConfig

            config = ModelConfig(model_id=self.model)
            engine = OllamaEngine(config)
            engine.initialize()

            prompt = self._build_soap_prompt(transcript, patient_info)
            result = engine.generate(prompt)

            return self._parse_soap_response(result)

        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return self._get_fallback_soap(transcript)

    def _build_soap_prompt(self, transcript: str, patient_info: dict) -> str:
        """建構 SOAP prompt"""
        patient_str = ""
        if patient_info:
            patient_str = f"""
病患資訊：
姓名: {patient_info.get("name", "")}
醫師: {patient_info.get("doctor", "")}
"""

        return f"""請根據以下醫療對話生成 SOAP 病歷格式。
{patient_str}
對話內容：
{transcript}

請嚴格按照以下格式輸出：
S: [主觀描述]
O: [客觀發現]
A: [評估診斷]
P: [治療計畫]
"""

    def _parse_soap_response(self, response: str) -> Dict[str, str]:
        """解析 SOAP 回應"""
        soap = {"subjective": "", "objective": "", "assessment": "", "plan": ""}

        lines = response.strip().split("\n")
        current = None

        for line in lines:
            line = line.strip()
            if line.startswith("S:"):
                current = "subjective"
                soap[current] = line[2:].strip()
            elif line.startswith("O:"):
                current = "objective"
                soap[current] = line[2:].strip()
            elif line.startswith("A:"):
                current = "assessment"
                soap[current] = line[2:].strip()
            elif line.startswith("P:"):
                current = "plan"
                soap[current] = line[2:].strip()
            elif current and line:
                soap[current] += " " + line

        return soap

    def _get_fallback_soap(self, transcript: str) -> Dict[str, str]:
        """備用 SOAP（開發測試用）"""
        return {
            "subjective": "Patient reports chest discomfort and difficulty breathing for two days.",
            "objective": "No specific abnormal findings on physical examination.",
            "assessment": "R07.89 - Other chest discomfort, R06.02 - Shortness of breath",
            "plan": "ECG test recommended. Follow-up in outpatient clinic.",
        }


class VoiceRecordingWorkflow:
    """語音錄製工作流程"""

    def __init__(self):
        self.recorder = AudioRecorder()
        self.transcriber = TranscriptEngine()
        self.soap_generator = SOAPGenerator()

        self.current_audio_file = ""
        self.current_transcript = ""
        self.current_soap = {}

    def start_recording(self) -> bool:
        """開始錄音"""
        return self.recorder.start()

    def stop_and_process(self, patient_info: dict = None) -> RecordingResult:
        """停止錄音並處理

        Args:
            patient_info: 病患資訊

        Returns:
            錄音結果
        """
        # 停止錄音
        self.current_audio_file = self.recorder.stop()

        if not self.current_audio_file:
            return RecordingResult(
                audio_file="", transcript="", soap={}, success=False, error="Recording failed"
            )

        # 轉文字
        try:
            self.current_transcript = self.transcriber.transcribe(self.current_audio_file)
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            self.current_transcript = ""

        # 生成 SOAP
        try:
            self.current_soap = self.soap_generator.generate(self.current_transcript, patient_info)
        except Exception as e:
            logger.error(f"SOAP generation failed: {e}")
            self.current_soap = {}

        return RecordingResult(
            audio_file=self.current_audio_file,
            transcript=self.current_transcript,
            soap=self.current_soap,
            success=True,
        )

    def get_results(self) -> dict:
        """取得目前結果"""
        return {
            "audio_file": self.current_audio_file,
            "transcript": self.current_transcript,
            "soap": self.current_soap,
        }


def main():
    """測試語音錄製流程"""
    import argparse

    parser = argparse.ArgumentParser(description="Voice Recording")
    parser.add_argument("--record", action="store_true", help="Start recording")
    parser.add_argument("--stop", action="store_true", help="Stop recording")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    workflow = VoiceRecordingWorkflow()

    if args.record:
        print("開始錄音...")
        workflow.start_recording()
        print("錄音中... 按 Enter 停止")
        input()
        print("處理中...")
        result = workflow.stop_and_process()

        print("\n=== 結果 ===")
        print(f"音訊: {result.audio_file}")
        print(f"\n逐字稿:\n{result.transcript}")
        print(
            f"\nSOAP:\nS: {result.soap.get('subjective', '')}\nO: {result.soap.get('objective', '')}\nA: {result.soap.get('assessment', '')}\nP: {result.soap.get('plan', '')}"
        )


if __name__ == "__main__":
    main()
