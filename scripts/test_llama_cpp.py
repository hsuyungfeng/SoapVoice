"""
Windows CPU Llama.cpp 測試
使用 llama.cpp CLI 進行離線測試

執行方式:
    cd /home/hsu/Desktop/SoapVoice/models/llama-cpp
    ./llama-cli -m ../qwen2.5-7b-instruct-q4_k_m.gguf [參數]
"""

import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Any

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

# 模型路徑
LLAMA_CLI = "/home/linuxbrew/.linuxbrew/bin/llama-cli"
MODELS_DIR = Path("/home/hsu/Desktop/SoapVoice/models")
QWEN2_5_7B = MODELS_DIR / "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
QWEN2_5_3B = MODELS_DIR / "qwen2.5-3b-instruct-q4_k_m.gguf"


def get_llama_models() -> List[Dict[str, Path]]:
    """取得可用的 GGUF 模型"""
    models = []
    for p in MODELS_DIR.glob("*.gguf"):
        models.append({"name": p.stem, "path": p})
    return models


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
    }


def generate_soap_prompt(transcript: str) -> str:
    """生成 SOAP Prompt"""
    return f"""你是一個專業的醫療病歷助理。請根據以下門診對話轉錄文字，生成標準的 SOAP 病歷記錄。

## 門診對話轉錄:
{transcript}

## 輸出格式:
### S (Subjective) - 主觀資料
[病人主訴、症狀描述、病史]

### O (Objective) - 客觀資料
- 生命體徵
- 理學檢查
- 檢驗檢查

### A (Assessment) - 評估
[臨床診斷、ICD-10]

### P (Plan) - 計劃
- 治療措施
- 後續處置
- 健康教育

請用繁體中文輸出完整的 SOAP 病歷。"""


def test_llama_cpp(
    prompt: str,
    model_path: Path,
    n_threads: int = 8,
    n_ctx: int = 4096,
    temperature: float = 0.3,
    max_tokens: int = 512,
) -> Dict[str, Any]:
    """使用 llama.cpp CLI 測試"""
    if not model_path.exists():
        return {"error": f"Model not found: {model_path}"}

    # 寫入臨時 prompt 檔案
    prompt_file = Path("/tmp/llama_prompt.txt")
    prompt_file.write_text(prompt, encoding="utf-8")

    cmd = [
        LLAMA_CLI,
        "-m",
        str(model_path),
        "--threads",
        str(n_threads),
        "-c",
        str(n_ctx),
        "--temp",
        str(temperature),
        "-n",
        str(max_tokens),
        "-f",
        str(prompt_file),
        "--no-display-prompt",
        "--gpu",
        "disable",  # 強制 CPU 模式
    ]

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        elapsed = time.time() - start

        if result.returncode == 0:
            return {
                "soap": result.stdout.strip(),
                "time_sec": round(elapsed, 2),
                "model": model_path.name,
                "method": "llama-cpp",
            }
        else:
            return {
                "error": result.stderr,
                "time_sec": round(elapsed, 2),
            }
    except subprocess.TimeoutExpired:
        return {"error": "Timeout", "time_sec": 300}
    except Exception as e:
        return {"error": str(e), "time_sec": 0}


def test_ocr(image_path: str) -> Dict[str, Any]:
    """使用 PaddleOCR 測試"""
    try:
        from paddleocr import PaddleOCR

        start = time.time()
        ocr = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False)
        result = ocr.ocr(image_path, cls=True)
        elapsed = time.time() - start

        text = ""
        if result and result[0]:
            text = "\n".join([line[1][0] for line in result[0]])

        return {"text": text.strip(), "time_sec": round(elapsed, 2)}
    except Exception as e:
        return {"text": "", "error": str(e)}


def run_tests():
    """執行完整測試"""
    print("=" * 60)
    print("Windows CPU Llama.cpp 測試")
    print("=" * 60)

    # 檢查可用模型
    models = get_llama_models()
    print(f"\n可用 GGUF 模型: {[m['name'] for m in models]}")

    # 選擇測試模型
    test_models = []
    if QWEN2_5_7B.exists():
        test_models.append(("qwen2.5:7b", QWEN2_5_7B))
    if QWEN2_5_3B.exists():
        test_models.append(("qwen2.5:3b", QWEN2_5_3B))

    all_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "test_type": "llama-cpp CPU only",
        "tests": [],
    }

    # 測試每個音檔
    for name, wav_path in TEST_WAV:
        full_wav = Path(wav_path)
        if not full_wav.exists():
            print(f"跳過: {name} (檔案不存在)")
            continue

        print(f"\n{'=' * 40}")
        print(f"測試: {name}")
        print(f"{'=' * 40}")

        result = {
            "name": name,
            "wav_file": str(wav_path),
        }

        # 1. ASR
        print(f"[ASR] 轉錄中...")
        asr_result = test_whisper(str(full_wav))
        result["asr"] = asr_result
        print(f"[ASR] 完成: {asr_result.get('time_sec', 0)}秒")

        if not asr_result.get("transcript"):
            print(f"[錯誤] 轉錄失敗")
            continue

        transcript = asr_result["transcript"]
        prompt = generate_soap_prompt(transcript)

        # 2. LLM 測試
        result["llm_results"] = []
        for model_name, model_path in test_models:
            print(f"[LLM:{model_name}] 生成 SOAP...")
            llm_result = test_llama_cpp(prompt, model_path)
            result["llm_results"].append(llm_result)
            print(f"[LLM:{model_name}] 完成: {llm_result.get('time_sec', 0)}秒")

        all_results["tests"].append(result)

    # 計算統計
    if all_results["tests"]:
        asr_times = [t["asr"].get("time_sec", 0) for t in all_results["tests"]]
        all_results["summary"] = {
            "whisper_avg": round(sum(asr_times) / len(asr_times), 2),
        }

        for model_name, _ in test_models:
            times = []
            for test in all_results["tests"]:
                for llm in test["llm_results"]:
                    if model_name in llm.get("model", ""):
                        times.append(llm.get("time_sec", 0))
            if times:
                all_results["summary"][f"{model_name}_avg"] = round(sum(times) / len(times), 2)

    # 儲存結果
    output = Path("tests/fixtures/results/llama_cpp_test.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n結果已儲存: {output}")
    return all_results


if __name__ == "__main__":
    run_tests()
