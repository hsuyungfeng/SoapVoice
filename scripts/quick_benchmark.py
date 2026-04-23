#!/usr/bin/env python3
"""快速 LLM 基準測試 - Ollama 本地驗證"""

import os, sys, time, json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
OUTPUT_DIR = Path(__file__).parent.parent / "benchmarks"
OUTPUT_DIR.mkdir(exist_ok=True)

TEST_MODELS = [
    "qwen3.6:latest",
    "qwen3.5:35b", 
    "gemma4:31b",
    "gemma4:26b",
    "gemma4:e4b",
    "gemma4:e2b",
]

TEST_TRANSCRIPTS = {
    "胸痛": "患者主訴胸部中央疼痛，持續 2 小時，伴隨呼吸困難，無發熱。病史：高血壓 5 年。身體檢查：血壓 150/95，心率 98。",
    "呼吸困難": "患者主訴呼吸困難 3 天，咳嗽，有黃綠色痰液，體溫 38.5°C。胸痛於深呼吸時加重。肺部有囉音。",
    "高血壓": "患者主訴頭痛、頸部酸痛，最近血壓升高至 160/100。病史：2 型糖尿病 8 年。",
    "糖尿病": "患者主訴口渴、疲勞、夜間排尿增加。空腹血糖 180 mg/dL。BMI 32。",
}

SOAP_PROMPT = """You are a medical scribe. Generate a concise SOAP note in Traditional Chinese (200-300 words).

Patient: {transcript}

Format:
S: 患者主訴
O: 檢查結果  
A: 初步診斷
P: 治療計畫"""

class OllamaBenchmark:
    def __init__(self, model_name):
        self.model_name = model_name
    
    def generate_soap(self, transcript):
        prompt = SOAP_PROMPT.format(transcript=transcript)
        start = time.time()
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": self.model_name, "prompt": prompt, "stream": False, "temperature": 0.3},
                timeout=300,
            )
            elapsed = time.time() - start
            if resp.status_code == 200:
                text = resp.json().get("response", "")
                tokens = len(text.split())
                return text, elapsed, tokens
        except Exception as e:
            logger.error(f"  ❌ {e}")
        return None, 0, 0
    
    def run(self):
        logger.info(f"\n🧠 {self.model_name}")
        logger.info("-" * 70)
        
        results = []
        total_time = total_tokens = 0
        
        for title, transcript in TEST_TRANSCRIPTS.items():
            soap, elapsed, tokens = self.generate_soap(transcript)
            if soap:
                logger.info(f"  {title}: {elapsed:.2f}s, {tokens} tokens ({tokens/elapsed:.1f} t/s)")
                results.append({"title": title, "time": elapsed, "tokens": tokens, "tps": tokens/elapsed})
                total_time += elapsed
                total_tokens += tokens
            else:
                logger.warning(f"  {title}: 失敗")
        
        if results:
            return {
                "model": self.model_name,
                "results": results,
                "total_time": total_time,
                "total_tokens": total_tokens,
                "avg_tps": total_tokens / total_time if total_time > 0 else 0,
            }
        return None

def generate_report(all_results):
    report = OUTPUT_DIR / "GPUllmcompare.md"
    
    with open(report, 'w', encoding='utf-8') as f:
        f.write(f"# SoapVoice LLM 基準測試報告\n\n")
        f.write(f"**測試日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**環境**: RTX 2080 Ti 22GB, Ollama\n")
        f.write(f"**測試**: 4 個醫療案例, 測量 SOAP 生成速度\n\n")
        
        # 排名
        f.write("## 效能排名\n\n")
        ranked = sorted([r for r in all_results if r], key=lambda x: x['avg_tps'], reverse=True)
        f.write("| 排名 | 模型 | Token/秒 | 平均耗時 | 總耗時 |\n")
        f.write("|------|------|---------|---------|--------|\n")
        
        for i, r in enumerate(ranked, 1):
            avg_time = r['total_time'] / len(r['results'])
            f.write(f"| {i} | {r['model']} | {r['avg_tps']:.1f} | {avg_time:.2f}s | {r['total_time']:.1f}s |\n")
        
        # 詳細
        f.write("\n## 詳細結果\n\n")
        for r in ranked:
            f.write(f"### {r['model']}\n\n")
            f.write("| 案例 | 耗時 | Token | Token/秒 |\n")
            f.write("|------|-----|-------|----------|\n")
            for res in r['results']:
                f.write(f"| {res['title']} | {res['time']:.2f}s | {res['tokens']} | {res['tps']:.1f} |\n")
            f.write("\n")
        
        f.write("## 推薦\n\n")
        if ranked:
            f.write(f"- **最快**: {ranked[0]['model']} ({ranked[0]['avg_tps']:.1f} token/秒)\n")
            f.write(f"- **最小**: gemma4:e2b (7.2GB)\n")
            f.write(f"- **平衡**: gemma4:26b (17GB)\n")
    
    logger.info(f"\n✅ 報告: {report}\n")

def main():
    logger.info("\n" + "="*70)
    logger.info("🚀 SoapVoice LLM 快速基準測試")
    logger.info("="*70)
    
    all_results = []
    for model in TEST_MODELS:
        bench = OllamaBenchmark(model)
        result = bench.run()
        all_results.append(result)
    
    if any(all_results):
        generate_report(all_results)
        logger.info("\n📊 摘要:")
        for r in sorted([x for x in all_results if x], key=lambda x: x['avg_tps'], reverse=True):
            logger.info(f"  {r['model']:20} → {r['avg_tps']:6.1f} token/秒")

if __name__ == "__main__":
    main()
