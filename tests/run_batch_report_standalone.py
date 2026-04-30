#!/usr/bin/env python3
"""
Standalone batch SOAP report generation - avoids circular imports
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

# Avoid importing the full src package to prevent circular imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import only what we need
from src.soap.soap_generator import SOAPGenerator, SOAPConfig
from src.db.llm_db_cli import create_llm_db_cli


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
        """
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
        """
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
        """
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
        """
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
        """
    }
]


def main():
    print("\n" + "=" * 80)
    print("BATCH VOICE RECORDS TESTING WITH DETAILED REPORT GENERATION")
    print("=" * 80)

    results = []
    total_start = time.time()

    try:
        print("\n🔧 Initializing components...")
        config = SOAPConfig(
            model_id="gemma-4-e4b",
            enable_rag=True,
            max_tokens=1024,
            temperature=0.3
        )

        generator = SOAPGenerator(config)
        generator.initialize()
        db_cli = create_llm_db_cli(Path("data/local_db/medical.db"))
        print("✅ Ready\n")

        for idx, test_case in enumerate(TEST_CASES, 1):
            print(f"Case {idx}/{len(TEST_CASES)}: {test_case['name']}...", end=" ", flush=True)
            case_start = time.time()

            try:
                # Database queries
                icd10_result = db_cli.query_icd10(test_case['chief_complaint'], limit=3)
                drug_result = db_cli.query_drugs(test_case['chief_complaint'], limit=3)

                icd10_codes = [r['code'] for r in icd10_result.get('results', [])]
                medications = [r['drug_name_en'] for r in drug_result.get('results', [])]

                # Generate SOAP
                gen_start = time.time()
                result = generator.generate(
                    transcript=test_case['transcript'],
                    patient_context={"chief_complaint": test_case['chief_complaint']}
                )
                gen_time = time.time() - gen_start
                case_time = time.time() - case_start

                soap = result.get("soap", {})

                case_result = {
                    "index": idx,
                    "name": test_case['name'],
                    "chief_complaint": test_case['chief_complaint'],
                    "transcript_length": len(test_case['transcript']),
                    "status": "success",
                    "timing": {
                        "soap_generation_s": gen_time,
                        "total_s": case_time
                    },
                    "icd10_codes": icd10_codes,
                    "medications": medications,
                    "db_queries": 2,
                    "soap": soap
                }

                results.append(case_result)
                print(f"✅ {gen_time:.1f}s")

            except Exception as e:
                print(f"❌ Error: {e}")
                results.append({
                    "index": idx,
                    "name": test_case['name'],
                    "chief_complaint": test_case['chief_complaint'],
                    "status": "error",
                    "error": str(e)
                })

        db_cli.close()
        total_time = time.time() - total_start

        # Save results as JSON
        report_dir = Path("benchmarks")
        report_dir.mkdir(parents=True, exist_ok=True)

        json_file = report_dir / f"BATCH_VOICE_RECORDS_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Report saved: {json_file}\n")

        # Summary
        successful = [r for r in results if r.get('status') == 'success']
        print("=" * 80)
        print(f"✅ Summary: {len(successful)}/{len(results)} cases succeeded in {total_time:.1f}s")
        print("=" * 80 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
