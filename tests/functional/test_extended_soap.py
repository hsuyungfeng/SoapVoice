"""
測試 SOAP 生成與醫囑藥物建議功能
"""

import sys
import time
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_extended_engine_process():
    """測試擴展引擎完整流程"""
    try:
        from scripts.extended_soapvoice import ExtendedSoapVoiceEngine

        engine = ExtendedSoapVoiceEngine()

        sample_path = project_root / "tests" / "fixtures" / "sample_zh.wav"
        if not sample_path.exists():
            print(f"❌ 樣本音訊檔案不存在: {sample_path}")
            return False

        print(f"🔊 處理樣本音訊: {sample_path}")
        start_time = time.time()
        result = engine.process(str(sample_path))
        elapsed = time.time() - start_time

        print(f"  處理時間: {elapsed:.2f} 秒")
        print(f"  轉錄文字: {result.transcript[:100]}...")
        print(f"  症狀: {result.symptoms}")
        print(f"  ICD-10 代碼: {[c['code'] for c in result.icd10_codes]}")
        print(f"  醫囑建議: {result.medical_orders}")
        print(f"  藥物建議: {result.drug_recommendations}")

        # 檢查關鍵欄位非空
        assert len(result.transcript.strip()) > 0, "轉錄文字不應為空"
        # 症狀可能為空（若音訊無症狀詞彙），但至少應有 ICD-10 代碼
        # ICD-10 代碼可能為空（若無匹配），但我們期望至少有一個
        if len(result.icd10_codes) == 0:
            print("⚠️ 未找到 ICD-10 代碼（可能音訊無症狀詞彙）")
        # 醫囑與藥物建議可能為空（若無匹配）
        if len(result.medical_orders) == 0:
            print("⚠️ 醫囑建議為空")
        if len(result.drug_recommendations) == 0:
            print("⚠️ 藥物建議為空")

        # 檢查 SOAP 英文與中文輸出
        assert len(result.soap_en.strip()) > 0, "英文 SOAP 不應為空"
        assert len(result.soap_zh.strip()) > 0, "中文 SOAP 不應為空"

        # 檢查 SOAP 結構關鍵字（粗略檢查）
        soap_en_lower = result.soap_en.lower()
        # 不一定有標準標籤，但至少包含 S O A P 段落
        # 我們只檢查長度
        print(f"  英文 SOAP 長度: {len(result.soap_en)} 字元")
        print(f"  中文 SOAP 長度: {len(result.soap_zh)} 字元")

        print("✅ 擴展引擎完整流程測試通過")
        return True
    except Exception as e:
        print(f"❌ 擴展引擎完整流程測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_extended_api_endpoint():
    """測試擴展流程 API 端點（需要後端運行）"""
    try:
        import requests

        health_url = "http://127.0.0.1:8010/health"
        try:
            resp = requests.get(health_url, timeout=2)
            backend_available = resp.status_code == 200
        except requests.exceptions.ConnectionError:
            backend_available = False

        if not backend_available:
            print("⚠️ 後端 API 未運行，跳過擴展 API 端點測試")
            return True  # 跳過不算失敗

        # 上傳樣本音訊進行完整處理
        sample_path = project_root / "tests" / "fixtures" / "sample_zh.wav"
        if not sample_path.exists():
            print(f"❌ 樣本音訊檔案不存在: {sample_path}")
            return False

        files = {"audio": open(sample_path, "rb")}
        data = {"audio_path": str(sample_path)}
        process_url = "http://127.0.0.1:8010/api/v1/extended/process"

        print(f"📡 呼叫擴展流程 API 端點: {process_url}")
        start_time = time.time()
        response = requests.post(process_url, files=files, data=data)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            print(f"  API 處理時間: {elapsed:.2f} 秒")
            print(f"  轉錄文字: {result.get('transcript', '')[:100]}...")
            print(f"  症狀: {result.get('symptoms', [])}")
            print(f"  ICD-10 代碼: {[c['code'] for c in result.get('icd10_codes', [])]}")
            print(f"  醫囑建議: {result.get('medical_orders', [])}")
            print(f"  藥物建議: {result.get('drug_recommendations', [])}")

            # 檢查關鍵欄位
            assert len(result.get("transcript", "").strip()) > 0, "轉錄文字不應為空"
            assert len(result.get("soap_en", "").strip()) > 0, "英文 SOAP 不應為空"
            assert len(result.get("soap_zh", "").strip()) > 0, "中文 SOAP 不應為空"

            print("✅ 擴展流程 API 端點測試通過")
            return True
        else:
            print(f"❌ 擴展流程 API 端點返回錯誤: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 擴展流程 API 端點測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_soap_structure():
    """測試 SOAP 結構完整性（使用已知症狀與 ICD-10）"""
    try:
        from scripts.extended_soapvoice import ExtendedSoapVoiceEngine

        engine = ExtendedSoapVoiceEngine()

        # 使用已知症狀的轉錄文字
        transcript = "病人胸悶兩天，伴隨咳嗽與發燒"
        symptoms = ["胸悶", "咳嗽", "發燒"]
        icd10_codes = [
            {"code": "R07.89", "description": "Chest tightness", "confidence": 0.9},
            {"code": "R05", "description": "Cough", "confidence": 0.9},
            {"code": "R50.9", "description": "Fever, unspecified", "confidence": 0.9},
        ]
        medical_orders = ["心電圖檢查", "胸部X光", "多喝水"]
        drug_recommendations = [
            {"name": "咳特靈", "dosage": "1# 3次/日", "category": "止咳"},
            {"name": "普拿疼", "dosage": "500mg 3次/日", "category": "退燒"},
        ]

        soap_result = engine.generate_extended_soap(
            transcript, symptoms, icd10_codes, medical_orders, drug_recommendations
        )

        print(f"  生成的 SOAP 字典鍵: {list(soap_result.keys())}")
        # 檢查必要鍵
        required_keys = [
            "subjective",
            "objective",
            "assessment",
            "plan",
            "medical_orders",
            "drug_recommendations",
        ]
        for key in required_keys:
            assert key in soap_result, f"SOAP 結果缺少鍵: {key}"
            print(f"    ✅ 包含 {key}")

        # 檢查醫囑與藥物建議保留
        assert soap_result["medical_orders"] == medical_orders, "醫囑建議未正確保留"
        assert soap_result["drug_recommendations"] == drug_recommendations, "藥物建議未正確保留"

        print("✅ SOAP 結構完整性測試通過")
        return True
    except Exception as e:
        print(f"❌ SOAP 結構完整性測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("📄 測試 SOAP 生成與醫囑藥物建議功能")
    print("=" * 60)

    results = []
    results.append(test_extended_engine_process())
    results.append(test_extended_api_endpoint())
    results.append(test_soap_structure())

    if all(results):
        print("\n✅ 所有 SOAP 生成功能測試通過")
        sys.exit(0)
    else:
        print("\n❌ 部分 SOAP 生成功能測試失敗")
        sys.exit(1)
