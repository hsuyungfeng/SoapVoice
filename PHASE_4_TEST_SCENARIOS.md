# Phase 4 Test Scenarios — 端到端訊息流測試

**目的**: 驗證 LINE → AstrBot → Ollama → SoapVoice 完整流程  
**狀態**: 測試計劃已建立 (2026-04-30)

---

## 前置條件 (必須)

所有三個服務必須同時運行:

```bash
# Terminal 1: Ollama
ollama serve

# Terminal 2: SoapVoice API (port 8010)
cd /home/hsu/Desktop/SoapVoice
uvicorn src.main:app --host 0.0.0.0 --port 8010

# Terminal 3: AstrBot (port 6185)
cd /home/hsu/Desktop/SoapVoice/AstrBot
python main.py
```

**驗證服務就緒:**

```bash
# 檢查 Ollama
curl http://localhost:11434/api/tags
# 應看到: qwen3.6:latest 在列表中

# 檢查 SoapVoice
curl http://localhost:8010/docs
# 應看到 FastAPI Swagger UI

# 檢查 AstrBot
curl http://localhost:6185/api/health
# 應看到 200 OK
```

---

## Test Scenario 1: 簡單文本訊息 (驗證基本路由)

**目標**: 驗證 AstrBot 能接收並路由訊息給 LLM

**步驟:**

```bash
# 1. 模擬 LINE webhook 請求
curl -X POST http://localhost:6185/api/platform/webhook/line_clinic_comms \
  -H "Content-Type: application/json" \
  -H "X-Line-Signature: YOUR_SIGNATURE" \
  -d '{
    "events": [
      {
        "type": "message",
        "message": {
          "type": "text",
          "text": "你好"
        },
        "source": {
          "type": "user",
          "userId": "U1234567890abcdef1234567890abcdef"
        },
        "timestamp": 1609459200000,
        "replyToken": "nHuyWiB7yP5Zw52FIkcQT"
      }
    ]
  }'

# 預期回應: 200 OK
```

**驗證:**

- [ ] AstrBot 日誌顯示接收訊息
- [ ] LLM (Ollama) 被呼叫
- [ ] 無錯誤堆棧跟蹤

**日誌位置:**

```bash
# 監看 AstrBot 日誌
tail -f AstrBot/logs/* 2>/dev/null || echo "Check console output"

# 監看 SoapVoice 日誌
tail -f /tmp/soapvoice.log 2>/dev/null || echo "Check terminal 2"
```

---

## Test Scenario 2: 患者身份驗證 (工具函式調用)

**目標**: 驗證 LLM 能正確調用 `verify_patient` 工具

**步驟:**

```bash
# 1. 發送包含身份資訊的訊息
curl -X POST http://localhost:6185/api/platform/webhook/line_clinic_comms \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "type": "message",
        "message": {
          "type": "text",
          "text": "我是王小明，生於1990年，請幫我查一下掛號資訊"
        },
        "source": {
          "type": "user",
          "userId": "Utest001"
        },
        "timestamp": 1609459200000,
        "replyToken": "reply001"
      }
    ]
  }'
```

**驗證:**

- [ ] LLM 抽取患者名字 (王小明) 和出生年份 (1990)
- [ ] `verify_patient` 工具被呼叫
- [ ] SoapVoice 接收 `GET /api/v1/patient/verify?name=王小明&birth_year=1990`
- [ ] SoapVoice 回傳 `{"verified": true, "patient_id": ...}`

**檢查 SoapVoice 日誌:**

```bash
# Terminal 2 (SoapVoice) 應顯示:
# INFO:     GET /api/v1/patient/verify?name=王小明&birth_year=1990
# 200 OK response with patient_id
```

---

## Test Scenario 3: 病歷查詢 (多步驟流程)

**目標**: 驗證 LLM 能調用 `search_patient_records` 並解析結果

**步驟:**

```bash
curl -X POST http://localhost:6185/api/platform/webhook/line_clinic_comms \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "type": "message",
        "message": {
          "type": "text",
          "text": "王小明，我最近的看診記錄"
        },
        "source": {
          "type": "user",
          "userId": "Utest001"
        },
        "timestamp": 1609459200000,
        "replyToken": "reply002"
      }
    ]
  }'
```

**預期流程:**

1. LLM 識別出患者名字
2. 呼叫 `verify_patient` 取得 patient_id
3. 呼叫 `search_patient_records` 檢索病歷
4. LLM 生成摘要回覆

**驗證:**

- [ ] SoapVoice 日誌顯示兩個 API 呼叫
- [ ] 患者隱私被保護 (LINE userId 與醫療資料分離)

---

## Test Scenario 4: 系統上下文注入 (驗證 @on_llm_request)

**目標**: 驗證 LLM 收到診所資訊和患者病歷上下文

**步驟:**

```bash
# 1. 監看 Ollama logs 以確認 system prompt
# Terminal 1 (Ollama) 應顯示包含診所資訊的 system prompt

# 2. 發送簡單訊息
curl -X POST http://localhost:6185/api/platform/webhook/line_clinic_comms \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "type": "message",
        "message": {
          "type": "text",
          "text": "診所電話多少"
        },
        "source": {
          "type": "user",
          "userId": "Utest001"
        },
        "timestamp": 1609459200000,
        "replyToken": "reply003"
      }
    ]
  }'
```

**驗證:**

- [ ] LLM 知道診所名稱、電話、地址
- [ ] 回覆包含來自 `clinic_info.json` 的資訊
- [ ] 系統提示詞正確注入

---

## Test Scenario 5: 錯誤處理 (邊界情況)

### 5A: 無效患者

```bash
curl -X POST http://localhost:6185/api/platform/webhook/line_clinic_comms \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "type": "message",
        "message": {
          "type": "text",
          "text": "我是假病人123，生於2099年"
        },
        "source": {
          "type": "user",
          "userId": "Utest002"
        },
        "timestamp": 1609459200000,
        "replyToken": "reply004"
      }
    ]
  }'
```

**預期**: LLM 禮貌地通知患者身份驗證失敗

### 5B: Ollama 連接失敗

```bash
# 1. 停止 Ollama
# pkill ollama

# 2. 發送訊息
curl -X POST http://localhost:6185/api/platform/webhook/line_clinic_comms ...

# 預期: AstrBot 優雅地處理 LLM 不可用
# 應返回錯誤訊息而非崩潰
```

### 5C: SoapVoice 不可達

```bash
# 1. 停止 SoapVoice
# pkill uvicorn

# 2. 發送包含身份驗證的訊息
curl -X POST http://localhost:6185/api/platform/webhook/line_clinic_comms ...

# 預期: LLM 工具調用失敗，AstrBot 返回降級回應
```

---

## 自動化測試腳本

```bash
#!/bin/bash

# test_phase4.sh — 自動化 Phase 4 測試

BASE_URL="http://localhost:6185/api/platform/webhook/line_clinic_comms"
SOAPVOICE_URL="http://localhost:8010"

test_count=0
pass_count=0

run_test() {
  local name=$1
  local payload=$2
  local expected_status=$3

  echo "Running: $name"
  test_count=$((test_count + 1))

  response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL" \
    -H "Content-Type: application/json" \
    -d "$payload")

  status=$(echo "$response" | tail -n1)
  body=$(echo "$response" | head -n-1)

  if [ "$status" = "$expected_status" ]; then
    echo "  ✓ PASS (HTTP $status)"
    pass_count=$((pass_count + 1))
  else
    echo "  ✗ FAIL (HTTP $status, expected $expected_status)"
    echo "  Response: $body"
  fi
  echo ""
}

# 檢查服務就緒
echo "Checking services..."
curl -s http://localhost:11434/api/tags > /dev/null && echo "✓ Ollama ready" || echo "✗ Ollama not ready"
curl -s http://localhost:8010/docs > /dev/null && echo "✓ SoapVoice ready" || echo "✗ SoapVoice not ready"
curl -s http://localhost:6185/api/health > /dev/null && echo "✓ AstrBot ready" || echo "✗ AstrBot not ready"
echo ""

# Test 1: Simple message
run_test "Simple message" \
  '{
    "events": [{
      "type": "message",
      "message": {"type": "text", "text": "你好"},
      "source": {"type": "user", "userId": "Utest001"},
      "timestamp": 1609459200000,
      "replyToken": "reply001"
    }]
  }' \
  "200"

# Test 2: Patient verification
run_test "Patient verification" \
  '{
    "events": [{
      "type": "message",
      "message": {"type": "text", "text": "我是王小明，生於1990年"},
      "source": {"type": "user", "userId": "Utest001"},
      "timestamp": 1609459200000,
      "replyToken": "reply002"
    }]
  }' \
  "200"

# Summary
echo "═══════════════════════════════════════════"
echo "Test Summary: $pass_count/$test_count passed"
echo "═══════════════════════════════════════════"

if [ $pass_count -eq $test_count ]; then
  echo "✓ All tests passed!"
  exit 0
else
  echo "✗ Some tests failed"
  exit 1
fi
```

**執行自動化測試:**

```bash
chmod +x test_phase4.sh
./test_phase4.sh
```

---

## 日誌監看指南

### 監看所有三個服務的日誌:

```bash
# Terminal 4: 監看所有日誌
tail -f <(echo "=== Ollama ===") \
        <(curl -s http://localhost:11434/api/tags 2>&1 | head -1) \
        <(echo "=== SoapVoice ===") \
        <(tail -f /tmp/soapvoice.log 2>/dev/null || echo "Waiting...") \
        <(echo "=== AstrBot ===") \
        <(tail -f AstrBot/logs/* 2>/dev/null || echo "Waiting...")
```

### 或分別監看:

```bash
# Terminal 1: Ollama (應看到 inference 日誌)
# Terminal 2: SoapVoice (應看到 API 呼叫)
# Terminal 3: AstrBot (應看到外掛載入和訊息處理)
```

---

## 成功標誌 (Phase 4 完成)

✅ **以下跡象表示 Phase 4 成功完成:**

1. **外掛加載**
   ```
   [INFO] Loading plugin: clinic_communication
   [INFO] Registered 5 LLM tools from ClinicCommunicationStar
   ```

2. **訊息接收**
   ```
   [INFO] Received LINE webhook: type=message, text="..."
   ```

3. **LLM 推理**
   ```
   [Ollama] Inference started for qwen3.6:latest
   [Ollama] Generated response
   ```

4. **工具調用 (若適用)**
   ```
   [INFO] Calling tool: verify_patient (name=王小明, birth_year=1990)
   [SoapVoice] GET /api/v1/patient/verify?name=王小明&birth_year=1990
   ```

5. **回應傳回**
   ```
   [INFO] Sending response back to LINE
   ```

---

## 常見問題排除

| 問題 | 症狀 | 解決方案 |
|------|------|--------|
| 外掛未加載 | AstrBot 日誌中無 "clinic_communication" | 檢查 `metadata.yaml` 語法，確認檔案位置 |
| LLM 無回應 | 訊息被吃掉，無 Ollama 日誌 | 確保 Ollama 執行中，模型已載入 (`ollama pull qwen3.6:latest`) |
| SoapVoice 不連通 | LLM 工具呼叫失敗 | 確保 SoapVoice 執行在 port 8010，檢查防火牆 |
| Webhook 驗證失敗 | 403 Forbidden | LINE 簽名驗證失敗，檢查 `channel_secret` 設定 |
| 患者隱私洩露 | LINE userId 出現在日誌 | 檢查 `patient_mapper.py` 的隔離機制 |

---

**預期完成時間**: 30-45 分鐘  
**下一步**: 若所有測試通過，進行 Phase 5 (工具函式完善)
