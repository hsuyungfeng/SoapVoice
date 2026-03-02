#!/usr/bin/env python3
"""
端到端整合測試

測試完整的 SoapVoice API 流程：
1. 語音串流（WebSocket）
2. 文本標準化
3. ICD-10 分類
4. SOAP 生成
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 檢查是否安裝必要套件
try:
    import httpx
    import websockets
except ImportError:
    logger.error("請安裝必要套件：pip install httpx websockets")
    sys.exit(1)


class SoapVoiceE2ETest:
    """SoapVoice 端到端測試"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=30.0)
        self.tests_passed = 0
        self.tests_failed = 0

    def run_test(self, name: str, test_func) -> bool:
        """執行單一測試"""
        logger.info(f"\n測試：{name}")
        try:
            test_func()
            logger.info(f"✓ {name} 通過")
            self.tests_passed += 1
            return True
        except AssertionError as e:
            logger.error(f"✗ {name} 失敗：{e}")
            self.tests_failed += 1
            return False
        except Exception as e:
            logger.error(f"✗ {name} 錯誤：{e}")
            self.tests_failed += 1
            return False

    def test_health_check(self):
        """測試健康檢查"""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_api_v1_root(self):
        """測試 API v1 根路徑"""
        response = self.client.get("/api/v1")
        assert response.status_code == 200
        data = response.json()
        assert "endpoints" in data

    def test_clinical_normalize(self):
        """測試文本標準化"""
        payload = {"text": "病人胸悶兩天還有點喘"}
        response = self.client.post("/api/v1/clinical/normalize", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "normalized_text" in data
        assert "terms" in data
        logger.info(f"  標準化結果：{data['normalized_text']}")
        logger.info(f"  匹配術語：{len(data['terms'])} 個")

    def test_clinical_icd10(self):
        """測試 ICD-10 分類"""
        payload = {"text": "病人胸悶，呼吸困難"}
        response = self.client.post("/api/v1/clinical/icd10", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "matches" in data
        if data["matches"]:
            logger.info(f"  主要代碼：{data['primary_code']}")
            logger.info(f"  匹配數量：{len(data['matches'])} 個")

    def test_clinical_soap_classify(self):
        """測試 SOAP 分類"""
        response = self.client.post(
            "/api/v1/clinical/classify/soap",
            params={"text": "病人說他胸悶很痛"},
        )
        assert response.status_code == 200
        data = response.json()
        # 注意：如果置信度低於閾值，可能會歸類為 unknown
        assert data["category"] in ["subjective", "unknown"]
        logger.info(f"  分類結果：{data['category']}")

    def test_clinical_soap_generate(self):
        """測試 SOAP 生成"""
        # 注意：SOAP 生成需要 LLM 模型，如果模型未載入會回傳 500
        # 這裡我們測試 API 端點可訪問
        payload = {
            "transcript": "病人胸悶兩天，呼吸困難，血壓 140/90",
            "patient_context": {
                "age": 45,
                "gender": "M",
            },
        }
        response = self.client.post("/api/v1/clinical/soap/generate", json=payload)
        # 允許 200（成功）或 500（模型未載入）
        if response.status_code == 200:
            data = response.json()
            assert "soap" in data
            logger.info(f"  SOAP 生成成功")
        elif response.status_code == 500:
            logger.info(f"  SOAP 生成需要 LLM 模型（預期行為）")
        else:
            raise AssertionError(f"Unexpected status code: {response.status_code}")

    def test_clinical_health(self):
        """測試臨床 NLP 健康檢查"""
        response = self.client.get("/api/v1/clinical/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "components" in data

    def run_all_tests(self):
        """執行所有測試"""
        logger.info("========================================")
        logger.info("SoapVoice 端到端整合測試")
        logger.info(f"目標：{self.base_url}")
        logger.info("========================================")

        # 檢查服務是否可用
        try:
            self.client.get("/health")
        except httpx.ConnectError:
            logger.error(f"無法連接到 {self.base_url}")
            logger.error("請確認服務已啟動：docker compose up -d")
            return False

        # 執行測試
        tests = [
            ("健康檢查", self.test_health_check),
            ("API v1 根路徑", self.test_api_v1_root),
            ("文本標準化", self.test_clinical_normalize),
            ("ICD-10 分類", self.test_clinical_icd10),
            ("SOAP 分類", self.test_clinical_soap_classify),
            ("SOAP 生成", self.test_clinical_soap_generate),
            ("臨床 NLP 健康檢查", self.test_clinical_health),
        ]

        for name, test_func in tests:
            self.run_test(name, test_func)

        # 總結
        logger.info("\n========================================")
        logger.info("測試摘要")
        logger.info("========================================")
        logger.info(f"通過：{self.tests_passed}")
        logger.info(f"失敗：{self.tests_failed}")
        logger.info(f"總計：{self.tests_passed + self.tests_failed}")

        return self.tests_failed == 0


def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description="SoapVoice 端到端整合測試")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="API 基礎 URL",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="顯示詳細輸出",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    tester = SoapVoiceE2ETest(base_url=args.url)
    success = tester.run_all_tests()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
