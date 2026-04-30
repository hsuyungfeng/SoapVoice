# Phase 4: AstrBot 設定與 LINE webhook 整合 — 實作指南

**狀態**: Phase 4 詳細規劃完成 (2026-04-30)  
**目標**: 啟用 ClinicCommunicationStar 外掛，整合 LINE 平台與 Ollama LLM

---

## 系統架構確認

### AstrBot 配置結構
- **主配置檔**: `data/cmd_config.json` (不存在時使用預設值)
- **配置儲存**: 根據 `AstrBotConfig` 類別，配置在 `data/cmd_config.json` 中
- **平台/Bot 管理**:
  - 平台列表位於 `config["platform"]` 陣列
  - 透過 Dashboard API `/api/config/post-new-platform` 新增平台
  - 或直接編輯 `cmd_config.json` 手動新增

### 外掛加載機制
- **路徑**: `data/plugins/{plugin_name}/`
- **元數據**: 必須包含 `metadata.yaml`
- **自動掃描**: AstrBot 啟動時自動掃描 `data/plugins/` 目錄
- **ClinicCommunicationStar 狀態**: ✅ 已完成，檔案結構就位

### LINE 平台支援
- **適配器**: `LinePlatformAdapter` (已內建)
- **必要憑證**:
  - `channel_access_token`: LINE Messaging API token
  - `channel_secret`: 用於驗證 webhook 簽名
- **Webhook 模式**: 統一 webhook (AstrBot 自動生成 UUID)
- **配置示例** (見下方)

---

## Phase 4 四大子任務

### 4.1 建立 AstrBot 主配置檔

**檔案**: `AstrBot/data/cmd_config.json`

```json
{
  "config_version": 2,
  "platform": [
    {
      "id": "line_clinic_comms",
      "type": "line",
      "enabled": true,
      "channel_access_token": "YOUR_LINE_CHANNEL_ACCESS_TOKEN",
      "channel_secret": "YOUR_LINE_CHANNEL_SECRET"
    }
  ],
  "provider": [
    {
      "id": "ollama_qwen",
      "type": "ollama",
      "base_url": "http://localhost:11434",
      "model": "qwen3.6:latest"
    }
  ],
  "provider_settings": {
    "default_provider_id": "ollama_qwen",
    "enable": true
  },
  "platform_settings": {
    "unique_session": false,
    "rate_limit": {
      "time": 60,
      "count": 30,
      "strategy": "stall"
    }
  },
  "timezone": "Asia/Taipei"
}
```

**關鍵步驟:**
1. 建立檔案並填入上述配置
2. 獲取實際的 LINE Bot Token 和 Channel Secret
3. 驗證 Ollama 提供者配置

---

### 4.2 驗證外掛自動加載

**檢查清單:**

```bash
# 1. 確認外掛目錄結構
ls -la AstrBot/data/plugins/clinic_communication/
# 預期輸出:
# - __init__.py
# - main.py (ClinicCommunicationStar 核心)
# - metadata.yaml ✅ (已驗證)
# - soapvoice_client.py
# - patient_mapper.py
# - knowledge_base.py

# 2. 確認外掛資料檔
ls -la AstrBot/data/plugin_data/clinic_communication/
# 預期輸出:
# - clinic_info.json
# - emergency.json
# - faq.json

# 3. 啟動 AstrBot 時檢查日誌
# 應看到: "[INFO] Loading plugin: clinic_communication"
```

**外掛的 metadata.yaml 驗證:**
- ✅ `name`: ClinicCommunicationStar
- ✅ `version`: 1.0.0
- ✅ `plugin_id`: clinic_communication
- ✅ `adapter`: line
- ✅ `enabled`: true
- ✅ `config`: 包含 ollama、soapvoice 設定

---

### 4.3 測試訊息流向 (本機整合測試)

**消息流程:**

```
LINE 客戶端
    ↓ (HTTPS webhook POST)
AstrBot 平台適配器 (port 6185)
    ↓ (接收並路由)
ClinicCommunicationStar 外掛
    ├─ @on_llm_request() 注入上下文
    ├─ 系統提示詞 + 患者病歷
    └─ LLM 推理 (Ollama port 11434)
        ↓ 可能呼叫工具函式
SoapVoice REST API (port 8010)
    └─ 患者驗證、病歷查詢
        ↓ (回傳結果)
AstrBot → LINE
```

**測試場景 (無需真實 LINE):**

1. **模擬 webhook 請求** (curl 或 Postman)
   ```bash
   curl -X POST http://localhost:6185/api/platform/webhook/{uuid} \
     -H "Content-Type: application/json" \
     -d '{
       "events": [{
         "type": "message",
         "message": {
           "type": "text",
           "text": "我的姓名是王小明，生日是1990年"
         },
         "source": {
           "type": "user",
           "userId": "U123456789abcdef1234567890abcdef"
         }
       }]
     }'
   ```

2. **驗證日誌** 應看到:
   - ✅ 外掛接收訊息
   - ✅ LLM 呼叫 (可透過 Ollama logs 確認)
   - ✅ 工具函式執行 (如 verify_patient)
   - ✅ SoapVoice API 呼叫 (檢查 SoapVoice logs)

3. **檢查 SoapVoice 日誌** (port 8010)
   ```bash
   # 應看到 GET /api/v1/patient/verify?name=王小明&birth_year=1990
   # Response: {"verified": true, "patient_id": 12345}
   ```

---

### 4.4 配置檢查清單

**環境變數** (`.env` 或系統環境)

```bash
# Ollama 配置
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.6:latest

# LINE 平台 (手動設定或透過 Dashboard)
LINE_BOT_TOKEN=YOUR_LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET=YOUR_LINE_CHANNEL_SECRET

# SoapVoice 配置
SOAPVOICE_BASE_URL=http://localhost:8010
SOAPVOICE_API_KEY=（如果需要）

# AstrBot 配置
ASTRBOT_HOST=0.0.0.0
ASTRBOT_PORT=6185
```

**啟動服務順序 (必須):**

```bash
# 1. 啟動 Ollama (背景)
ollama serve &

# 2. 啟動 SoapVoice API (port 8010)
cd /home/hsu/Desktop/SoapVoice
uvicorn src.main:app --host 0.0.0.0 --port 8010 &

# 3. 啟動 AstrBot (port 6185)
cd /home/hsu/Desktop/SoapVoice/AstrBot
python main.py

# 或使用 Docker Compose (如果已配置)
docker-compose up
```

---

## 實作步驟 (按順序執行)

### Step 1: 建立配置檔 (5 分鐘)
- [ ] 建立 `AstrBot/data/cmd_config.json`
- [ ] 填入正確的 LINE credentials
- [ ] 驗證 Ollama provider 配置

### Step 2: 啟動服務 (10 分鐘)
- [ ] 確保 Ollama 執行中 (`ollama ps` 確認 qwen3.6:latest 已載入)
- [ ] 啟動 SoapVoice API (`uvicorn src.main:app --port 8010`)
- [ ] 啟動 AstrBot (`python AstrBot/main.py`)

### Step 3: 驗證外掛加載 (5 分鐘)
- [ ] 檢查 AstrBot 啟動日誌 (尋找 "Loading plugin: clinic_communication")
- [ ] 確認 5 個 LLM 工具已註冊

### Step 4: 測試訊息流向 (15 分鐘)
- [ ] 使用 curl 模擬 LINE webhook (見 4.3)
- [ ] 驗證 SoapVoice API 被呼叫
- [ ] 檢查 LLM 是否正確推理

### Step 5: LINE 真實整合 (如需要)
- [ ] 在 LINE Developers Console 設定 Webhook URL
- [ ] 向 Bot 傳送真實訊息進行測試
- [ ] 驗證端到端流程

---

## 故障排除

### AstrBot 無法啟動
```bash
# 檢查依賴
pip list | grep -E "quart|fastapi"

# 檢查 Python 版本 (需 3.11+)
python --version

# 查看詳細日誌
python AstrBot/main.py --debug
```

### 外掛未加載
```bash
# 確認檔案存在
ls AstrBot/data/plugins/clinic_communication/metadata.yaml

# 檢查 metadata.yaml 格式
python -c "import yaml; yaml.safe_load(open('AstrBot/data/plugins/clinic_communication/metadata.yaml'))"

# 查看 AstrBot 日誌 (外掛加載錯誤會詳細記錄)
```

### LLM 工具未註冊
```bash
# 確認外掛中有 @llm_tool 裝飾器
grep -n "@llm_tool" AstrBot/data/plugins/clinic_communication/main.py

# 檢查 Ollama 連接
curl http://localhost:11434/api/tags
```

### SoapVoice API 無回應
```bash
# 確認 API 啟動
curl http://localhost:8010/api/v1/health

# 檢查病患驗證端點
curl "http://localhost:8010/api/v1/patient/verify?name=王小明&birth_year=1990"
```

---

## 預期輸出 (完成標誌)

✅ **Phase 4 成功完成的跡象:**

1. AstrBot 啟動時無錯誤
2. 外掛日誌: `[INFO] ClinicCommunicationStar loaded successfully`
3. 模擬 webhook 請求回應 200 OK
4. SoapVoice API 日誌顯示患者驗證呼叫
5. LLM (Ollama) 日誌顯示模型推理
6. LINE webhook 反向驗證通過 (如有 LINE 整合)

---

## 下一步 (Phase 5)

- **工具函式完善**: 增強 5 個 LLM 工具的錯誤處理、prompt 優化
- **知識庫擴展**: 增加更多診所 FAQ、衛教資料
- **測試覆蓋**: 單元測試、集成測試、端到端測試
- **效能監控**: 添加指標、日誌追蹤、錯誤警報

---

**建立於**: 2026-04-30  
**預估完成時間**: 1-2 小時  
**技術棧**: FastAPI + AstrBot + Ollama + LINE Messaging API
