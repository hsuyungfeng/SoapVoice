#!/usr/bin/env python3
"""詳細測試 p8 檢查點功能"""

import subprocess
import time
import json
import sys
import os
from urllib import request, parse


def start_server():
    """啟動後端伺服器"""
    env = os.environ.copy()
    env["USE_LLAMA_CPP"] = "true"
    proc = subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            "src.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8010",
            "--log-level",
            "warning",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc


def wait_for_server(timeout=30):
    """等待伺服器啟動"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = request.urlopen("http://localhost:8010/health", timeout=2)
            if req.status == 200:
                return True
        except:
            pass
        time.sleep(1)
    return False


def send_request(url, method="GET", data=None, headers=None):
    """發送 HTTP 請求"""
    if headers is None:
        headers = {}
    if data is not None and method == "POST":
        data = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as resp:
            return resp.read().decode()
    except Exception as e:
        print(f"請求失敗: {e}")
        return None


def main():
    print("=== 詳細測試 p8 檢查點 ===")

    # 啟動伺服器
    print("啟動伺服器...")
    server = start_server()
    try:
        if not wait_for_server():
            print("❌ 伺服器啟動超時")
            server.terminate()
            return 1

        print("✅ 伺服器啟動成功")

        # 測試 1: 音訊轉錄
        print("\n1. 測試 CPU Whisper 轉錄...")
        # 使用 Form 編碼發送 audio_path
        import urllib.parse

        data = urllib.parse.urlencode({"audio_path": "data/recordings/temp.wav"}).encode()
        req = request.Request(
            "http://localhost:8010/api/v1/extended/transcribe", data=data, method="POST"
        )
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                print(f"   轉錄文字: {result.get('transcript', '')[:100]}...")
                transcript = result.get("transcript", "")
                if transcript:
                    print("   ✅ CPU Whisper 轉錄成功")
                else:
                    print("   ⚠️  轉錄文字為空")
        except Exception as e:
            print(f"   ❌ 轉錄失敗: {e}")
            transcript = "病人主訴頭痛三天，伴隨噁心嘔吐，體溫38.5度，血壓140/90。"

        # 測試 2: 症狀提取
        print("\n2. 測試症狀提取...")
        medical_text = "病人主訴頭痛三天，伴隨噁心嘔吐，體溫38.5度，血壓140/90。有高血壓病史。"
        symptoms_resp = send_request(
            f"http://localhost:8010/api/v1/extended/symptoms/{parse.quote(medical_text)}"
        )
        if symptoms_resp:
            symptoms_data = json.loads(symptoms_resp)
            symptoms = symptoms_data.get("symptoms", [])
            print(f"   症狀列表: {symptoms}")
            if symptoms:
                print("   ✅ 症狀提取成功")
            else:
                print("   ⚠️  症狀提取返回空列表")

        # 測試 3: ICD-10 分類
        print("\n3. 測試 ICD-10 分類...")
        icd10_resp = send_request(
            f"http://localhost:8010/api/v1/extended/icd10/{parse.quote(medical_text)}"
        )
        if icd10_resp:
            icd10_data = json.loads(icd10_resp)
            icd10_codes = icd10_data.get("icd10_codes", [])
            print(f"   ICD-10 代碼: {icd10_codes}")
            if icd10_codes:
                print("   ✅ ICD-10 分類成功")
            else:
                print("   ⚠️  ICD-10 分類返回空列表")

        # 測試 4: 完整擴展流程（使用醫療文字）
        print("\n4. 測試完整擴展流程...")
        payload = {
            "transcript": medical_text,
            "model": "qwen2.5:7b",
            "include_symptoms": True,
            "include_icd10": True,
            "include_orders": True,
            "include_drugs": True,
            "output_lang": "en",
        }
        process_resp = send_request(
            "http://localhost:8010/api/v1/extended/process", method="POST", data=payload
        )
        if process_resp:
            process_data = json.loads(process_resp)
            print(f"   處理時間: {process_data.get('processing_time')}s")
            print(f"   症狀數量: {len(process_data.get('symptoms', []))}")
            print(f"   ICD-10 代碼數量: {len(process_data.get('icd10_codes', []))}")
            print(f"   醫囑數量: {len(process_data.get('medical_orders', []))}")
            print(f"   藥物建議數量: {len(process_data.get('drug_recommendations', []))}")

            # 檢查關鍵欄位
            if process_data.get("icd10_codes"):
                print("   ✅ ICD-10 代碼顯示正常")
            else:
                print("   ❌ ICD-10 代碼缺失")

            if process_data.get("medical_orders"):
                print("   ✅ 醫囑建議顯示正常")
            else:
                print("   ❌ 醫囑建議缺失")

            if process_data.get("drug_recommendations"):
                print("   ✅ 藥物建議顯示正常")
            else:
                print("   ❌ 藥物建議缺失")

            if process_data.get("soap"):
                print("   ✅ SOAP 病歷生成正常")
                # 顯示 SOAP 結構
                soap = process_data["soap"]
                for key in ["subjective", "objective", "assessment", "plan"]:
                    if key in soap:
                        print(
                            f"      {key}: {soap[key][:80]}..."
                            if len(str(soap[key])) > 80
                            else f"      {key}: {soap[key]}"
                        )

        # 測試 5: Web UI 頁面
        print("\n5. 測試 Web UI 頁面...")
        for page in ["/", "/test.html"]:
            resp = send_request(f"http://localhost:8010{page}")
            if resp and "html" in resp.lower():
                print(f"   ✅ {page} 頁面可訪問")
            else:
                print(f"   ⚠️  {page} 頁面可能無法載入")

        print("\n=== 測試完成 ===")

    finally:
        print("停止伺服器...")
        server.terminate()
        server.wait(timeout=5)

    return 0


if __name__ == "__main__":
    sys.exit(main())
