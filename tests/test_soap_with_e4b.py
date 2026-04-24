#!/usr/bin/env python3
"""
Test SOAP Generation with Gemma 4 E4B Model

使用 Gemma 4 E4B 模型測試 LLM Database CLI 整合的 SOAP 生成
記錄生成時間、品質和資料庫查詢結果
"""

import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.soap.soap_generator import SOAPGenerator, SOAPConfig
from src.db.llm_db_cli import create_llm_db_cli


def test_soap_generation_with_e4b():
    """使用 Gemma 4 E4B 測試 SOAP 生成"""

    print("\n" + "=" * 70)
    print("SOAP Generation Test with Gemma 4 E4B Model")
    print("Testing LLM Database CLI Integration")
    print("=" * 70)

    # 醫療對話文本（台灣醫療案例）
    transcript = """
    醫生：早上好，今天哪裡不舒服？
    病人：醫生，我最近三天開始感覺胸部隱隱作痛，特別是在呼吸的時候會更痛。
    醫生：胸痛多久了？程度如何？
    病人：大概早上開始的，痛度還不至於很嚴重，但是呼吸深的時候會明顯感受到。
    醫生：有沒有咳嗽或其他症狀？
    病人：有點咳嗽，但不多。偶爾會有點喘。
    醫生：最近有沒有發燒？
    病人：沒有發燒，體溫應該正常。
    醫生：有心臟病病史嗎？
    病人：沒有，家族裡也沒有心臟病史。
    醫生：我先幫你檢查一下。聽起來像是胸膜炎或輕微的肺炎，但需要進一步檢查確認。
    病人：需要拍 X 光嗎？
    醫生：是的，我建議先拍胸部 X 光來排除肺部問題，也可能需要做心電圖。
    病人：好的，那藥物方面呢？
    醫生：先開止痛藥和消炎藥給你，看看症狀有沒有改善。如果三天後還是沒好，就需要回診檢查。
    """

    print(f"\n📋 Test Case: Taiwanese Medical Scenario (Chest Pain with Cough)")
    print(f"Transcript length: {len(transcript)} characters\n")

    try:
        # 1. 初始化 SOAP Generator
        print("🔧 Initializing SOAP Generator with Gemma 4 E4B...")
        start_init = time.time()

        config = SOAPConfig(
            model_id="gemma-4-e4b",
            enable_rag=True,
            rag_top_k=3,
            max_tokens=1024,
            temperature=0.3
        )

        generator = SOAPGenerator(config)
        # 強制使用 llama.cpp + E4B 模型
        import os
        os.environ["USE_LLAMA_CPP"] = "true"
        os.environ["LLAMA_MODEL_PATH"] = "models/gemma-4-E4B-it-Q4_K_M.gguf"
        os.environ["LLAMA_N_GPU_LAYERS"] = "-1"  # 完全 GPU 卸載

        generator.initialize()
        init_time = time.time() - start_init
        print(f"✅ SOAP Generator initialized in {init_time:.2f}s\n")

        # 2. 初始化資料庫 CLI
        print("🗄️  Initializing LLM Database CLI...")
        start_db = time.time()
        cli = create_llm_db_cli(Path("data/local_db/medical.db"))
        db_time = time.time() - start_db
        print(f"✅ Database CLI initialized in {db_time:.2f}s\n")

        # 3. 查詢相關的 ICD-10 和藥品
        print("🔍 Querying database for relevant ICD-10 codes and medications...\n")

        # ICD-10 查詢
        print("  ICD-10 Codes (Chest pain):")
        icd10_result = cli.query_icd10("chest pain", limit=3)
        icd10_codes = [r['code'] for r in icd10_result.get('results', [])]
        for r in icd10_result.get('results', []):
            print(f"    • {r['code']}: {r['name_en']} ({r['name_cn']})")

        # 藥品查詢
        print("\n  Medications (Pain relief):")
        drug_result = cli.query_drugs("pain relief", limit=3)
        drug_recs = [
            {"name": r['drug_name_en'], "dosage": "遵醫囑"}
            for r in drug_result.get('results', [])
        ]
        for r in drug_result.get('results', []):
            print(f"    • {r['drug_name_en']} ({r['drug_name_cn']})")
            print(f"      ATC: {r['atc_code']} | Form: {r['dosage_form']}")

        # 4. 生成 SOAP
        print("\n" + "-" * 70)
        print("🚀 Generating SOAP with LLM Database CLI Integration...\n")
        start_gen = time.time()

        result = generator.generate(
            transcript=transcript,
            patient_context={
                "age": "45",
                "gender": "M",
                "chief_complaint": "Chest pain with cough"
            },
            drug_recommendations=drug_recs
        )

        gen_time = time.time() - start_gen
        print(f"✅ SOAP generated in {gen_time:.2f}s\n")

        # 5. 顯示結果
        print("=" * 70)
        print("📄 GENERATED SOAP NOTE")
        print("=" * 70)

        soap = result.get("soap", {})

        print("\n[SUBJECTIVE]")
        print(soap.get("subjective", "N/A")[:500])

        print("\n[OBJECTIVE]")
        print(soap.get("objective", "N/A")[:500])

        print("\n[ASSESSMENT]")
        print(soap.get("assessment", "N/A")[:500])

        print("\n[PLAN]")
        print(soap.get("plan", "N/A")[:500])

        # 6. 性能統計
        print("\n" + "=" * 70)
        print("📊 PERFORMANCE METRICS")
        print("=" * 70)

        total_time = init_time + db_time + gen_time

        print(f"\n  Initialization:     {init_time:8.2f}s")
        print(f"  Database queries:   {db_time:8.2f}s")
        print(f"  SOAP generation:    {gen_time:8.2f}s")
        print(f"  {'─' * 40}")
        print(f"  Total time:         {total_time:8.2f}s")

        if gen_time > 0:
            print(f"  Response rate:      {1/gen_time:.2f} SOAP/sec")

        # 7. 儲存完整結果
        output_file = Path("benchmarks/E4B_SOAP_TEST_RESULT.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        test_result = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": "Gemma 4 E4B",
            "transcript_length": len(transcript),
            "timing": {
                "initialization_s": init_time,
                "database_queries_s": db_time,
                "soap_generation_s": gen_time,
                "total_s": total_time
            },
            "icd10_found": len(icd10_codes),
            "icd10_codes": icd10_codes,
            "medications_found": len(drug_recs),
            "medications": [d["name"] for d in drug_recs],
            "soap_output": {
                "subjective": soap.get("subjective", ""),
                "objective": soap.get("objective", ""),
                "assessment": soap.get("assessment", ""),
                "plan": soap.get("plan", "")
            },
            "llm_response_length": len(result.get("raw_response", "")),
            "status": "success"
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(test_result, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Test result saved to: {output_file}\n")

        # 8. 顯示資料庫統計
        print("=" * 70)
        print("🗄️  DATABASE STATISTICS")
        print("=" * 70)

        stats = cli.get_statistics()
        if stats.get('status') == 'success':
            for table, count in stats['statistics'].items():
                print(f"  {table}: {count:,} records")

        cli.close()

        print("\n" + "=" * 70)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("=" * 70 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ Test failed with error:")
        print(f"  {type(e).__name__}: {e}\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_soap_generation_with_e4b()
    sys.exit(0 if success else 1)
