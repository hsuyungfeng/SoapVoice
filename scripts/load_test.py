#!/usr/bin/env python3
"""
負載測試腳本

使用 locust 進行 API 負載測試
測試場景：
1. 文本標準化 API
2. ICD-10 分類 API
3. SOAP 分類 API
4. 健康檢查 API
"""

import random
import logging
from locust import HttpUser, task, between

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 測試用醫療文本
TEST_TEXTS = [
    "病人胸悶兩天還有點喘",
    "頭痛發燒咳嗽",
    "腹痛腹瀉噁心",
    "血壓 140/90 心跳每分 80 下",
    "初步診斷為肺炎疑似感染",
    "開藥三天後回診追蹤",
    "病人說他胸悶很痛",
    "呼吸困難伴隨心悸",
    "胃痛伴隨腹脹",
    "失眠焦慮疲倦",
]


class SoapVoiceUser(HttpUser):
    """SoapVoice API 負載測試用戶"""

    # 等待時間 1-3 秒
    wait_time = between(1, 3)

    @task(3)
    def test_normalize(self):
        """測試文本標準化 API"""
        text = random.choice(TEST_TEXTS)
        with self.client.post(
            "/api/v1/clinical/normalize",
            json={"text": text},
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(2)
    def test_icd10(self):
        """測試 ICD-10 分類 API"""
        text = random.choice(TEST_TEXTS)
        with self.client.post(
            "/api/v1/clinical/icd10",
            json={"text": text},
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(2)
    def test_soap_classify(self):
        """測試 SOAP 分類 API"""
        text = random.choice(TEST_TEXTS)
        with self.client.post(
            "/api/v1/clinical/classify/soap",
            params={"text": text},
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(1)
    def test_health(self):
        """測試健康檢查 API"""
        self.client.get("/health")

    @task(1)
    def test_clinical_health(self):
        """測試臨床 NLP 健康檢查"""
        self.client.get("/api/v1/clinical/health")


class SoapVoiceWeightedUser(SoapVoiceUser):
    """加權測試用戶 - 模擬真實使用場景"""

    # 文本標準化使用頻率最高
    @task(5)
    def test_normalize(self):
        super().test_normalize()

    # ICD-10 分類次之
    @task(3)
    def test_icd10(self):
        super().test_icd10()

    # SOAP 分類再次
    @task(2)
    def test_soap_classify(self):
        super().test_soap_classify()

    # 健康檢查最少
    @task(1)
    def test_health(self):
        super().test_health()
