import subprocess
import json
import time
from pathlib import Path

# 定義音訊檔案列表
AUDIO_DIR = Path("static")
AUDIO_FILES = [
    "chest_pain.wav",
    "hypertension.wav",
    "diabetes.wav",
    "wound_care.wav",
    "respiratory.wav",
    "drug_order.wav",
    "surgery_record.wav",
    "doctor_patient.wav",
]

# 配置
MODEL_PATH = "models/gemma-4-E4B-it-Q4_K_M.gguf"
BACKEND = "llama.cpp"
OUTPUT_FILE = "compare_results_gemma.json"

def run_test(audio_file):
    audio_path = AUDIO_DIR / audio_file
    print(f"Running test: {audio_file}...")
    
    start_time = time.time()
    try:
        # 執行 CLI 並獲取 JSON 輸出
        cmd = [
            "uv", "run", "src/cli_typer.py", "process",
            "--audio", str(audio_path),
            "--backend", BACKEND,
            "--model-path", MODEL_PATH,
            "--whisper-model", "small",
            "--json"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout
        json_start = output.find('{')
        if json_start != -1:
            data = json.loads(output[json_start:])
        else:
            data = {"error": "No JSON found", "output": output}
            
    except Exception as e:
        print(f"Error running {audio_file}: {e}")
        data = {"error": str(e)}
        
    duration = time.time() - start_time
    data["benchmark_duration"] = duration
    return data

def main():
    results = {}
    for audio in AUDIO_FILES:
        results[audio] = run_test(audio)
        # 存檔以防中斷
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
    print(f"Benchmark completed. Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
