"""
完整 SOAP 生成測試
結合 qwen2.5:7b, gemma4:e4b, Whisper medium, PaddleOCR
使用專案 Prompt 系統並記錄完整過程

執行方式:
    uv run --with httpx python3 scripts/test_soap_pipeline.py
"""

import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# 測試音檔
TEST_WAV = [
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
    import psutil

    info = {
        "cpu_cores": psutil.cpu_count(logical=False),
        "cpu_threads": psutil.cpu_count(logical=True),
        "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
    }
    try:
        import subprocess

        gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
        )
        if gpu.returncode == 0:
            info["gpu"] = gpu.stdout.strip().split("\n")[0]
    except Exception:
        pass
    return info


def test_whisper(audio_path: str) -> Dict[str, Any]:
    """使用 Faster-Whisper 轉錄"""
    from faster_whisper import WhisperModel

    start = time.time()
    model = WhisperModel("medium", device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, language="zh")
    text = " ".join([seg.text for seg in segments])
    elapsed = time.time() - start

    return {
        "transcript": text.strip(),
        "language": info.language,
        "time_sec": round(elapsed, 2),
        "method": "faster-whisper-medium",
    }


def test_ocr(image_path: str) -> Dict[str, Any]:
    """使用 PaddleOCR 辨識圖片"""
    try:
        from paddleocr import PaddleOCR

        start = time.time()
        ocr = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False)
        result = ocr.ocr(image_path, cls=True)
        elapsed = time.time() - start

        text = ""
        if result and result[0]:
            text = "\n".join([line[1][0] for line in result[0]])

        return {
            "text": text.strip(),
            "time_sec": round(elapsed, 2),
            "method": "paddleocr",
        }
    except Exception as e:
        return {"text": "", "error": str(e), "time_sec": 0, "method": "paddleocr"}


def generate_soap_prompt(transcript: str, ocr_text: str = "") -> str:
    """生成 SOAP 病歷的 Prompt (使用專案格式)"""
    ocr_section = ""
    if ocr_text:
        ocr_section = f"\n## 螢幕截圖 OCR 結果:\n{ocr_text}\n"

    return f"""你是一個專業的醫療病歷助理。請根據以下門診對話轉錄文字，生成標準的 SOAP 病歷記錄。

## 門診對話轉錄:
{transcript}{ocr_section}

## 輸出格式要求:
請嚴格按照以下格式輸出 SOAP 病歷，使用繁體中文:

### S (Subjective) - 主觀資料
病人的主訴、症狀描述、病史、用藥情況等（用病人第一人稱描述）

### O (Objective) - 客觀資料
- 生命體徵: 體溫、血壓、心率、呼吸次數等
- 理學檢查: 身體檢查發現
- 檢驗檢查: 實驗室檢查結果、影像學發現

### A (Assessment) - 評估
臨床診斷、診斷代碼(ICD-10)、病情嚴重程度評估

### P (Plan) - 計劃
- 治療措施: 藥物處方、生活建議
- 後續處置: 檢查安排、門診追蹤
- 健康教育: 用藥指導、衛教內容

請確保輸出完整、專業，符合醫療記錄標準。"""


def test_llm_ollama(
    prompt: str,
    model_name: str,
    temperature: float = 0.3,
    max_tokens: int = 512,
) -> Dict[str, Any]:
    """使用 Ollama LLM 生成 SOAP"""
    import httpx

    start = time.time()
    try:
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            )
        elapsed = time.time() - start

        if resp.status_code == 200:
            result = resp.json()
            return {
                "soap": result.get("response", "").strip(),
                "time_sec": round(elapsed, 2),
                "model": model_name,
                "method": "ollama",
            }
        else:
            return {
                "soap": "",
                "error": f"HTTP {resp.status_code}",
                "time_sec": round(elapsed, 2),
                "model": model_name,
            }
    except Exception as e:
        return {
            "soap": "",
            "error": str(e),
            "time_sec": 0,
            "model": model_name,
        }


def run_soap_test(
    name: str,
    wav_path: str,
    ocr_image: Optional[str] = None,
    llm_models: List[str] = None,
) -> Dict[str, Any]:
    """執行完整的 SOAP 生成測試"""
    if llm_models is None:
        llm_models = ["qwen2.5:7b", "gemma4:e4b"]

    result = {
        "name": name,
        "wav_file": wav_path,
        "asr": {},
        "ocr": {},
        "llm_results": [],
    }

    # 1. ASR - Whisper
    logger.info(f"[{name}] 1. Whisper 轉錄中...")
    asr_result = test_whisper(wav_path)
    result["asr"] = asr_result
    logger.info(f"[{name}] ASR 完成: {asr_result['time_sec']}秒")

    if not asr_result.get("transcript"):
        logger.warning(f"[{name}] 轉錄失敗，跳過 LLM 測試")
        result["llm_results"] = [{"error": "ASR failed"}]
        return result

    # 2. OCR - PaddleOCR (可選)
    if ocr_image and Path(ocr_image).exists():
        logger.info(f"[{name}] 2. PaddleOCR 辨識中...")
        ocr_result = test_ocr(ocr_image)
        result["ocr"] = ocr_result
        logger.info(f"[{name}] OCR 完成: {ocr_result.get('time_sec', 0)}秒")
    else:
        result["ocr"] = {"text": "", "method": "none"}

    # 3. LLM - 根據不同模型生成 SOAP
    for model in llm_models:
        logger.info(f"[{name}] 3. LLM ({model}) 生成 SOAP...")

        prompt = generate_soap_prompt(
            asr_result["transcript"],
            ocr_text=result["ocr"].get("text", ""),
        )

        llm_result = test_llm_ollama(prompt, model)
        result["llm_results"].append(llm_result)
        logger.info(f"[{name}] {model} 完成: {llm_result.get('time_sec', 0)}秒")

    return result


def main():
    """主程式"""
    import httpx

    logger.info("=" * 60)
    logger.info("SoapVoice 完整 SOAP 生成測試")
    logger.info("=" * 60)

    # 檢查 Ollama
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get("http://localhost:11434/api/tags")
            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]
            logger.info(f"可用 Ollama 模型: {model_names}")
    except Exception as e:
        logger.error(f"Ollama 未運行: {e}")
        return

    # 測試配置
    llm_models = ["qwen2.5:7b", "gemma4:e4b"]

    # 執行測試
    all_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "system": get_system_info(),
        "config": {
            "llm_models": llm_models,
            "asr": "faster-whisper medium",
            "ocr": "paddleocr",
        },
        "tests": [],
    }

    for name, wav_path in TEST_WAV:
        full_wav = Path(wav_path)
        if not full_wav.exists():
            logger.warning(f"檔案不存在: {wav_path}")
            continue

        logger.info(f"\n{'=' * 40}")
        logger.info(f"測試案例: {name}")
        logger.info(f"{'=' * 40}")

        result = run_soap_test(name, str(full_wav), llm_models=llm_models)
        all_results["tests"].append(result)

    # 統計摘要
    if all_results["tests"]:
        asr_times = [t["asr"].get("time_sec", 0) for t in all_results["tests"]]
        ocr_times = [
            t["ocr"].get("time_sec", 0) for t in all_results["tests"] if t["ocr"].get("time_sec")
        ]

        all_results["summary"] = {
            "whisper": {
                "avg": round(sum(asr_times) / len(asr_times), 2),
                "min": min(asr_times),
                "max": max(asr_times),
            },
            "paddleocr": {
                "avg": round(sum(ocr_times) / len(ocr_times), 2) if ocr_times else 0,
            },
        }

        # 每個 LLM 模型統計
        for model in llm_models:
            model_times = []
            for test in all_results["tests"]:
                for llm_result in test["llm_results"]:
                    if llm_result.get("model") == model:
                        model_times.append(llm_result.get("time_sec", 0))
            if model_times:
                all_results["summary"][model] = {
                    "avg": round(sum(model_times) / len(model_times), 2),
                    "min": min(model_times),
                    "max": max(model_times),
                }

    # 儲存結果
    output_dir = Path("tests/fixtures/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "soap_pipeline_test.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    logger.info(f"\n結果已儲存: {output_path}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("測試結果摘要")
    print("=" * 60)

    summary = all_results.get("summary", {})
    print(f"Whisper 平均: {summary.get('whisper', {}).get('avg', 0)}秒")
    print(f"qwen2.5:7b 平均: {summary.get('qwen2.5:7b', {}).get('avg', 0)}秒")
    print(f"gemma4:e4b 平均: {summary.get('gemma4:e4b', {}).get('avg', 0)}秒")

    # 打印第一個案例的 SOAP 輸出樣例
    if all_results["tests"] and all_results["tests"][0]["llm_results"]:
        print("\n" + "=" * 60)
        print("SOAP 輸出樣例 (第一個案例)")
        print("=" * 60)
        for llm in all_results["tests"][0]["llm_results"]:
            print(f"\n--- {llm.get('model')} ---")
            print(llm.get("soap", "N/A")[:800])
            print("...")

    return all_results


if __name__ == "__main__":
    main()
