"""
測試術語標準化與 ICD-10 分類功能
"""

import os
import sys
import re
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_terminology_mapper():
    """測試醫療術語映射器"""
    try:
        from src.nlp.terminology_mapper import MedicalTerminologyMapper

        mapper = MedicalTerminologyMapper()

        # 測試已知症狀
        test_cases = [
            ("病人胸悶兩天", ["胸悶"]),
            ("患者咳嗽發燒", ["咳嗽", "發燒"]),
            ("頭痛腹痛", ["頭痛", "腹痛"]),
            ("呼吸困難喘", ["呼吸困難", "喘"]),
        ]

        all_passed = True
        for text, expected_terms in test_cases:
            normalized, mappings = mapper.map_text(text)
            found_terms = [m.original for m in mappings]
            print(f"  文字: {text}")
            print(f"    標準化: {normalized}")
            print(f"    找到術語: {found_terms}")
            for expected in expected_terms:
                if expected in found_terms:
                    print(f"      ✅ 包含 {expected}")
                else:
                    print(f"      ❌ 缺少 {expected}")
                    all_passed = False

        if all_passed:
            print("✅ 術語映射器測試通過")
            return True
        else:
            print("❌ 術語映射器測試失敗")
            return False
    except Exception as e:
        print(f"❌ 術語映射器測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_icd10_classifier():
    """測試 ICD-10 分類器"""
    try:
        from src.nlp.icd10_classifier import ICD10Classifier

        classifier = ICD10Classifier()

        test_cases = [
            ("病人胸悶兩天", ["R07.89"]),
            ("咳嗽發燒", ["R05", "R50.9"]),
            ("頭痛腹痛", ["R51", "R10.9"]),
            ("呼吸困難喘", ["R06.02"]),
        ]

        all_passed = True
        for text, expected_codes in test_cases:
            matches = classifier.classify(text)
            found_codes = [m.code for m in matches]
            print(f"  文字: {text}")
            print(f"    找到 ICD-10 代碼: {found_codes}")
            for expected in expected_codes:
                if expected in found_codes:
                    print(f"      ✅ 包含 {expected}")
                else:
                    print(f"      ❌ 缺少 {expected}")
                    all_passed = False

        if all_passed:
            print("✅ ICD-10 分類器測試通過")
            return True
        else:
            print("❌ ICD-10 分類器測試失敗")
            return False
    except Exception as e:
        print(f"❌ ICD-10 分類器測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_extended_symptom_extraction():
    """測試擴展引擎的症狀提取"""
    try:
        from scripts.extended_soapvoice import ExtendedSoapVoiceEngine

        engine = ExtendedSoapVoiceEngine()

        test_cases = [
            ("病人胸悶兩天", ["胸悶"]),
            ("咳嗽發燒頭痛", ["咳嗽", "發燒", "頭痛"]),
            ("腹痛腹瀉嘔吐", ["腹痛", "腹瀉", "嘔吐"]),
        ]

        all_passed = True
        for text, expected_symptoms in test_cases:
            symptoms = engine.extract_symptoms(text)
            print(f"  文字: {text}")
            print(f"    提取症狀: {symptoms}")
            for expected in expected_symptoms:
                if expected in symptoms:
                    print(f"      ✅ 包含 {expected}")
                else:
                    print(f"      ❌ 缺少 {expected}")
                    all_passed = False

        if all_passed:
            print("✅ 擴展症狀提取測試通過")
            return True
        else:
            print("❌ 擴展症狀提取測試失敗")
            return False
    except Exception as e:
        print(f"❌ 擴展症狀提取測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_extended_icd10_classification():
    """測試擴展引擎的 ICD-10 分類"""
    try:
        from scripts.extended_soapvoice import ExtendedSoapVoiceEngine

        engine = ExtendedSoapVoiceEngine()

        test_cases = [
            ("病人胸悶兩天", ["R07.89"]),
            ("咳嗽發燒", ["R05", "R50.9"]),
        ]

        all_passed = True
        for text, expected_codes in test_cases:
            results = engine.classify_icd10(text)
            found_codes = [r["code"] for r in results]
            print(f"  文字: {text}")
            print(f"    分類結果: {found_codes}")
            for expected in expected_codes:
                if expected in found_codes:
                    print(f"      ✅ 包含 {expected}")
                else:
                    print(f"      ❌ 缺少 {expected}")
                    all_passed = False

        if all_passed:
            print("✅ 擴展 ICD-10 分類測試通過")
            return True
        else:
            print("❌ 擴展 ICD-10 分類測試失敗")
            return False
    except Exception as e:
        print(f"❌ 擴展 ICD-10 分類測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_api_endpoints():
    """測試術語標準化與 ICD-10 API 端點（需要後端運行）"""
    try:
        import requests

        health_url = "http://127.0.0.1:8010/health"
        try:
            resp = requests.get(health_url, timeout=2)
            backend_available = resp.status_code == 200
        except requests.exceptions.ConnectionError:
            backend_available = False

        if not backend_available:
            print("⚠️ 後端 API 未運行，跳過 API 端點測試")
            return True  # 跳過不算失敗

        # 測試術語標準化端點
        normalize_url = "http://127.0.0.1:8010/api/v1/clinical/normalize"
        test_text = "病人胸悶兩天伴隨咳嗽"
        payload = {"text": test_text}
        response = requests.post(normalize_url, json=payload)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 術語標準化 API 成功: {result['normalized_text']}")
            print(f"   術語數: {len(result['terms'])}")
        else:
            print(f"❌ 術語標準化 API 失敗: {response.status_code} - {response.text}")
            return False

        # 測試 ICD-10 分類端點
        icd10_url = "http://127.0.0.1:8010/api/v1/clinical/icd10"
        response = requests.post(icd10_url, json=payload)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ ICD-10 分類 API 成功: {len(result['matches'])} 個匹配")
            for match in result["matches"]:
                print(f"   代碼: {match['code']}, 描述: {match['description_zh']}")
        else:
            print(f"❌ ICD-10 分類 API 失敗: {response.status_code} - {response.text}")
            return False

        print("✅ API 端點測試通過")
        return True
    except Exception as e:
        print(f"❌ API 端點測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🏥 測試術語標準化與 ICD-10 分類功能")
    print("=" * 60)

    results = []
    results.append(test_terminology_mapper())
    results.append(test_icd10_classifier())
    results.append(test_extended_symptom_extraction())
    results.append(test_extended_icd10_classification())
    results.append(test_api_endpoints())

    if all(results):
        print("\n✅ 所有術語與 ICD-10 功能測試通過")
        sys.exit(0)
    else:
        print("\n❌ 部分術語與 ICD-10 功能測試失敗")
        sys.exit(1)
