"""
SoapVoice 完整整合模組
支援 CPU 和 GPU 模式切換
"""

import time
from typing import Dict, Any, Optional
from enum import Enum
from faster_whisper import WhisperModel
import requests


class ComputeMode(Enum):
    CPU = "cpu"
    GPU = "gpu"


class SoapVoiceEngine:
    """整合 Whisper + Ollama 的 SOAP 生成引擎"""

    def __init__(
        self,
        compute_mode: ComputeMode = ComputeMode.GPU,
        whisper_model: str = "medium",
        llm_model: str = "qwen2.5:14b",
        ollama_url: str = "http://localhost:11434",
    ):
        self.compute_mode = compute_mode
        self.whisper_model = whisper_model
        self.llm_model = llm_model
        self.ollama_url = ollama_url
        self._whisper = None

    def _init_whisper(self):
        """初始化 Whisper 模型"""
        if self._whisper is None:
            device = "cuda" if self.compute_mode == ComputeMode.GPU else "cpu"
            compute_type = "int8_float16" if self.compute_mode == ComputeMode.GPU else "int8"
            print(f"初始化 Whisper: {device} / {compute_type}")
            self._whisper = WhisperModel(
                self.whisper_model,
                device=device,
                compute_type=compute_type,
            )

    def transcribe(self, audio_path: str, language: str = "zh") -> Dict[str, Any]:
        """語音轉文字"""
        self._init_whisper()

        start = time.time()
        segments, info = self._whisper.transcribe(audio_path, language=language)

        transcript = ""
        for segment in segments:
            transcript += segment.text

        return {
            "transcript": transcript,
            "language": info.language,
            "language_probability": info.language_probability,
            "time": time.time() - start,
        }

    def generate_soap(
        self,
        transcript: str,
        output_lang: str = "en",
        include_transcript: bool = True,
    ) -> Dict[str, Any]:
        """生成 SOAP 病歷"""

        if output_lang == "en":
            prompt = f"""Provide the output in this exact format:

## 中文逐字稿:
{transcript}

## English SOAP Note:
S - Subjective:
[English translation of patient complaints]

O - Objective:
[Physical examination findings]

A - Assessment:
[Diagnosis in English]

P - Plan:
[Treatment plan in English]
"""
        else:
            prompt = f"""請將以下醫療對話轉換為 SOAP 病歷格式：

{transcript}
"""

        start = time.time()
        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": self.llm_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 512},
            },
        )

        result = response.json()

        return {
            "soap": result.get("response", "No response"),
            "model": self.llm_model,
            "time": time.time() - start,
        }

    def process(
        self,
        audio_path: str,
        output_lang: str = "en",
        include_transcript: bool = True,
    ) -> Dict[str, Any]:
        """完整流程：轉錄 + SOAP 生成"""

        # Step 1: 轉錄
        transcribe_result = self.transcribe(audio_path)

        # Step 2: SOAP 生成
        soap_result = self.generate_soap(
            transcribe_result["transcript"],
            output_lang=output_lang,
            include_transcript=include_transcript,
        )

        return {
            "transcript": transcribe_result["transcript"],
            "transcribe_time": transcribe_result["time"],
            "soap": soap_result["soap"],
            "soap_time": soap_result["time"],
            "total_time": transcribe_result["time"] + soap_result["time"],
            "compute_mode": self.compute_mode.value,
            "whisper_model": self.whisper_model,
            "llm_model": self.llm_model,
        }


def cpu_mode_demo():
    """CPU 模式演示"""
    print("=" * 60)
    print("🔵 CPU 模式演示")
    print("=" * 60)

    engine = SoapVoiceEngine(
        compute_mode=ComputeMode.CPU,
        whisper_model="medium",
        llm_model="qwen2.5:14b",
    )

    result = engine.process(
        "tests/fixtures/sample_zh.wav",
        output_lang="en",
    )

    return result


def gpu_mode_demo():
    """GPU 模式演示"""
    print("=" * 60)
    print("🟢 GPU 模式演示")
    print("=" * 60)

    engine = SoapVoiceEngine(
        compute_mode=ComputeMode.GPU,
        whisper_model="medium",
        llm_model="qwen2.5:14b",
    )

    result = engine.process(
        "tests/fixtures/sample_zh.wav",
        output_lang="en",
    )

    return result


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "both"

    if mode == "cpu":
        result = cpu_mode_demo()
    elif mode == "gpu":
        result = gpu_mode_demo()
    else:
        # 比較兩種模式
        print("\n" + "🔵 CPU 模式測試".center(60, "="))
        cpu_result = cpu_mode_demo()

        print("\n" + "🟢 GPU 模式測試".center(60, "="))
        gpu_result = gpu_mode_demo()

        print("\n" + "📊 效能比較".center(60, "="))
        print(f"CPU 模式總耗時: {cpu_result['total_time']:.2f}s")
        print(f"GPU 模式總耗時: {gpu_result['total_time']:.2f}s")

        print("\n" + "📝 輸出範例".center(60, "="))
        print(cpu_result["soap"])
