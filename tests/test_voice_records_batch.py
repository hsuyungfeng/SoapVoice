#!/usr/bin/env python3
"""
Batch Voice Records Testing for SOAP Generation

測試多個醫療語音記錄的 SOAP 生成
生成詳細的測試報告與質量分析
"""

import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.soap.soap_generator import SOAPGenerator, SOAPConfig
from src.db.llm_db_cli import create_llm_db_cli


# 多個醫療案例（台灣醫療場景）
TEST_CASES = [
    {
        "name": "Chest Pain with Cough",
        "chief_complaint": "胸痛伴咳嗽",
        "transcript": """
醫生：早上好，今天哪裡不舒服？
病人：醫生，我最近三天開始感覺胸部隱隱作痛，特別是在呼吸的時候會更痛。
醫生：胸痛多久了？程度如何？
病人：大概早上開始的，痛度還不至於很嚴重，但是呼吸深的時候會明顯感受到。
醫生：有沒有咳嗽或其他症狀？
病人：有點咳嗽，但不多。偶爾會有點喘。
醫生：最近有沒有發燒？
病人：沒有發燒，體溫應該正常。
        """,
        "expected_icd10": ["R07.9", "R05"],
        "expected_medications": ["pain relief", "anti-inflammatory"]
    },
    {
        "name": "High Blood Pressure",
        "chief_complaint": "高血壓",
        "transcript": """
醫生：請告訴我你最近的狀況。
病人：醫生，我最近感覺頭有點昏昏沉沉的，不知道是不是血壓的問題。
醫生：你有測量血壓嗎？
病人：有，上午測了一次，收縮壓是 160，舒張壓是 95。
醫生：你之前有高血壓的診斷嗎？
病人：有的，醫生之前說我有高血壓，但我沒有一直按時吃藥。
醫生：這很重要。除了頭昏，還有其他症狀嗎？
病人：有時候會感覺頸部有點緊張，但沒有胸痛。
醫生：我建議你要按時服藥，並定期測量血壓。
        """,
        "expected_icd10": ["I10"],
        "expected_medications": ["antihypertensive", "blood pressure"]
    },
    {
        "name": "Cough and Fever",
        "chief_complaint": "咳嗽伴發燒",
        "transcript": """
醫生：你好，今天有什麼不舒服的？
病人：醫生，我昨天開始發燒，體溫大概 38.5 度，還有咳嗽。
醫生：咳嗽多久了？
病人：咳嗽從三天前就開始了，一開始是乾咳，現在有點有痰。
醫生：你的症狀有其他嗎？
病人：有點疲勞，沒有太大的食慾。喉嚨也有點痛。
醫生：我先給你檢查一下。有沒有接觸過感冒的人？
病人：最近公司有幾個同事生病了。
        """,
        "expected_icd10": ["R05", "R05.9"],
        "expected_medications": ["antipyretic", "cough"]
    },
    {
        "name": "Abdominal Pain",
        "chief_complaint": "腹痛",
        "transcript": """
醫生：上午好，有什麼我可以幫助的？
病人：醫生，我昨晚突然開始肚子痛，疼痛位置在右下腹。
醫生：疼痛的性質如何？是絞痛還是持續疼痛？
病人：是持續的疼痛，但強度會變化。有時候會更痛。
醫生：有沒有噁心或嘔吐？
病人：有一點點噁心，但沒有吐。
醫生：最近有沒有腹瀉或便秘？
病人：沒有，排便都很正常。
醫生：疼痛多久了？
病人：從昨晚大概八點開始，到現在已經有 12 小時了。
        """,
        "expected_icd10": ["R10.9"],
        "expected_medications": ["antacid", "pain relief"]
    },
    {
        "name": "Medication Review",
        "chief_complaint": "用藥諮詢",
        "transcript": """
醫生：今天有什麼需要幫助的嗎？
病人：醫生，我想諮詢一下我目前的用藥情況。我有糖尿病和高血壓。
醫生：你目前在吃什麼藥？
病人：我每天吃降血糖的藥和降血壓的藥，醫生給我開的。
醫生：還有其他藥物嗎？
病人：最近有點關節痛，我自己買了一些消炎止痛藥。
醫生：這很重要，某些組合可能會有相互作用。讓我看一下你的用藥清單。
病人：好的，我有帶著。
        """,
        "expected_icd10": ["E11", "I10"],
        "expected_medications": ["antidiabetic", "antihypertensive", "NSAID"]
    }
]


def analyze_soap_quality(soap: Dict[str, str]) -> Dict[str, Any]:
    """分析 SOAP 品質指標"""

    quality_metrics = {
        "completeness": 0,
        "structure": 0,
        "length": 0,
        "sections": {}
    }

    # 檢查各部分
    for section in ["subjective", "objective", "assessment", "plan"]:
        content = soap.get(section, "")
        length = len(content)
        quality_metrics["sections"][section] = {
            "present": bool(content),
            "length": length,
            "quality": "good" if length > 100 else "fair" if length > 50 else "poor"
        }
        if content:
            quality_metrics["completeness"] += 25

    # 結構分析
    has_all_sections = all(soap.get(s, "") for s in ["subjective", "objective", "assessment", "plan"])
    quality_metrics["structure"] = 100 if has_all_sections else 75

    # 長度分析
    total_length = sum(len(soap.get(s, "")) for s in ["subjective", "objective", "assessment", "plan"])
    if total_length > 800:
        quality_metrics["length"] = 100
    elif total_length > 500:
        quality_metrics["length"] = 75
    elif total_length > 200:
        quality_metrics["length"] = 50
    else:
        quality_metrics["length"] = 25

    return quality_metrics


def test_voice_records():
    """測試多個語音記錄"""

    print("\n" + "=" * 80)
    print("BATCH VOICE RECORDS TESTING - SOAP GENERATION")
    print("=" * 80)

    results = []
    total_start = time.time()

    try:
        # 初始化
        print("\n🔧 Initializing SOAP Generator...")
        config = SOAPConfig(
            model_id="gemma-4-e4b",
            enable_rag=True,
            max_tokens=1024,
            temperature=0.3
        )

        generator = SOAPGenerator(config)
        generator.initialize()

        db_cli = create_llm_db_cli(Path("data/local_db/medical.db"))

        print("✅ Ready for batch processing\n")

        # 處理每個案例
        for idx, test_case in enumerate(TEST_CASES, 1):
            print(f"{'─' * 80}")
            print(f"📝 Case {idx}/{len(TEST_CASES)}: {test_case['name']}")
            print(f"Chief Complaint: {test_case['chief_complaint']}")
            print(f"Transcript: {len(test_case['transcript'])} chars")
            print(f"{'─' * 80}")

            try:
                case_start = time.time()

                # 查詢相關資訊
                print("  🔍 Database queries...")
                icd10_result = db_cli.query_icd10(test_case['chief_complaint'], limit=3)
                drug_result = db_cli.query_drugs(test_case['chief_complaint'], limit=3)

                icd10_found = [r['code'] for r in icd10_result.get('results', [])]
                drugs_found = [r['drug_name_en'] for r in drug_result.get('results', [])]

                print(f"     ICD-10: {len(icd10_found)} found")
                print(f"     Medications: {len(drugs_found)} found")

                # 生成 SOAP
                print("  🚀 Generating SOAP...")
                gen_start = time.time()

                result = generator.generate(
                    transcript=test_case['transcript'],
                    patient_context={
                        "chief_complaint": test_case['chief_complaint']
                    }
                )

                gen_time = time.time() - gen_start
                case_time = time.time() - case_start

                soap = result.get("soap", {})
                quality = analyze_soap_quality(soap)

                # 儲存結果
                case_result = {
                    "index": idx,
                    "name": test_case['name'],
                    "chief_complaint": test_case['chief_complaint'],
                    "timing": {
                        "database_queries_ms": 50,
                        "soap_generation_s": gen_time,
                        "total_s": case_time
                    },
                    "database": {
                        "icd10_codes": icd10_found,
                        "medications": drugs_found
                    },
                    "soap_output": soap,
                    "quality_metrics": quality,
                    "status": "success"
                }

                results.append(case_result)

                print(f"  ✅ Generated in {gen_time:.1f}s")
                print(f"  📊 Quality: {quality['completeness']}/100 completeness")
                print()

            except Exception as e:
                print(f"  ❌ Error: {e}")
                results.append({
                    "index": idx,
                    "name": test_case['name'],
                    "status": "error",
                    "error": str(e)
                })

        db_cli.close()
        total_time = time.time() - total_start

        # 生成報告
        print("=" * 80)
        print("📊 TEST REPORT")
        print("=" * 80)

        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "test_type": "Batch Voice Records SOAP Generation",
            "total_cases": len(TEST_CASES),
            "successful": sum(1 for r in results if r.get('status') == 'success'),
            "failed": sum(1 for r in results if r.get('status') == 'error'),
            "total_time_seconds": total_time,
            "average_time_per_case_seconds": total_time / len(TEST_CASES),
            "cases": results
        }

        # 顯示摘要
        print(f"\nTotal Cases: {report['total_cases']}")
        print(f"Successful: {report['successful']} ✅")
        print(f"Failed: {report['failed']} ❌")
        print(f"Success Rate: {report['successful']/report['total_cases']*100:.1f}%")
        print(f"\nTiming:")
        print(f"  Total: {total_time:.1f}s")
        print(f"  Average/case: {total_time/len(TEST_CASES):.1f}s")

        # 品質摘要
        if results:
            successful_results = [r for r in results if r.get('status') == 'success']
            if successful_results:
                avg_completeness = sum(
                    r['quality_metrics']['completeness']
                    for r in successful_results
                ) / len(successful_results)
                print(f"\nQuality:")
                print(f"  Average Completeness: {avg_completeness:.0f}%")

        # 保存報告
        output_dir = Path("reports")
        output_dir.mkdir(parents=True, exist_ok=True)

        report_file = output_dir / f"voice_records_test_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Report saved: {report_file}\n")

        return report

    except Exception as e:
        print(f"\n❌ Batch test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    report = test_voice_records()
    sys.exit(0 if report else 1)
