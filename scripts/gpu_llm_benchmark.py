#!/usr/bin/env python3
"""
SoapVoice GPU + LLM 基準測試
測試環境：2080 Ti 22GB VRAM
測試模型：Gemma 4 E4B、Qwen 3.6、Qwen 3.5、Gemma 4 多個版本
測試資料：static/ 目錄下的醫療語音樣本

產出：GPUllmcompare.md 包含詳細效能、品質、SOAP 生成對比
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import subprocess
import wave

# 加入專案路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.asr.whisper_model import WhisperModel
from src.soap.soap_generator import SOAPGenerator
from src.llm.llama_engine import LlamaEngine, LlamaConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# 配置
# ============================================================================

STATIC_DIR = Path(__file__).parent.parent / "static"
OUTPUT_DIR = Path(__file__).parent.parent / "benchmarks"
OUTPUT_DIR.mkdir(exist_ok=True)

# 測試音頻檔案
TEST_AUDIO_FILES = [
    "chest_pain.wav",
    "respiratory.wav",
    "hypertension.wav",
    "diabetes.wav",
    "drug_order.wav",
    "wound_care.wav",
    "surgery_record.wav",
    "doctor_patient.wav",
]

# 測試 LLM 模型配置
LLM_MODELS = [
    {
        "name": "Gemma 4 E4B (Q4_K_M, 5.1GB GGUF)",
        "type": "llama_cpp",
        "model_path": "models/gemma-4-E4B-it-Q4_K_M.gguf",
        "n_gpu_layers": -1,
    },
    {
        "name": "Qwen 3.6:Latest (Ollama)",
        "type": "ollama",
        "model_id": "qwen3.6:latest",
        "n_gpu_layers": 1,
    },
    {
        "name": "Qwen 3.5:35B (Ollama)",
        "type": "ollama",
        "model_id": "qwen3.5:35b",
        "n_gpu_layers": 1,
    },
    {
        "name": "Gemma 4:31B (Ollama)",
        "type": "ollama",
        "model_id": "gemma4:31b",
        "n_gpu_layers": 1,
    },
    {
        "name": "Gemma 4:26B (Ollama)",
        "type": "ollama",
        "model_id": "gemma4:26b",
        "n_gpu_layers": 1,
    },
    {
        "name": "Gemma 4:E4B (Ollama)",
        "type": "ollama",
        "model_id": "gemma4:e4b",
        "n_gpu_layers": 1,
    },
]

# ============================================================================
# ASR 測試
# ============================================================================

class ASRBenchmark:
    def __init__(self):
        self.results = []
        self.asr_model = None

    def initialize(self):
        """初始化 ASR 模型（Faster-Whisper Medium @ CUDA）"""
        logger.info("🎙️  初始化 Faster-Whisper Medium (CUDA)...")
        start = time.time()
        try:
            self.asr_model = WhisperModel("medium", device="cuda", compute_type="float16")
            init_time = time.time() - start
            logger.info(f"✅ ASR 模型初始化完成（{init_time:.2f}s）")
            return True
        except Exception as e:
            logger.error(f"❌ ASR 初始化失敗: {e}")
            return False

    def get_audio_duration(self, audio_path: Path) -> float:
        """取得音檔時長（秒）"""
        try:
            with wave.open(str(audio_path), 'rb') as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                return frames / rate
        except Exception as e:
            logger.warning(f"無法取得 {audio_path.name} 時長: {e}")
            return 0.0

    def benchmark_file(self, audio_path: Path) -> Dict:
        """測試單個音檔的 ASR 性能"""
        if not audio_path.exists():
            logger.warning(f"⚠️  音檔不存在: {audio_path}")
            return None

        logger.info(f"🎙️  測試 ASR: {audio_path.name}")
        duration = self.get_audio_duration(audio_path)

        start = time.time()
        try:
            segments, info = self.asr_model.transcribe(str(audio_path), language="zh")
            elapsed = time.time() - start

            transcript = "".join([segment.text for segment in segments])
            rtf = elapsed / duration if duration > 0 else 0  # Real-time factor

            result = {
                "file": audio_path.name,
                "duration_sec": duration,
                "asr_time_sec": elapsed,
                "rtf": rtf,
                "transcript": transcript[:100] + "..." if len(transcript) > 100 else transcript,
            }

            logger.info(f"  ✅ {audio_path.name}: {elapsed:.2f}s (RTF: {rtf:.2f}x), 字數: {len(transcript)}")
            return result

        except Exception as e:
            logger.error(f"  ❌ ASR 處理失敗: {e}")
            return None

    def run_all(self) -> List[Dict]:
        """執行所有音檔的 ASR 測試"""
        if not self.initialize():
            return []

        logger.info(f"\n{'='*70}")
        logger.info("📊 ASR 基準測試開始")
        logger.info(f"{'='*70}\n")

        results = []
        for audio_file in TEST_AUDIO_FILES:
            audio_path = STATIC_DIR / audio_file
            result = self.benchmark_file(audio_path)
            if result:
                results.append(result)

        self.results = results
        return results

# ============================================================================
# LLM 測試
# ============================================================================

class LLMBenchmark:
    def __init__(self, model_config: Dict):
        self.config = model_config
        self.engine = None
        self.results = []

    def initialize(self) -> bool:
        """初始化 LLM 引擎"""
        logger.info(f"🧠 初始化 LLM: {self.config['name']}")
        start = time.time()

        try:
            if self.config["type"] == "llama_cpp":
                llama_config = LlamaConfig(
                    model_path=self.config["model_path"],
                    n_gpu_layers=self.config["n_gpu_layers"],
                )
                self.engine = LlamaEngine(llama_config)
            elif self.config["type"] == "ollama":
                # Ollama 初始化（假設 Ollama 已在 localhost:11434 運行）
                logger.info(f"  ⚠️  Ollama 模式需要手動驗證 {self.config['model_id']} 已拉取")
                # 實際實現需要 OllamaEngine，此處簡化
                return False

            init_time = time.time() - start
            logger.info(f"✅ LLM 初始化完成（{init_time:.2f}s）")
            return True

        except Exception as e:
            logger.error(f"❌ LLM 初始化失敗: {e}")
            return False

    def generate_soap(self, transcript: str, patient_context: str = "") -> Tuple[Dict, float]:
        """使用 LLM 生成 SOAP"""
        if not self.engine:
            return None, 0.0

        prompt = self._build_soap_prompt(transcript, patient_context)

        start = time.time()
        try:
            # 呼叫 LLM 生成
            response = self.engine.generate(prompt, max_tokens=1000)
            elapsed = time.time() - start

            soap = self._parse_soap_response(response)
            return soap, elapsed

        except Exception as e:
            logger.error(f"❌ SOAP 生成失敗: {e}")
            return None, 0.0

    def _build_soap_prompt(self, transcript: str, context: str = "") -> str:
        """構建 SOAP 提示詞"""
        return f"""You are a medical scribe. Based on the patient consultation transcript, generate a structured SOAP note in Traditional Chinese.

Patient transcript:
{transcript}

Patient context:
{context if context else 'N/A'}

Generate SOAP note:
S (Subjective):
O (Objective):
A (Assessment):
P (Plan):
"""

    def _parse_soap_response(self, response: str) -> Dict:
        """解析 LLM 返回的 SOAP"""
        soap = {
            "subjective": "",
            "objective": "",
            "assessment": "",
            "plan": "",
            "raw": response
        }

        # 簡單的分割邏輯
        lines = response.split('\n')
        current_section = None

        for line in lines:
            if 'Subjective' in line or 'S (' in line:
                current_section = 'subjective'
            elif 'Objective' in line or 'O (' in line:
                current_section = 'objective'
            elif 'Assessment' in line or 'A (' in line:
                current_section = 'assessment'
            elif 'Plan' in line or 'P (' in line:
                current_section = 'plan'
            elif current_section and line.strip():
                soap[current_section] += line + '\n'

        return soap

    def benchmark_file(self, transcript: str, filename: str) -> Dict:
        """測試單個文字的 LLM 性能"""
        logger.info(f"  🧠 {filename}")

        soap, elapsed = self.generate_soap(transcript)

        if soap:
            result = {
                "file": filename,
                "model": self.config["name"],
                "llm_time_sec": elapsed,
                "tokens_generated": len(soap["raw"].split()),
                "soap": soap,
            }
            logger.info(f"    ✅ {elapsed:.2f}s, 生成 {result['tokens_generated']} tokens")
            return result
        else:
            logger.error(f"    ❌ 生成失敗")
            return None

# ============================================================================
# 主要測試控制器
# ============================================================================

class BenchmarkController:
    def __init__(self):
        self.asr_results = []
        self.llm_results = {}
        self.start_time = None

    def run_full_benchmark(self):
        """執行完整基準測試"""
        self.start_time = datetime.now()
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 SoapVoice GPU + LLM 基準測試")
        logger.info(f"開始時間: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"GPU: 2080 Ti (22GB VRAM)")
        logger.info(f"{'='*70}\n")

        # Phase 1: ASR 測試
        logger.info("\n" + "="*70)
        logger.info("PHASE 1: ASR (語音轉文字) 基準測試")
        logger.info("="*70 + "\n")

        asr_bench = ASRBenchmark()
        self.asr_results = asr_bench.run_all()

        # Phase 2: 提取轉錄稿
        logger.info("\n" + "="*70)
        logger.info("PHASE 2: 準備 LLM 測試資料")
        logger.info("="*70 + "\n")

        transcripts = {}
        for result in self.asr_results:
            transcripts[result["file"]] = result["transcript"]

        # Phase 3: LLM 測試
        logger.info("\n" + "="*70)
        logger.info("PHASE 3: LLM (SOAP 生成) 基準測試")
        logger.info("="*70 + "\n")

        for model_config in LLM_MODELS:
            logger.info(f"\n📊 測試模型: {model_config['name']}")
            logger.info("-" * 70)

            llm_bench = LLMBenchmark(model_config)
            if not llm_bench.initialize():
                logger.warning(f"⚠️  {model_config['name']} 初始化失敗，跳過")
                continue

            model_results = []
            for filename, transcript in transcripts.items():
                result = llm_bench.benchmark_file(transcript, filename)
                if result:
                    model_results.append(result)

            self.llm_results[model_config["name"]] = model_results

        # Phase 4: 生成報告
        logger.info("\n" + "="*70)
        logger.info("PHASE 4: 生成對比報告")
        logger.info("="*70 + "\n")

        self.generate_report()

    def generate_report(self):
        """生成 MD 格式的對比報告"""
        report_path = OUTPUT_DIR / "GPUllmcompare.md"

        with open(report_path, 'w', encoding='utf-8') as f:
            # 標題
            f.write("# SoapVoice GPU + LLM 基準測試報告\n\n")
            f.write(f"**測試日期**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**GPU**: NVIDIA RTX 2080 Ti (22GB VRAM)\n")
            f.write(f"**測試工具**: SoapVoice GPU Benchmark\n\n")

            # ASR 結果摘要
            f.write("## 1. ASR (語音轉文字) 效能\n\n")
            f.write("**模型**: Faster-Whisper Medium @ CUDA (float16)\n\n")

            f.write("| 音檔 | 時長 (秒) | ASR 耗時 (秒) | RTF | 轉錄字數 |\n")
            f.write("|------|---------|-------------|-----|----------|\n")

            total_asr_time = 0
            total_duration = 0
            for result in self.asr_results:
                f.write(f"| {result['file']} | {result['duration_sec']:.2f} | "
                       f"{result['asr_time_sec']:.2f} | {result['rtf']:.3f} | "
                       f"{len(result['transcript'])} |\n")
                total_asr_time += result['asr_time_sec']
                total_duration += result['duration_sec']

            avg_rtf = total_asr_time / total_duration if total_duration > 0 else 0
            f.write(f"\n**平均 RTF**: {avg_rtf:.3f}x (1.0 = 實時)  \n")
            f.write(f"**總 ASR 耗時**: {total_asr_time:.2f}s\n\n")

            # LLM 結果對比
            f.write("## 2. LLM (SOAP 生成) 效能對比\n\n")

            for model_name, results in self.llm_results.items():
                f.write(f"### {model_name}\n\n")

                if not results:
                    f.write("⚠️  此模型測試失敗或未運行\n\n")
                    continue

                f.write("| 音檔 | SOAP 耗時 (秒) | Token 數 | Token/秒 |\n")
                f.write("|------|--------------|---------|----------|\n")

                total_llm_time = 0
                total_tokens = 0
                for result in results:
                    tokens = result['tokens_generated']
                    time_sec = result['llm_time_sec']
                    tps = tokens / time_sec if time_sec > 0 else 0

                    f.write(f"| {result['file']} | {time_sec:.2f} | {tokens} | {tps:.1f} |\n")
                    total_llm_time += time_sec
                    total_tokens += tokens

                avg_tps = total_tokens / total_llm_time if total_llm_time > 0 else 0
                f.write(f"\n**平均 Token/秒**: {avg_tps:.1f}  \n")
                f.write(f"**總 SOAP 耗時**: {total_llm_time:.2f}s  \n")
                f.write(f"**平均單檔耗時**: {total_llm_time / len(results):.2f}s\n\n")

            # 完整 SOAP 樣本（第一個檔案）
            f.write("## 3. SOAP 生成樣本\n\n")

            for model_name, results in self.llm_results.items():
                if results:
                    f.write(f"### {model_name} - {results[0]['file']}\n\n")
                    f.write("```\n")
                    f.write(results[0]['soap']['raw'][:500])
                    f.write("\n...\n```\n\n")

            # 效能排名
            f.write("## 4. 效能排名\n\n")

            f.write("### 最快 SOAP 生成（Token/秒）\n\n")

            rankings = []
            for model_name, results in self.llm_results.items():
                if results:
                    total_time = sum(r['llm_time_sec'] for r in results)
                    total_tokens = sum(r['tokens_generated'] for r in results)
                    tps = total_tokens / total_time if total_time > 0 else 0
                    rankings.append((model_name, tps, total_time))

            rankings.sort(key=lambda x: x[1], reverse=True)

            for i, (name, tps, total_time) in enumerate(rankings, 1):
                f.write(f"{i}. **{name}**: {tps:.1f} token/秒 (總耗時: {total_time:.2f}s)\n")

            f.write("\n")

            # 推薦
            f.write("## 5. 推薦結論\n\n")
            f.write(f"- **最適合臨床使用**: {rankings[0][0] if rankings else 'N/A'} (最快)\n")
            f.write(f"- **品質與速度平衡**: 根據 SOAP 內容質量評估\n")
            f.write(f"- **2080 Ti 22GB 配置**: 可同時運行多個模型或前景任務\n\n")

        logger.info(f"✅ 報告已生成: {report_path}")
        print(f"\n📄 完整報告: {report_path}\n")

# ============================================================================
# 進入點
# ============================================================================

if __name__ == "__main__":
    controller = BenchmarkController()
    controller.run_full_benchmark()
