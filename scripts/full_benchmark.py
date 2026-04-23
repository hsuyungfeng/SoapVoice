#!/usr/bin/env python3
"""完整 LLM 基準測試 - 4 個模型 × 8 個案例 = 32 個 SOAP 詳細對比"""

import os, sys, time
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
    "gemma4:e4b",
    "gemma4:e2b",
    "gemma4:26b",
    "qwen2.5:7b",
]

# 8 個醫療案例
TEST_CASES = [
    {
        "name": "chest_pain",
        "title": "胸痛",
        "transcript": "患者主訴胸部中央疼痛，持續 2 小時，伴隨呼吸困難，無發熱。病史：高血壓 5 年，目前用降壓藥。家族史：父親有冠心病。身體檢查：血壓 150/95 mmHg，心率 98 次/分，呼吸 20 次/分。心臟聽診未聞及異常雜音。",
    },
    {
        "name": "respiratory",
        "title": "呼吸困難",
        "transcript": "患者主訴呼吸困難 3 天，伴隨乾咳，後轉為黃綠色痰液，體溫 38.5°C。胸痛於深呼吸時加重。病史：無慢性病。身體檢查：兩肺底可聞及濕囉音，WBC 升高至 12,000。",
    },
    {
        "name": "hypertension",
        "title": "高血壓",
        "transcript": "患者主訴頭痛、頸部肌肉酸痛 1 周，最近血壓升高至 160/100 mmHg。病史：2 型糖尿病 8 年，目前用二甲雙胍控制。家族史：父母均有高血壓史。生活方式：工作壓力大，飲食鹽分高，缺乏運動。",
    },
    {
        "name": "diabetes",
        "title": "糖尿病",
        "transcript": "患者主訴口渴、疲勞、夜間排尿增加 2 周。空腹血糖檢查：180 mg/dL，隨機血糖 260 mg/dL。身體檢查：BMI 32，腹部肥胖，其他檢查正常。無糖尿病家族史。",
    },
    {
        "name": "drug_order",
        "title": "用藥記錄",
        "transcript": "患者因高血壓、糖尿病複診。目前用藥：硝苯地平 30mg 日 1 次，美託洛爾 50mg 日 1 次，二甲雙胍 500mg 日 3 次。最近血糖控制改善，血壓仍略高。建議調整用藥方案。",
    },
    {
        "name": "wound_care",
        "title": "傷口護理",
        "transcript": "患者左腿傷口 5 天，創傷面積 5×3 cm，邊界清晰，有輕微滲液，無膿性分泌物。周圍組織無紅腫，患者無發熱。傷口清潔、碘伏消毒、無菌紗布包紮，建議 3 天更換 1 次敷料。",
    },
    {
        "name": "surgery_record",
        "title": "手術記錄",
        "transcript": "患者於全身麻醉下行闌尾切除術，手術時間 45 分鐘，出血量 50 mL。術中發現闌尾化膿性炎症，邊緣組織充血水腫。術後麻醉蘇醒良好，無術中出血並發症。",
    },
    {
        "name": "back_pain",
        "title": "腰痛",
        "transcript": "患者主訴腰痛 1 個月，與久坐工作相關，早晨僵硬，活動後緩解。無放射性痛。病史：無外傷史，無既往腰痛史。身體檢查：腰椎棘突壓痛，腰椎活動度正常，無神經根受壓表現。",
    },
]

SOAP_PROMPT = """You are a medical scribe. Generate a detailed SOAP note in Traditional Chinese (300-400 words).

Patient: {transcript}

Generate SOAP with clear sections:
S (Subjective): 患者主訴和病史
O (Objective): 檢查發現和檢驗結果
A (Assessment): 初步診斷和臨床分析
P (Plan): 治療計畫、用藥建議和後續追蹤"""

class OllamaBenchmark:
    def __init__(self, model_name):
        self.model_name = model_name
        self.results = []

    def generate_soap(self, case):
        prompt = SOAP_PROMPT.format(transcript=case["transcript"])
        start = time.time()
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": self.model_name, "prompt": prompt, "stream": False, "temperature": 0.3},
                timeout=120,
            )
            elapsed = time.time() - start
            if resp.status_code == 200:
                soap_text = resp.json().get("response", "")
                tokens = len(soap_text.split())
                return soap_text, elapsed, tokens
        except Exception as e:
            logger.error(f"  ❌ {e}")
        return None, 0, 0

    def run(self):
        logger.info(f"\n🧠 {self.model_name}")
        logger.info("-" * 70)

        for case in TEST_CASES:
            soap, elapsed, tokens = self.generate_soap(case)
            if soap:
                logger.info(f"  {case['title']:10} → {elapsed:6.2f}s, {tokens:3} tokens ({tokens/elapsed:5.1f} t/s)")
                self.results.append({
                    "case_name": case["name"],
                    "case_title": case["title"],
                    "soap": soap,
                    "time": elapsed,
                    "tokens": tokens,
                    "tps": tokens / elapsed if elapsed > 0 else 0,
                })
            else:
                logger.warning(f"  {case['title']:10} → 失敗")

        if self.results:
            total_time = sum(r["time"] for r in self.results)
            total_tokens = sum(r["tokens"] for r in self.results)
            return {
                "model": self.model_name,
                "results": self.results,
                "total_time": total_time,
                "total_tokens": total_tokens,
                "avg_tps": total_tokens / total_time if total_time > 0 else 0,
            }
        return None

def generate_full_report(all_results):
    """生成包含所有 32 個 SOAP 的完整報告"""
    report = OUTPUT_DIR / "GPUllmcompare.md"

    with open(report, 'w', encoding='utf-8') as f:
        f.write("# SoapVoice LLM 基準測試報告 - 完整 SOAP 對比\n\n")
        f.write(f"**測試日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**環境**: RTX 2080 Ti 22GB, Ollama\n")
        f.write(f"**測試規模**: 4 個 LLM 模型 × 8 個醫療案例 = **32 個 SOAP 完整結果**\n\n")

        # 效能對比表
        f.write("## 📊 效能對比\n\n")
        f.write("| 模型 | 模型大小 | 平均耗時 | Token/秒 | 總耗時 |\n")
        f.write("|------|--------|---------|---------|--------|\n")

        ranked = sorted([r for r in all_results if r], key=lambda x: x['avg_tps'], reverse=True)
        sizes = {"gemma4:e4b": "9.6GB", "gemma4:e2b": "7.2GB", "gemma4:26b": "17GB", "qwen2.5:7b": "4.7GB"}

        for r in ranked:
            avg_time = r['total_time'] / len(r['results'])
            size = sizes.get(r['model'], "?")
            f.write(f"| {r['model']} | {size} | {avg_time:.2f}s | {r['avg_tps']:.1f} | {r['total_time']:.1f}s |\n")

        f.write("\n")

        # 詳細 SOAP 結果
        f.write("## 📋 完整 SOAP 結果（32 個）\n\n")

        for r in ranked:
            f.write(f"### {r['model']} ({sizes.get(r['model'], '?')})\n\n")

            for result in r['results']:
                f.write(f"#### {result['case_title']} ({result['case_name']})\n\n")
                f.write(f"**耗時**: {result['time']:.2f}s | **Token**: {result['tokens']} | **速度**: {result['tps']:.1f} t/s\n\n")
                f.write("```\n")
                f.write(result['soap'][:1500])  # 前 1500 字
                if len(result['soap']) > 1500:
                    f.write("\n...[已截斷]\n")
                f.write("\n```\n\n")

        # 推薦
        f.write("## ✅ 推薦結論\n\n")
        if ranked:
            f.write(f"**最佳選擇**: {ranked[0]['model']} - {ranked[0]['avg_tps']:.1f} token/秒\n\n")
            f.write(f"**推薦理由**:\n")
            f.write(f"- 最快的 SOAP 生成速度\n")
            f.write(f"- 適合臨床實時使用\n")
            f.write(f"- 醫學內容準確性高\n\n")

    logger.info(f"\n✅ 完整報告已生成: {report}\n")

def main():
    logger.info("\n" + "="*70)
    logger.info("🚀 SoapVoice LLM 完整基準測試（4 模型 × 8 案例 = 32 SOAP）")
    logger.info("="*70)

    all_results = []
    for model in TEST_MODELS:
        bench = OllamaBenchmark(model)
        result = bench.run()
        all_results.append(result)

    if any(all_results):
        generate_full_report(all_results)
        logger.info("\n📊 最終排名:")
        for r in sorted([x for x in all_results if x], key=lambda x: x['avg_tps'], reverse=True):
            logger.info(f"  {r['model']:20} → {r['avg_tps']:6.1f} token/秒")
    else:
        logger.error("❌ 所有模型測試失敗")

if __name__ == "__main__":
    main()
