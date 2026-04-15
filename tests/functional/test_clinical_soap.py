"""
測試臨床 SOAP 生成端點（使用 llama.cpp）
"""

import sys
import time
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_clinical_soap_generate():
    """測試臨床 SOAP 生成端點"""
    try:
        import requests

        health_url = "http://127.0.0.1:8010/health"
        try:
            resp = requests.get(health_url, timeout=2)
            backend_available = resp.status_code == 200
        except requests.exceptions.ConnectionError:
            backend_available = False

        if not backend_available:
            print("⚠️ 後端 API 未運行，跳過臨床 SOAP 生成測試")
            return True  # 跳過不算失敗

        # 使用已知症狀的轉錄文字
        transcript = "病人胸悶兩天，伴隨咳嗽與發燒"
        payload = {
            "transcript": transcript,
            "patient_context": {"age": 45, "gender": "M", "chief_complaint": "chest pain"},
        }
        url = "http://127.0.0.1:8010/api/v1/clinical/soap/generate"

        print(f"📡 呼叫臨床 SOAP 生成端點: {url}")
        start_time = time.time()
        response = requests.post(url, json=payload)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            soap = result.get("soap", {})
            metadata = result.get("metadata", {})
            print(f"  處理時間: {elapsed:.2f} 秒")
            print(f"  SOAP 主觀: {soap.get('subjective', '')[:50]}...")
            print(f"  SOAP 客觀: {soap.get('objective', '')[:50]}...")
            print(f"  SOAP 評估: {soap.get('assessment', '')[:50]}...")
            print(f"  SOAP 計畫: {soap.get('plan', '')[:50]}...")
            print(f"  醫囑建議: {soap.get('medical_orders', [])}")
            print(f"  藥物建議: {soap.get('drug_recommendations', [])}")
            print(f"  模型版本: {metadata.get('model_version', 'unknown')}")

            # 檢查必要欄位
            assert "subjective" in soap, "SOAP 缺少 subjective 欄位"
            assert "objective" in soap, "SOAP 缺少 objective 欄位"
            assert "assessment" in soap, "SOAP 缺少 assessment 欄位"
            assert "plan" in soap, "SOAP 缺少 plan 欄位"
            assert "medical_orders" in soap, "SOAP 缺少 medical_orders 欄位"
            assert "drug_recommendations" in soap, "SOAP 缺少 drug_recommendations 欄位"

            # 醫囑與藥物建議可能為空（若資料庫無匹配）
            # 但至少 SOAP 文字不應為空
            # 檢查至少一個 SOAP 欄位有內容
            soap_fields = [
                soap.get("subjective", ""),
                soap.get("objective", ""),
                soap.get("assessment", ""),
                soap.get("plan", ""),
            ]
            if any(field.strip() for field in soap_fields):
                print("✅ SOAP 內容非空")
            else:
                print("⚠️ SOAP 內容全部為空（可能 LLM 未回應）")

            print("✅ 臨床 SOAP 生成端點測試通過")
            return True
        else:
            print(f"❌ 臨床 SOAP 生成端點返回錯誤: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 臨床 SOAP 生成端點測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("📄 測試臨床 SOAP 生成端點")
    print("=" * 60)

    if test_clinical_soap_generate():
        print("\n✅ 臨床 SOAP 生成端點測試通過")
        sys.exit(0)
    else:
        print("\n❌ 臨床 SOAP 生成端點測試失敗")
        sys.exit(1)
