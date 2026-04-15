#!/usr/bin/env python3
"""CLI-based model comparison script using the project's own CLI and prompt logic."""

import json
import time
import subprocess
from pathlib import Path
import sys
import os

# 專案路徑
PROJECT_ROOT = Path(__file__).parent.parent
STATIC_DIR = PROJECT_ROOT / "static"
RESULTS_DIR = PROJECT_ROOT / "tests/fixtures/results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# 測試音檔
AUDIO_FILES = [
    ("chest_pain.wav", "胸痛"),
    ("hypertension.wav", "高血壓"),
    ("diabetes.wav", "糖尿病"),
    ("wound_care.wav", "傷口護理"),
    ("respiratory.wav", "呼吸道"),
    ("drug_order.wav", "醫囑"),
    ("surgery_record.wav", "手術記錄"),
    ("doctor_patient.wav", "醫病對話"),
]

def get_audio_info(file_path: Path) -> tuple:
    import wave
    try:
        with wave.open(str(file_path), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            duration = round(frames / rate, 1)
            size = round(file_path.stat().st_size / 1024, 1)
            return duration, size
    except:
        return 0, 0

def run_asr(audio_path: Path):
    """使用專案內的 WhisperModel 進行 ASR"""
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.asr.whisper_model import WhisperModel
    
    # 這裡預設使用 medium 模型，device 為 cpu
    os.environ["WHISPER_DEVICE"] = "cpu"
    os.environ["WHISPER_COMPUTE_TYPE"] = "int8"
    
    start_time = time.time()
    model = WhisperModel(model_id="medium")
    result = model.transcribe(str(audio_path))
    elapsed = round(time.time() - start_time, 2)
    
    return result.get("text", ""), elapsed

def run_cli_soap(text: str, model: str, backend: str, model_path: str = None):
    """呼叫 src/cli_typer.py 並擷取 JSON 結果"""
    cmd = [
        "uv", "run", "python", "src/cli_typer.py", "main",
        "--text", text,
        "--model", model,
        "--backend", backend,
        "--json"
    ]
    if model_path:
        cmd.extend(["--model-path", model_path])
        
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    elapsed = round(time.time() - start_time, 2)
    
    if result.returncode != 0:
        return {"error": f"CLI failed: {result.stderr}"}, elapsed
        
    try:
        # 尋找 JSON 區塊（Rich 的 console.print_json 可能會帶一些 ANSI 色彩，或者我們直接解析）
        output = result.stdout.strip()
        # 移除可能的終端色彩代碼 (如果有的話)
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-z])')
        clean_output = ansi_escape.sub('', output)
        
        # 尋找第一個 { 和最後一個 } 之間的內容
        json_match = re.search(r'\{.*\}', clean_output, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0)), elapsed
        else:
            return {"error": f"Could not find JSON in output: {clean_output}"}, elapsed
    except Exception as e:
        return {"error": f"JSON parse error: {str(e)}", "raw": result.stdout}, elapsed

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/compare_cli.py <model> [backend] [model_path]")
        print("Example: python scripts/compare_cli.py qwen2.5:7b ollama")
        print("Example: python scripts/compare_cli.py gemma-4 llama.cpp models/gemma-4-E4B-it-Q4_K_M.gguf")
        sys.exit(1)

    model_name = sys.argv[1]
    backend = sys.argv[2] if len(sys.argv) > 2 else "ollama"
    model_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    results = []
    output_file = RESULTS_DIR / f"{model_name.replace(':', '_')}_cli_results.json"

    print(f"🚀 Testing model: {model_name} (Backend: {backend})")
    print(f"📂 Results will be saved to: {output_file}\n")

    for audio_file, label in AUDIO_FILES:
        audio_path = STATIC_DIR / audio_file
        print(f"👉 Processing: {label} ({audio_file})")
        
        # 1. ASR
        print(f"   [1/2] ASR Transcribing...", end=" ", flush=True)
        transcript, asr_time = run_asr(audio_path)
        print(f"✅ {asr_time}s")
        
        # 2. CLI SOAP
        print(f"   [2/2] Generating SOAP via CLI...", end=" ", flush=True)
        soap_result, llm_time = run_cli_soap(transcript, model_name, backend, model_path)
        
        if "error" in soap_result:
            print(f"❌ Error: {soap_result['error']}")
        else:
            print(f"✅ {llm_time}s")
            
        # 彙整結果
        duration, size = get_audio_info(audio_path)
        entry = {
            "name": label,
            "audio_file": audio_file,
            "audio_duration": duration,
            "transcript": transcript,
            "asr_time": asr_time,
            "llm_time": llm_time,
            "total_time": round(asr_time + llm_time, 2),
            "model": model_name,
            "backend": backend,
            "result": soap_result
        }
        results.append(entry)
        print("-" * 30)

    # 存檔
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print(f"\n✨ Benchmark complete. Saved to {output_file}")

if __name__ == "__main__":
    main()
