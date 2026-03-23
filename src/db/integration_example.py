"""
症狀到藥物推薦整合範例

展示如何使用本地資料庫和 ATC 分類系統，
根據症狀智慧推薦藥物
"""

from pathlib import Path
from src.db.local_database import LocalDatabase
from src.db.atc_classification import get_atc_by_symptom, get_atc_info


def recommend_drugs_by_symptom(db: LocalDatabase, symptom: str, limit: int = 5) -> dict:
    """根據症狀推薦藥物

    Args:
        db: 本地資料庫
        symptom: 症狀名稱
        limit: 最大推薦數

    Returns:
        包含 ATC 分類和藥物推薦的字典
    """
    # Step 1: 根據症狀取得可能的 ATC 分類
    atc_codes = get_atc_by_symptom(symptom)

    if not atc_codes:
        return {
            "symptom": symptom,
            "atc_codes": [],
            "drugs": [],
            "message": f"找不到 {symptom} 對應的 ATC 分類",
        }

    # Step 2: 取得 ATC 分類詳細資訊
    atc_info = []
    for code in atc_codes:
        info = get_atc_info(code)
        if info:
            atc_info.append(
                {
                    "code": info.code,
                    "name_cn": info.name_cn,
                    "name_en": info.name_en,
                    "description": info.description,
                }
            )

    # Step 3: 搜尋符合 ATC 分類的藥物
    all_drugs = []
    for code in atc_codes:
        drugs = db.search_drugs_by_atc_class(code, limit=10)
        for drug in drugs:
            all_drugs.append(
                {
                    "drug_code": drug.drug_code,
                    "drug_name_cn": drug.drug_name_cn,
                    "drug_name_en": drug.drug_name_en,
                    "atc_code": drug.atc_code,
                    "atc_category": get_atc_info(code[:3]).name_cn
                    if len(code) >= 3
                    else get_atc_info(code).name_cn
                    if code in get_atc_info(code)
                    else code,
                    "payment_price": drug.payment_price,
                    "dosage_form": drug.dosage_form,
                    "payment_rules": drug.payment_rules[:100] + "..."
                    if len(drug.payment_rules) > 100
                    else drug.payment_rules,
                }
            )

    # 去重（根據藥品代碼）
    unique_drugs = []
    seen_codes = set()
    for drug in all_drugs:
        if drug["drug_code"] not in seen_codes:
            seen_codes.add(drug["drug_code"])
            unique_drugs.append(drug)

    return {
        "symptom": symptom,
        "atc_codes": atc_codes,
        "atc_info": atc_info,
        "drugs": unique_drugs[:limit],
        "total_found": len(unique_drugs),
    }


def demo_symptom_to_drug_recommendation():
    """症狀到藥物推薦示範"""

    # 初始化資料庫
    db = LocalDatabase(Path("data/local_db/medical.db"))

    print("=" * 70)
    print("症狀到藥物推薦系統")
    print("=" * 70)

    # 測試各種症狀
    test_symptoms = ["咳嗽", "頭痛", "發燒", "過敏", "胃痛", "腹瀉", "關節痛"]

    for symptom in test_symptoms:
        print(f"\n{'=' * 70}")
        print(f"症狀: {symptom}")
        print("=" * 70)

        # 取得推薦
        result = recommend_drugs_by_symptom(db, symptom, limit=5)

        # 顯示 ATC 分類
        if result["atc_info"]:
            print("\n可能的 ATC 分類:")
            for info in result["atc_info"]:
                print(f"  • {info['code']} - {info['name_cn']}")
                print(f"    {info['description']}")

        # 顯示推薦藥物
        if result["drugs"]:
            print(f"\n推薦藥物 (共 {result['total_found']} 種):")
            print("-" * 70)
            for i, drug in enumerate(result["drugs"], 1):
                print(f"\n{i}. {drug['drug_name_cn']}")
                print(f"   藥品代碼: {drug['drug_code']}")
                print(f"   ATC: {drug['atc_code']} ({drug['atc_category']})")
                print(f"   劑型: {drug['dosage_form']}")
                print(f"   健保價: {drug['payment_price']} 元")
                if drug["payment_rules"]:
                    print(f"   給付規定: {drug['payment_rules']}")
        else:
            print(f"\n找不到推薦藥物")

    db.close()


def demo_icd_to_drug_recommendation():
    """ICD-10 診斷到藥物推薦示範"""

    db = LocalDatabase(Path("data/local_db/medical.db"))

    print("\n" + "=" * 70)
    print("ICD-10 診斷到藥物推薦系統")
    print("=" * 70)

    # 測試診斷
    test_diagnoses = [
        ("J06.9", "急性上呼吸道感染"),
        ("J20.9", "急性支氣管炎"),
        ("K29.5", "慢性胃炎"),
        ("M54.5", "腰痛"),
        ("R05", "咳嗽"),
    ]

    for icd_code, icd_name in test_diagnoses:
        print(f"\n{'=' * 70}")
        print(f"診斷: {icd_name} ({icd_code})")
        print("=" * 70)

        # 搜尋 ICD-10
        icd_results = db.search_icd10(icd_name, limit=1)

        # 根據診斷推斷可能症狀
        symptom_map = {
            "J06": ["咳嗽", "喉嚨痛", "鼻塞"],
            "J20": ["咳嗽", "有痰", "胸痛"],
            "K29": ["胃痛", "腹脹", "嘔吐"],
            "M54": ["腰痛", "背痛", "關節痛"],
            "R05": ["咳嗽", "喉嚨痛"],
        }

        prefix = icd_code[:3] if len(icd_code) >= 3 else icd_code[:2]
        symptoms = symptom_map.get(prefix, ["一般"])

        # 為每個症狀推薦藥物
        for symptom in symptoms:
            result = recommend_drugs_by_symptom(db, symptom, limit=3)
            if result["drugs"]:
                print(f"\n症狀「{symptom}」推薦:")
                for drug in result["drugs"][:2]:
                    print(f"  • {drug['drug_name_cn']} (ATC: {drug['atc_code']})")

    db.close()


def main():
    """主程式"""
    print("\n" + "=" * 70)
    print("本地醫療資料庫整合應用示範")
    print("=" * 70)
    print("\n本示範展示:")
    print("1. 根據症狀搜尋 ATC 分類")
    print("2. 根據 ATC 分類推薦藥物")
    print("3. ICD-10 診斷到藥物推薦")
    print()

    # 執行示範
    demo_symptom_to_drug_recommendation()
    demo_icd_to_drug_recommendation()

    print("\n" + "=" * 70)
    print("示範完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
