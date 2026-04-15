"""
完整模型測試腳本

測試內容:
- ASR: Whisper.cpp 語音轉文字
- LLM: gemma4:e4b + qwen2.5:7b SOAP 生成
- OCR: PaddleOCR/Tesseract 螢幕截圖辨識

執行方式:
    uv run python scripts/test_all_models.py
"""

import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 測試音檔
TEST_WAV_FILES = [
    ("chest_pain", "static/chest_pain.wav"),
    ("hypertension", "static/hypertension.wav"),
    ("diabetes", "static/diabetes.wav"),
    ("wound_care", "static/wound_care.wav"),
    ("respiratory", "static/respiratory.wav"),
    ("drug_order", "static/drug_order.wav"),
    ("surgery_record", "static/surgery_record.wav"),
    ("doctor_patient", "static/doctor_patient.wav"),
]


def get_system_info() -> Dict[str, Any]:
    """取得系統資訊"""
    import psutil

    info = {
        "cpu_cores": psutil.cpu_count(logical=False),
        "cpu_threads": psutil.cpu_count(logical=True),
        "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 1),
    }
    try:
        import subprocess

        gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
        )
        if gpu.returncode == 0:
            info["gpu"] = gpu.stdout.strip().split("\n")[0]
    except Exception:
        info["gpu"] = "None"
    return info


def test_whisper_cpp(audio_path: str) -> Dict[str, Any]:
    """使用 Whisper 進行語音轉文字"""
    # 1. 嘗試 faster-whisper (Python)
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel("medium", device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path)
        text = " ".join([segment.text for segment in segments])
        return {"text": text.strip(), "language": info.language, "method": "faster-whisper"}
    except ImportError:
        logger.warning("faster-whisper 未安裝")

    # 2. 嘗試 whisper CLI
    import subprocess

    try:
        result = subprocess.run(
            ["whisper", "-m", "medium", "-f", audio_path, "--language", "zh"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            # 輸出在同名的 .txt 檔案中
            txt_path = audio_path.replace(".wav", ".txt")
            if Path(txt_path).exists():
                with open(txt_path) as f:
                    text = f.read()
                return {"text": text.strip(), "method": "whisper-cli"}
    except Exception as e:
        logger.warning(f"whisper CLI 失敗: {e}")

    return {"text": "", "error": "No ASR method available", "method": "none"}


def test_llm_ollama(prompt: str, model_name: str) -> Dict[str, Any]:
    """使用 Ollama 測試 LLM"""
    import httpx

    try:
        start = time.time()
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 500,
                    },
                },
            )
        elapsed = time.time() - start

        if resp.status_code == 200:
            result = resp.json()
            text = result.get("response", "")
            # 檢查是否為空回應
            if not text or len(text.strip()) < 10:
                logger.warning(f"模型回應過短: {text[:100] if text else 'empty'}")
            return {
                "text": text.strip(),
                "time_sec": round(elapsed, 2),
                "method": "ollama",
            }
        else:
            return {"text": "", "error": f"HTTP {resp.status_code}", "time_sec": elapsed}
    except Exception as e:
        return {"text": "", "error": str(e), "time_sec": 0}


def test_llm_llama_cpp(prompt: str, model_path: str) -> Dict[str, Any]:
    """使用 llama.cpp 測試 LLM"""
    # 這個功能需要 llama.cpp 已編譯並可用
    # 目前這個測試主要使用 Ollama
    return {"text": "", "error": "llama.cpp not implemented", "time_sec": 0}


def test_ocr(image_path: str) -> Dict[str, Any]:
    """測試 OCR 模型"""
    # 1. 嘗試 Tesseract
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang="chi_tra+eng")
        return {"text": text.strip(), "method": "tesseract"}
    except Exception as e:
        logger.warning(f"Tesseract 失敗: {e}")

    # 2. 嘗試 EasyOCR
    try:
        import easyocr

        reader = easyocr.Reader(["ch_tra", "en"], gpu=False)
        result = reader.readtext(image_path)
        text = " ".join([item[1] for item in result])
        return {"text": text.strip(), "method": "easyocr"}
    except Exception as e:
        logger.warning(f"EasyOCR 失敗: {e}")

    # 3. 嘗試 PaddleOCR
    try:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False)
        result = ocr.ocr(image_path, cls=True)
        text = ""
        if result and result[0]:
            text = "\n".join([line[1][0] for line in result[0]])
        return {"text": text.strip(), "method": "paddleocr"}
    except Exception as e:
        logger.warning(f"PaddleOCR 失敗: {e}")

    return {"text": "", "error": "No OCR method available", "method": "none"}


def generate_soap_prompt(transcript: str) -> str:
    """生成 SOAP 病歷提示詞"""
    return f"""你是一個專業的醫療助理，請根據以下醫療對話轉錄文字，生成 SOAP 病歷記錄。

轉錄內容:
{transcript}

請生成標準的 SOAP 病歷格式:
- S (Subjective): 主觀資料 - 病人的主訴和症狀描述
- O (Objective): 客觀資料 - 檢查發現的生命體徵和理學檢查
- A (Assessment): 評估 - 診斷和臨床判斷
- P (Plan): 計劃 - 治療計劃和後續處理

請用繁體中文輸出完整的 SOAP 病歷。"""


def run_full_test() -> Dict[str, Any]:
    """執行完整測試"""
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "system_info": get_system_info(),
        "tests": [],
    }

    # 測試每個音檔
    for name, wav_path in TEST_WAV_FILES:
        logger.info(f"=== 測試: {name} ===")
        wav_full = Path(wav_path)
        if not wav_full.exists():
            logger.warning(f"檔案不存在: {wav_path}")
            continue

        test_result = {
            "name": name,
            "wav_file": str(wav_path),
            "asr": {},
            "llm_gemma": {},
            "llm_qwen": {},
            "total_time": 0,
        }

        # 1. ASR 測試
        logger.info(f"  [ASR] 開始轉錄...")
        asr_start = time.time()
        asr_result = test_whisper_cpp(str(wav_full))
        asr_elapsed = time.time() - asr_start
        test_result["asr"] = {
            **asr_result,
            "time_sec": round(asr_elapsed, 2),
        }
        logger.info(f"  [ASR] 完成 ({asr_elapsed:.2f}秒)")

        if not asr_result.get("text"):
            logger.warning(f"  ASR 轉錄失敗，跳過 LLM 測試")
            test_result["llm_gemma"] = {"error": "ASR failed", "time_sec": 0}
            test_result["llm_qwen"] = {"error": "ASR failed", "time_sec": 0}
            results["tests"].append(test_result)
            continue

        transcript = asr_result["text"]
        prompt = generate_soap_prompt(transcript)

        # 2. gemma4:e4b 測試
        logger.info(f"  [LLM:gemma4:e4b] 開始生成 SOAP...")
        llm_start = time.time()
        gemma_result = test_llm_ollama(prompt, "gemma4:e4b")
        gemma_elapsed = time.time() - llm_start
        test_result["llm_gemma"] = {
            **gemma_result,
            "time_sec": round(gemma_elapsed, 2),
        }
        logger.info(f"  [LLM:gemma4:e4b] 完成 ({gemma_elapsed:.2f}秒)")

        # 3. qwen2.5:7b 測試
        logger.info(f"  [LLM:qwen2.5:7b] 開始生成 SOAP...")
        qwen_start = time.time()
        qwen_result = test_llm_ollama(prompt, "qwen2.5:7b")
        qwen_elapsed = time.time() - qwen_start
        test_result["llm_qwen"] = {
            **qwen_result,
            "time_sec": round(qwen_elapsed, 2),
        }
        logger.info(f"  [LLM:qwen2.5:7b] 完成 ({qwen_elapsed:.2f}秒)")

        test_result["total_time"] = round(asr_elapsed + gemma_elapsed + qwen_elapsed, 2)
        results["tests"].append(test_result)
        logger.info(f"  [總計] {test_result['total_time']}秒\n")

    # 計算統計
    if results["tests"]:
        gemma_times = [
            t["llm_gemma"].get("time_sec", 0)
            for t in results["tests"]
            if t["llm_gemma"].get("time_sec")
        ]
        qwen_times = [
            t["llm_qwen"].get("time_sec", 0)
            for t in results["tests"]
            if t["llm_qwen"].get("time_sec")
        ]
        asr_times = [
            t["asr"].get("time_sec", 0) for t in results["tests"] if t["asr"].get("time_sec")
        ]

        results["summary"] = {
            "gemma4:e4b": {
                "avg_time_sec": round(sum(gemma_times) / len(gemma_times), 2) if gemma_times else 0,
                "min_time_sec": min(gemma_times) if gemma_times else 0,
                "max_time_sec": max(gemma_times) if gemma_times else 0,
            },
            "qwen2.5:7b": {
                "avg_time_sec": round(sum(qwen_times) / len(qwen_times), 2) if qwen_times else 0,
                "min_time_sec": min(qwen_times) if qwen_times else 0,
                "max_time_sec": max(qwen_times) if qwen_times else 0,
            },
            "whisper": {
                "avg_time_sec": round(sum(asr_times) / len(asr_times), 2) if asr_times else 0,
            },
        }

    return results


def main():
    """主程式"""
    logger.info("開始完整模型測試...")

    # 檢查 Ollama 是否運行
    try:
        import httpx

        with httpx.Client(timeout=5.0) as client:
            resp = client.get("http://localhost:11434/api/tags")
            if resp.status_code != 200:
                logger.error("Ollama 未運行，請先啟動 ollama serve")
                return
            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]
            logger.info(f"可用模型: {model_names}")
    except Exception as e:
        logger.error(f"無法連接 Ollama: {e}")
        return

    # 執行測試
    results = run_full_test()

    # 儲存結果
    output_path = Path("tests/fixtures/results/full_model_test.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"測試結果已儲存到: {output_path}")

    # 打印摘要
    if "summary" in results:
        print("\n" + "=" * 60)
        print("測試結果摘要")
        print("=" * 60)
        summary = results["summary"]
        print(f"Whisper 平均時間: {summary.get('whisper', {}).get('avg_time_sec', 0)}秒")
        print(f"gemma4:e4b 平均時間: {summary.get('gemma4:e4b', {}).get('avg_time_sec', 0)}秒")
        print(f"qwen2.5:7b 平均時間: {summary.get('qwen2.5:7b', {}).get('avg_time_sec', 0)}秒")
        print("=" * 60)

    return results


if __name__ == "__main__":
    main()
