"""
Test LLM Database CLI Integration

測試 LLM 資料庫 CLI 層的查詢功能
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.llm_db_cli import LLMDatabaseCLI, create_llm_db_cli


def test_icd10_query():
    """測試 ICD-10 查詢"""
    print("\n✅ TEST: ICD-10 Query")
    print("-" * 60)

    cli = create_llm_db_cli(Path("data/local_db/medical.db"))

    # 測試關鍵字查詢
    result = cli.query_icd10("chest pain", limit=3)
    print(f"Query: 'chest pain'")
    print(f"Status: {result['status']}")
    print(f"Results count: {result['count']}")

    if result['status'] == 'success':
        for r in result['results'][:2]:
            print(f"  • {r['code']}: {r['name_en']} ({r['name_cn']})")

    # 測試代碼查詢
    detail = cli.get_icd10_by_code("R07.9")
    print(f"\nQuery: ICD-10 code 'R07.9'")
    print(f"Status: {detail['status']}")
    if detail['status'] == 'success':
        print(f"  {detail['code']}: {detail['name_en']} ({detail['name_cn']})")

    cli.close()


def test_drug_query():
    """測試藥品查詢"""
    print("\n✅ TEST: Drug Query")
    print("-" * 60)

    cli = create_llm_db_cli(Path("data/local_db/medical.db"))

    # 測試藥品名稱查詢
    result = cli.query_drugs("aspirin", limit=3)
    print(f"Query: 'aspirin'")
    print(f"Status: {result['status']}")
    print(f"Results count: {result['count']}")

    if result['status'] == 'success':
        for r in result['results'][:1]:
            print(f"  • {r['drug_name_en']} ({r['drug_name_cn']})")
            print(f"    ATC: {r['atc_code']} | 劑型: {r['dosage_form']}")

    # 測試 ATC 分類查詢
    atc_result = cli.query_drugs_by_atc("N02", limit=5)
    print(f"\nQuery: ATC class 'N02' (Analgesics)")
    print(f"Status: {atc_result['status']}")
    print(f"Results count: {atc_result['count']}")

    if atc_result['status'] == 'success':
        for r in atc_result['results'][:2]:
            print(f"  • {r['drug_name_cn']} ({r['atc_code']})")

    cli.close()


def test_medical_orders():
    """測試醫療服務查詢"""
    print("\n✅ TEST: Medical Orders Query")
    print("-" * 60)

    cli = create_llm_db_cli(Path("data/local_db/medical.db"))

    result = cli.query_medical_orders("injection", limit=3)
    print(f"Query: 'injection'")
    print(f"Status: {result['status']}")
    print(f"Results count: {result['count']}")

    if result['status'] == 'success':
        for r in result['results'][:2]:
            print(f"  • {r['name_en']} ({r['name_cn']})")
            print(f"    Category: {r['category']} | Points: {r['fee_points']}")

    cli.close()


def test_statistics():
    """測試資料庫統計"""
    print("\n✅ TEST: Database Statistics")
    print("-" * 60)

    cli = create_llm_db_cli(Path("data/local_db/medical.db"))

    stats = cli.get_statistics()
    print(f"Status: {stats['status']}")

    if stats['status'] == 'success':
        for table, count in stats['statistics'].items():
            print(f"  • {table}: {count} records")

    cli.close()


if __name__ == "__main__":
    print("=" * 60)
    print("LLM Database CLI Integration Tests")
    print("=" * 60)

    try:
        test_icd10_query()
        test_drug_query()
        test_medical_orders()
        test_statistics()

        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
