#!/usr/bin/env python3
"""Generate CompareModel.md with full results in display format"""

import json
from pathlib import Path
from datetime import datetime

RESULTS_DIR = Path("/home/hsu/Desktop/SoapVoice/tests/fixtures/results")

MODELS = ["qwen2.5:3b", "qwen2.5:7b", "gemma4:e4b", "gemma4:e2b"]

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


def load_results():
    """Load results from compare_*.json files and model_results.json files"""
    all_results = []
    
    # Load batch files (compare_*.json)
    for json_file in RESULTS_DIR.glob("compare_*.json"):
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for model, model_data in data.items():
                        for r in model_data.get("results", []):
                            r["model_name"] = model
                            all_results.append(r)
                elif isinstance(data, list):
                    for r in data:
                        all_results.append(r)
        except Exception as e:
            print(f"Error loading {json_file}: {e}")

    # Load direct model files (e.g., qwen2.5:3b_results.json)
    for json_file in RESULTS_DIR.glob("*_results.json"):
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for r in data:
                        if "model_name" not in r:
                            r["model_name"] = r.get("model")
                        all_results.append(r)
        except Exception as e:
            print(f"Error loading {json_file}: {e}")

    # Deduplicate results based on model and file (keeping the latest tested ideally, but taking the first match here)
    unique_results = {}
    for r in all_results:
        key = f"{r.get('model_name')}_{r.get('file')}"
        if key not in unique_results:
            unique_results[key] = r

    return list(unique_results.values())


def format_result(r):
    """Format a single result as displayed on web"""
    lines = []
    lines.append(f"### {r['name']} ({r['model_name']})")
    lines.append("")
    lines.append(
        f"⏱️ 總處理時間: {r.get('total_time', 0)}秒 | 🎤 ASR: whisper ({r.get('transcribe_time', 0)}秒) | 🧠 LLM: {r.get('model', r['model_name'])} ({r.get('llm_time', 0)}秒)"
    )
    lines.append("")
    lines.append("📋 症狀分析")
    symptoms = r.get("symptoms", [])
    if symptoms:
        lines.append(", ".join([s if isinstance(s, str) else s.get("name", "") for s in symptoms]))
    else:
        lines.append("無")
    lines.append("")
    lines.append("🏥 ICD-10 診斷")
    codes = r.get("icd10_codes", [])
    if codes:
        lines.append(
            " | ".join([f"{c.get('code', '')} - {c.get('description', '')}" for c in codes])
        )
    else:
        lines.append("無")
    lines.append("")
    lines.append("💊 藥物建議")
    drugs = r.get("drug_recommendations", [])
    if drugs:
        lines.append(
            " | ".join([f"{d.get('name', '')}: {d.get('dosage', '依醫囑')}" for d in drugs])
        )
    else:
        lines.append("無")
    lines.append("")
    lines.append("📝 醫囑")
    orders = r.get("medical_orders", [])
    if orders:
        lines.append(" | ".join(orders))
    else:
        lines.append("無")
    lines.append("")
    lines.append("📄 SOAP 病歷")
    lines.append("```")
    soap = r.get("soap", {})
    # Handle both old and new format
    if isinstance(soap, dict):
        soap_text = soap.get("en") or soap.get("zh", "無")
    else:
        soap_text = soap if soap else "無"
    lines.append(soap_text[:2000])  # Limit length
    lines.append("```")
    lines.append("")
    lines.append("---")
    return "\n".join(lines)


def main():
    results = load_results()
    print(f"載入 {len(results)} 筆結果")

    if not results:
        print("沒有結果，請先執行測試")
        return

    # 產生 MD
    md = f"""# 模型比較報告

生成時間: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 測試配置

- **模型**: qwen2.5:3b, qwen2.5:7b
- **音檔數量**: 8 個
- **測試環境**: Ollama + GPU (RTX 2080 Ti)
- **測試總數**: {len(results)} 筆

---

## 測試結果總覽

| 檔案 | 模型 | 總時間 | 狀態 |
|------|------|--------|------|
"""
    for r in results:
        status = "❌" if r.get("error") else "✅"
        md += f"| {r['name']} | {r['model_name']} | {r.get('total_time', '-')}秒 | {status} |\n"

    md += "\n---\n\n"

    # 每個音檔的所有模型結果
    for audio_file, name in AUDIO_FILES:
        md += f"## {name}\n\n"

        # 找這個音檔的結果 (支援兩種格式：含前綴或不含)
        full_path = f"static/{audio_file}"
        file_results = [r for r in results if r["file"] == audio_file or r["file"] == full_path]

        if not file_results:
            md += "*尚未測試*\n\n"
            continue

        # 按模型顯示
        for r in file_results:
            if r.get("error"):
                md += f"### ❌ {r['model_name']}: {r.get('error')}\n\n"
            else:
                md += format_result(r)
                md += "\n"

    # 統計摘要
    md += "\n## 模型平均效能\n\n"

    for model in MODELS:
        model_results = [r for r in results if r.get("model_name") == model]
        if model_results:
            avg_total = sum(r.get("total_time", 0) for r in model_results) / len(model_results)
            avg_llm = sum(r.get("llm_time", 0) for r in model_results) / len(model_results)
            avg_transcribe = sum(r.get("transcribe_time", 0) for r in model_results) / len(
                model_results
            )
            md += f"- **{model}**: 平均 {avg_total:.1f}秒 (轉譯 {avg_transcribe:.1f}秒 + LLM {avg_llm:.1f}秒)\n"

    md += "\n---\n\n"
    md += "*Generated by SoapVoice comparison script*\n"

    # 儲存
    md_path = Path("/home/hsu/Desktop/SoapVoice/CompareModel.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"已更新: {md_path}")

    # 顯示完成狀態
    print("\n=== 測試狀態 ===")
    for audio_file, name in AUDIO_FILES:
        file_results = [r for r in results if r["file"] == audio_file]
        statuses = []
        for model in MODELS:
            matching = [r for r in file_results if r["model_name"] == model]
            if matching:
                if matching[0].get("error"):
                    statuses.append(f"{model.split(':')[1]}:❌")
                else:
                    statuses.append(f"{model.split(':')[1]}:✅")
            else:
                statuses.append(f"{model.split(':')[1]}:待測")
        print(f"{name}: {', '.join(statuses)}")


if __name__ == "__main__":
    main()
