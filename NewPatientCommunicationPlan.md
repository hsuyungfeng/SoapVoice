# 診所患者通訊系統整合方案

*Last updated: 2026-04-30*

## 核心願景

將 SoapVoice 從**醫生端醫療工具**轉變為**患者-醫療機構雙向通訊平台**，整合 LINE 訊息、本地 LLM、與既有病歷系統，為診所患者提供 24/7 自動衛教、掛號查詢、用藥說明與緊急狀況辨識，全程 LAN 本機運作，零雲端依賴。

---

## 整體架構

```
患者手機 (LINE App)
    │ HTTPS 通道
    ▼
LINE 訊息 API (雲端 webhook)
    │
    ▼ POST /api/platform/webhook/{uuid}
    │
┌───────────────────────────────────────────────────────────┐
│ AstrBot (port 6185)                                       │
│ /home/hsu/Desktop/SoapVoice/AstrBot/                      │
│                                                            │
│ ┌─────────────────────────────────────────────────────┐  │
│ │ LinePlatformAdapter (已實作)                          │  │
│ │ ClinicCommunicationStar 外掛                        │  │
│ │   ├─ @on_llm_request: 注入診所資訊+患者病歷         │  │
│ │   ├─ @filter.regex: 文字訊息路由                    │  │
│ │   ├─ @filter.event_message_type: 語音訊息路由       │  │
│ │   └─ @llm_tool: 工具函式集                          │  │
│ │       ├─ get_clinic_info()      診所資訊查詢        │  │
│ │       ├─ search_patient_records() 病歷搜尋          │  │
│ │       ├─ check_emergency_routing() 緊急轉介        │  │
│ │       ├─ get_disease_education() 疾病衛教          │  │
│ │       └─ link_line_user_to_patient() 身份連結      │  │
│ └─────────────────────────────────────────────────────┘  │
│       ↓                          ↓              ↓          │
└───────────────────────────────────────────────────────────┘
    │                              │              │
    ▼                              ▼              ▼
┌──────────────────┐  ┌──────────────────────┐  ┌──────────────────┐
│ Ollama           │  │ SoapVoice FastAPI    │  │ VibeVoice-ASR    │
│ port 11434       │  │ port 8010            │  │ port 8000        │
│                  │  │                      │  │ (未來擴展)        │
│ LLM 推理引擎      │  │ REST API endpoints:  │  │ vLLM 音檔轉文字   │
│ 選項:            │  │ /records/search      │  │ base64 audio → txt
│ • qwen3.6:27b    │  │ /records/{id}        │  │ (VIBEVOICE_      │
│ • medgemma:27b   │  │ /patient/verify (新) │  │  ENABLED=false)   │
│ • gemma4:26b     │  │ SQLite DB:           │  │                  │
│ ~15-17GB VRAM    │  │ soapvoice_records.db │  │ ~8.5GB VRAM      │
└──────────────────┘  └──────────────────────┘  └──────────────────┘
         ↓                         ↓                        ↓
    RTX 2080 Ti 22GB VRAM 共用基礎設施
```

---

## GPU 記憶體配置策略

### 目前配置 (VibeVoice 延後)

**RTX 2080 Ti 22GB**
- Ollama LLM 伺服器: ~15-17GB (27B 模型 Q4_K_M 量化)
- 系統 + 緩衝: ~3-5GB

### 未來擴展 (加購第二張 GPU 卡)

當採購第二張 GPU 時：
- **2080 Ti**: 專供 Ollama LLM (~17GB)
- **新卡 (如 3060 12GB)**: VibeVoice-ASR-7B (~8.5GB) via vLLM
- 外掛程式已預留 `VIBEVOICE_ENABLED` 特性旗標，等待啟動

---

## LLM 模型選擇

使用 **A/B 測試方法** 評估三個候選模型在診所環境的表現:

| 模型 | VRAM | 特色 | 評估指標 |
|------|------|------|----------|
| **qwen3.6:27b** | ~16GB | 青雲 3 原生，中文醫療領域強 | 中文醫學準確度 ⭐⭐⭐⭐⭐ |
| **medgemma:27b** | ~16GB | Google 醫療領域微調版 | 衛教回覆品質、副作用列舉準確度 |
| **gemma4:26b** | ~14-15GB | Gemma 4 通用推理，速度快 | 回應延遲、多語言支援 |

### 評估流程

1. 準備 20 題測試問卷 (覆蓋掛號、用藥、衛教、緊急)
2. 各模型執行相同測試集
3. 評分維度:
   - 準確度 (診所資訊、衛教內容)
   - 反應時間 (秒數)
   - 繁體中文自然度
   - 安全性 (是否誤診、是否超出範圍)
4. 選擇總分最高的模型作為生產環境預設

### 啟用指令

```bash
# 拉取模型
ollama pull qwen3.6:27b
ollama pull medgemma:27b
ollama pull gemma4:26b

# 測試模型
ollama run qwen3.6:27b "你是診所助理，患者問掛號時間"

# 切換模型 (編輯 AstrBot cmd_config.json 中 provider.model_name)
```

---

## 核心功能流程

### 流程 1: 診所資訊查詢

```
患者: "請問你們禮拜一到五都幾點開診？"

→ route_message() 路由至 LLM
→ inject_context() 自動注入 clinic_info.json (每次請求)
→ LLM 識別查詢意圖
→ LLM 呼叫 get_clinic_info(info_type="hours")
→ 工具回傳 JSON 格式診所時間
→ LLM 轉換為自然繁體中文回覆
→ "我們禮拜一到五的看診時間為 08:30-12:00、14:00-17:30..."
```

**設計理由**
- 診所資訊每次都注入到系統提示詞 (~500 tokens)，避免 LLM 幻覺
- 工具函式確保數據一致性
- JSON 存放在 `clinic_info.json`，方便診所人員線上編輯

---

### 流程 2: 用藥副作用說明

```
患者: "我在吃的氨氯地平，有什麼副作用我要注意的？"

→ route_message() 路由至 LLM
→ LLM 識別「氨氯地平」(鈣通道阻斷劑)
→ LLM 呼叫 get_disease_education(condition="氨氯地平")
→ 工具回傳結構化衛教提示詞，含:
   - 常見副作用 (臉潮紅、踝部水腫、心跳加速)
   - 何時應回診 (超過 XX 狀況)
   - 日常照護提醒
   - 禁止項: 無具體劑量、無替代方案、無停藥建議
→ LLM 以患者友善語氣回覆衛教內容

回覆例: "氨氯地平是降血壓藥，常見副作用有：
1) 臉潮紅（20-30% 患者）- 通常 1-2 週後改善
2) 踝部水腫（5-10% 患者）- 請多抬腿休息
3) 頭暈（10% 患者）- 避免快速起身
如果超過 1 個月未改善，或出現其他症狀，請回診諮詢醫生。"
```

**設計理由**
- 衛教內容由 LLM 動態生成，但受限於 `get_disease_education()` 提示詞框架
- 框架內建禁止項 (無劑量、無自行停藥建議)，防止誤導患者
- 患者友善語言，鼓勵患者回診

---

### 流程 3: 緊急狀況辨識與轉介

```
患者: "我爸爸突然胸痛很嚴重，有點喘不過氣，該怎麼辦？"

→ route_message() 路由至 LLM
→ 系統提示詞已包含 emergency.json 關鍵字列表
→ LLM 辨識關鍵字: "胸痛"、"喘不過氣" → 高危警報
→ LLM 主動呼叫 check_emergency_routing(
    symptom_description="胸痛很嚴重 喘不過氣"
  )
→ 工具函式掃描 emergency.json 關鍵字列表
→ 觸發 EMERGENCY_DETECTED
→ LLM 優先回覆 (無延遲):
   "⚠️  請立即撥打 119！
   胸痛合併呼吸困難可能是心臟、肺部或其他緊急狀況。
   不要等待，馬上叫救護車。
   
   如在台北市，可聯絡:
   - 119 (全國緊急)
   - XX 醫院急診: 02-XXXX-XXXX"

→ 系統同時記錄此訊息為「緊急事件」，方便診所事後追蹤
```

**設計理由**
- 緊急關鍵字硬編碼在 `emergency.json`，不依賴 LLM 判斷
- `check_emergency_routing()` 是關鍵防護層，確保不遺漏高危症狀
- LLM 接到 EMERGENCY_DETECTED 信號後，立即優先回覆 119 建議
- 關鍵字涵蓋最常見的緊急症狀 (胸痛、呼吸困難、中風、喪失意識等)

---

### 流程 4: 患者身份連結與病歷查詢

```
患者 (首次使用): "我想查我上次看診的記錄"

→ route_message() 路由至 LLM
→ inject_context() 檢查 line_patients.db 中是否有連結記錄
→ 無連結 → LLM 回覆:
   "您好！為了保護您的隱私，查詢就診記錄需要先完成身份驗證。
   請提供您的姓名和出生年份。
   例如: 王小明，1980"

患者: "王小明，1975年"

→ LLM 辨識患者意圖
→ LLM 呼叫 link_line_user_to_patient(
    patient_name="王小明", 
    birth_year="1975"
  )
→ 工具函式執行:
   1. POST http://localhost:8010/api/v1/patient/verify?name=王小明&birth_year=1975
   2. SoapVoice 回傳 {verified: true, patient_id: 123}
   3. 在 line_patients.db 寫入:
      line_user_id (LINE Uxxxxxxxx) 
      ↔ patient_record_id (123) 
      + consent_given = 1
→ LLM 回覆:
   "身份驗證完成，王先生。您的 LINE 帳號已連結至病患記錄。
   之後可直接查詢就診摘要。"

患者 (後續): "我血壓最近怎麼樣？"

→ route_message() 路由至 LLM
→ inject_context() 找到已連結的患者 (王小明)
→ 自動搜尋最近 2 筆就診摘要:
   [就診摘要] 2026-04-15 Dr. 陳: 高血壓追蹤，血壓 140/88，控制良好
   [就診摘要] 2026-03-01 Dr. 陳: 高血壓初診，ASA、ACEI 已開立
→ 系統提示詞包含患者病歷上下文
→ LLM 回覆:
   "王先生，根據您上次 (4/15) 的就診記錄，
   您的血壓控制得很好 (140/88)。
   Dr. 陳建議持續監測...
   如血壓超過 160/100，請盡快回診。"
```

**隱私設計**
- LINE userId 永遠不存入 SoapVoice 醫療 DB
- 身份驗證透過 `GET /patient/verify` 端點，僅返回 `{verified, patient_id}`
- 病歷查詢返回**摘要** (就診日期、醫生、評估前 100 字)，不返回完整逐字稿
- 患者對應表存放在外掛專屬 SQLite (`line_patients.db`)，與醫療資料庫完全隔離
- 同意標記 (`consent_given = 1`) 確保查詢前已取得患者明確同意

---

### 流程 5: 掛號資訊查詢

```
患者: "怎麼掛號？要等多久？"

→ LLM 自動注入 clinic_info.json 中的掛號說明
→ LLM 呼叫 get_clinic_info(info_type="all")
→ 回覆包含:
   - 掛號方式 (電話、現場、線上 [若有])
   - 掛號電話號碼
   - 現場掛號時間段
   - 平均等待時間 (若有統計)
```

---

### 流程 6: 語音訊息轉文字與回覆 (未來擴展)

```
患者: [錄製 20 秒語音訊息說明症狀]

(啟動條件: VIBEVOICE_ENABLED=true + 第二張 GPU 卡)

→ route_message() 偵測 Record 元件
→ vibevoice_client.transcribe(audio_bytes)
   POST http://localhost:8000/v1/chat/completions
   payload: {model: "VibeVoice-ASR", audio_url: "data:audio/m4a;base64,..."}
   返回: "我最近頭痛很嚴重，已經持續 3 天了，也有點噁心..."
→ request_llm(prompt=f"[患者語音轉文字]: {transcript}")
→ 後續流程同常規文字訊息 (進入流程 1-5)
```

---

## 檔案結構與實作清單

### 新建檔案清單

#### AstrBot 外掛

```
AstrBot/data/plugins/clinic_communication/
├── __init__.py              (空即可，Python 套件標記)
├── main.py                  (★ 核心: ClinicCommunicationStar)
├── soapvoice_client.py      (async HTTP 包裝器，呼叫 /records/search 等)
├── vibevoice_client.py      (async HTTP 包裝器，vLLM /v1/chat/completions)
├── patient_mapper.py        (SQLite 管理: LINE userId ↔ patient_id)
├── knowledge_base.py        (載入 JSON 知識庫，提供查詢介面)
└── metadata.yaml            (AstrBot 外掛後設資料)

AstrBot/data/plugin_data/clinic_communication/
├── clinic_info.json         (診所名稱、電話、地址、時間、服務項目)
├── emergency.json           (119 轉介關鍵字列表 + 路由訊息)
└── faq.json                 (常見問題 Q&A 對)
```

#### SoapVoice 修改

```
src/api/patient_records_api.py  (新增 GET /api/v1/patient/verify 端點)
```

---

## 實作步驟 (執行序)

### Phase 1: 基礎環境 (1-2 小時)

#### 步驟 1.1 - 拉取 LLM 模型

```bash
# 在 GPU 伺服器上執行
ollama pull qwen3.6:27b     # ~18GB 下載，Q4_K_M 量化
ollama pull medgemma:27b    # ~18GB 下載
ollama pull gemma4:26b      # ~15GB 下載

# 驗證
ollama list
curl http://localhost:11434/api/tags
```

#### 步驟 1.2 - 驗證 SoapVoice 執行中

```bash
cd /home/hsu/Desktop/SoapVoice
# (若尚未啟動)
uvicorn src.main:app --host 0.0.0.0 --port 8010 &

# 驗證
curl http://localhost:8010/health
curl http://localhost:8010/api/v1/health
```

---

### Phase 2: SoapVoice 修改 (30 分鐘)

#### 步驟 2.1 - 新增身份驗證端點

編輯 `src/api/patient_records_api.py`:

```python
from fastapi import APIRouter, HTTPException, Depends

router = APIRouter(prefix="/api/v1", tags=["patient_records"])

@router.get("/patient/verify")
async def verify_patient_identity(
    name: str = Query(..., min_length=1),
    birth_year: str = Query(..., regex=r"^\d{4}$")
):
    """
    身份驗證端點 (LINE 患者帳號連結用)
    
    僅返回 {verified, patient_id}，不洩露病歷內容
    """
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id FROM patient_records 
            WHERE name = ? AND birth_date LIKE ?
            LIMIT 1
            """,
            (name, f"{birth_year}%")
        )
        row = await cursor.fetchone()
    
    if row:
        return {"verified": True, "patient_id": row[0]}
    else:
        return {"verified": False, "patient_id": None}
```

#### 步驟 2.2 - 測試新端點

```bash
curl "http://localhost:8010/api/v1/patient/verify?name=王小明&birth_year=1975"
# 預期回應: {"verified": true, "patient_id": 123}
```

---

### Phase 3: AstrBot 外掛開發 (4-6 小時)

#### 步驟 3.1 - 建立外掛目錄結構

```bash
cd /home/hsu/Desktop/SoapVoice/AstrBot

mkdir -p data/plugins/clinic_communication
mkdir -p data/plugin_data/clinic_communication

touch data/plugins/clinic_communication/__init__.py
touch data/plugins/clinic_communication/main.py
touch data/plugins/clinic_communication/soapvoice_client.py
touch data/plugins/clinic_communication/vibevoice_client.py
touch data/plugins/clinic_communication/patient_mapper.py
touch data/plugins/clinic_communication/knowledge_base.py
touch data/plugins/clinic_communication/metadata.yaml
```

#### 步驟 3.2 - 編寫核心檔案

**main.py** - 主星類 (★ 優先完成此項)

包含內容:
- `ClinicCommunicationStar` 類
- `initialize()` - 初始化 DB + 載入知識庫
- `@filter.on_llm_request()` - 注入診所 + 患者上下文
- `@filter.event_message_type(ALL)` - 訊息路由
- `@filter.llm_tool()` x 5 - 工具函式:
  - `get_clinic_info()`
  - `search_patient_soap_records()`
  - `check_emergency_routing()`
  - `get_disease_education()`
  - `link_line_user_to_patient()`

**soapvoice_client.py**

封裝 HTTP 呼叫:
- `search_records(name, limit)` → GET /api/v1/records/search
- `get_record(record_id)` → GET /api/v1/records/{id}
- `verify_patient(name, birth_year)` → GET /api/v1/patient/verify

**vibevoice_client.py**

封裝 VibeVoice vLLM 呼叫 (特性旗標):
- `transcribe(audio_bytes)` → POST /v1/chat/completions (base64 audio)

**patient_mapper.py**

SQLite 管理:
- 表: `line_patient_mapping` (line_user_id, patient_record_id, consent_given)
- 方法: `get_patient_id()`, `link_patient()`, `check_consent()`

**knowledge_base.py**

載入 JSON 並提供查詢:
- `load_clinic_info()` → dict
- `load_emergency_keywords()` → list
- `load_faq()` → list[dict]

#### 步驟 3.3 - 編寫知識庫 JSON 檔案

**clinic_info.json**

```json
{
  "name": "康健診所",
  "phone": "02-1234-5678",
  "address": "台北市松山區民權東路 100 號",
  "hours": {
    "weekday": "08:30-12:00, 14:00-17:30, 18:00-20:00",
    "saturday": "08:30-12:00",
    "sunday": "休診",
    "holiday": "依政府公告"
  },
  "services": [
    "一般內科",
    "兒科",
    "家庭醫學科",
    "預防接種",
    "健康檢查",
    "慢性病管理"
  ],
  "appointment_note": "請致電掛號或現場掛號",
  "insurance": "接受健保，自費項目請洽詢"
}
```

**emergency.json**

```json
{
  "keywords": [
    "胸痛", "心臟", "心肌梗塞",
    "呼吸困難", "喘不過氣", "哮喘發作",
    "中風", "口齒不清", "肢體無力",
    "暈厥", "失去意識", "意識不清",
    "嚴重過敏", "過敏休克",
    "大量出血", "傷口無法止血",
    "骨折", "脊椎傷害",
    "抽搐", "癲癇發作",
    "自殺", "自傷", "極端行為"
  ],
  "action": "立即撥打 119 或前往急診室。診所非緊急救護機構。",
  "hospital_er": {
    "name": "台北馬偕醫院",
    "phone": "02-2543-3535",
    "address": "台北市中山區民族東路 2 號"
  }
}
```

**faq.json**

```json
[
  {
    "q": "如何掛號？",
    "a": "可致電 02-1234-5678 或現場掛號。詳見診所時間表。"
  },
  {
    "q": "健保如何給付？",
    "a": "一般門診健保部分負擔 50 元；慢性病連續處方箋優惠。"
  },
  {
    "q": "第一次就診需帶什麼？",
    "a": "請帶健保卡、身份證、及過去病歷 (若有)。"
  }
]
```

---

### Phase 4: AstrBot 組態與啟動 (1 小時)

#### 步驟 4.1 - 設定 cmd_config.json

編輯 `AstrBot/data/cmd_config.json`:

```json
{
  "platform": [
    {
      "id": "line-clinic",
      "type": "line",
      "enable": true,
      "channel_access_token": "<取自 LINE Developers Console>",
      "channel_secret": "<取自 LINE Developers Console>",
      "webhook_uuid": "<AstrBot 儀表板自動生成>"
    }
  ],
  "provider": [
    {
      "id": "local-llm",
      "type": "openai_chat_completion",
      "enable": true,
      "api_base": "http://127.0.0.1:11434/v1",
      "api_key": "ollama",
      "model_name": "qwen3.6:27b",
      "enable_function_calling": true,
      "temperature": 0.3,
      "max_tokens": 512
    }
  ]
}
```

#### 步驟 4.2 - 啟動 AstrBot

```bash
cd /home/hsu/Desktop/SoapVoice/AstrBot
uv run main.py

# 預期日誌:
# INFO: AstrBotCoreLifecycle initialized
# INFO: PluginManager loaded clinic_communication
# INFO: Dashboard listening on http://localhost:6185
```

#### 步驟 4.3 - 驗證外掛已載入

開啟瀏覽器訪問 `http://localhost:6185`，在外掛列表中應看到 `clinic_communication` 標記為 `已啟用`。

---

### Phase 5: 公開 Webhook 與註冊 (1 小時)

#### 步驟 5.1 - 曝露 AstrBot 至公網

使用 **Cloudflare Tunnel** (推薦，免費，無需設定埠轉發):

```bash
# 安裝 cloudflared (若未安裝)
# 參考 https://developers.cloudflare.com/cloudflare-one/connections/connect-applications/install-and-setup/

cloudflared tunnel --url http://localhost:6185

# 輸出例:
# 2026-04-30 10:30:00 INF Your quick tunnel has been created! Visit it at (this 
# URL will be valid for 3 hours):
#
# https://abc123-tranquil-frost.trycloudflare.com

# (複製此 URL)
```

#### 步驟 5.2 - 在 LINE Developers Console 註冊 Webhook

1. 開啟 https://developers.line.biz/console/
2. 登入並選擇診所對應的 Messaging API 頻道
3. 點選「Messaging API」分頁
4. 找到「Webhook」設定區域
5. 在「Webhook URL」欄位貼上:
   ```
   https://<cloudflare-domain>/api/platform/webhook/<webhook-uuid>
   ```
   其中 `<webhook-uuid>` 從 AstrBot 儀表板「LINE 平台」卡片查詢
6. 點「驗證」— 應返回 HTTP 200
7. 開啟「使用 Webhook」開關
8. 關閉「自動回覆訊息」(讓 AstrBot 全權處理)
9. 儲存設定

#### 步驟 5.3 - 測試 Webhook 連線

在 AstrBot 儀表板的 LINE 平台卡片，點「測試 Webhook」，應收到 `HTTP 200 OK`。

---

### Phase 6: 端到端測試 (1-2 小時)

#### 測試用例清單

| 測試案例 | 輸入 | 預期輸出 |
|---------|------|---------|
| 診所時間 | "禮拜一幾點開?" | 診所時間表 (自 clinic_info.json) |
| 掛號方式 | "怎麼掛號" | 電話 + 現場掛號說明 |
| 用藥副作用 | "高血壓藥有什麼副作用" | 患者友善衛教，無具體劑量 |
| 緊急狀況 | "我突然胸痛喘不過氣" | 立即 119 路由建議 |
| 身份連結 | "我想查我的病歷" → "王小明，1975" | 身份驗證 → 連結成功訊息 |
| 患者查詢 | (已連結後) "我血壓最近如何" | 個人化回覆，含上次就診摘要 |

#### 測試執行

```bash
# 用另一台手機加入診所 LINE 官方帳號，逐一發送上述測試訊息
# 在 AstrBot 儀表板的「聊天」分頁觀看完整對話記錄與系統日誌
# 若回覆異常，檢查:
# - Ollama 是否仍執行 (curl http://localhost:11434/api/tags)
# - SoapVoice 是否仍執行 (curl http://localhost:8010/health)
# - 外掛日誌 (AstrBot 儀表板 → logs)
```

---

### Phase 7: LLM A/B 測試與選型 (2-4 小時)

準備 20 題標準測試集 (儘可能涵蓋診所常見問題):

```
[測試 1] "你們禮拜日開嗎"
[測試 2] "請問掛號要多少錢"
[測試 3] "我在吃的阿司匹靈，停藥會不會危險"
[測試 4] "我忽然頭暈心跳很快，該怎麼辦"
[測試 5] "我想查上次看診的結果"
... (共 20 題)
```

執行流程:
1. 切換 `model_name` 為 `qwen3.6:27b`，執行 20 題，評分
2. 重啟 Ollama，切換 `model_name` 為 `medgemma:27b`，執行相同 20 題，評分
3. 重啟，測試 `gemma4:26b`，評分
4. 匯總得分，選擇最高者

評分維度 (每項 0-10):
- **準確度** - 回覆是否符合事實、無幻覺
- **安全性** - 是否避免診斷、超出範圍
- **中文自然度** - 措辭流暢度
- **反應時間** - 秒數 (< 2 秒為優)
- **繁體支援** - 是否使用繁體而非簡體

選定獲勝模型，更新 `cmd_config.json` 並重新啟動 AstrBot。

---

## 隱私與安全設計

### 隱私保護措施

| 風險 | 防護機制 |
|------|----------|
| LINE userId 外洩 | 永不存入 SoapVoice 醫療 DB；僅存於外掛隔離 SQLite |
| 身份盜用 | 身份驗證需姓名 + 出生年份；`verify_patient` API 只回傳布林值 |
| 病歷過度暴露 | 查詢結果限制為日期、醫生、評估摘要 (100 字)，永不返回完整逐字稿 |
| 未授權查詢 | `consent_given` 旗標強制確認；查詢前必須通過身份連結流程 |
| 資料庫混汙 | 外掛擁有獨立 SQLite (`line_patients.db`)，與醫療 DB 完全分隔 |

### 安全建議

- **診所須知**: 使用診所官方 LINE 帳號，定期驗證公開 webhook URL 仍有效
- **患者提示**: 首次對話時，自動提醒患者「本系統保護您的隱私，僅醫療相關資訊會被查詢」
- **稽核日誌**: 未來可在 `line_patients.db` 中加入 `verified_at`, `queried_at` 時戳，供診所稽核

---

## 常見問題與故障排除

### Q: 外掛載入失敗

**症狀**: AstrBot 儀表板中看不到 clinic_communication

**排除步驟**:
1. 檢查目錄結構是否正確 (`data/plugins/clinic_communication/main.py` 存在)
2. 檢查 `main.py` 中 `@star.register()` 裝飾器是否存在
3. 檢查 Python 語法無誤 (`python -m py_compile data/plugins/clinic_communication/main.py`)
4. 檢查 AstrBot 日誌中的導入錯誤

### Q: LLM 回覆速度慢 (> 5 秒)

**症狀**: 患者訊息後延遲 > 5 秒才收到回覆

**原因**: 
- Ollama 模型過大、VRAM 不足、CPU 執行中
- 網路延遲
- LLM 生成長篇回覆

**解決**:
- 檢查 `nvidia-smi` 中 Ollama 進程的 VRAM 使用是否達到上限
- 調低 LLM `temperature` (更快收斂)、`max_tokens` (回覆更短)
- 使用更小的模型 (如 gemma4:26b)

### Q: Webhook 驗證失敗 (Cloudflare)

**症狀**: LINE Developers Console 顯示「Webhook 驗證失敗」

**排除步驟**:
1. 檢查 AstrBot 是否執行中 (`curl http://localhost:6185/`)
2. 檢查 Cloudflare Tunnel 是否執行中 (`cloudflared status`)
3. 測試 tunnel URL 直接存取 (`curl https://<domain>/health`)
4. 檢查 LINE 秘鑰是否正確複製 (無多餘空白)

### Q: 患者身份驗證總是失敗

**症狀**: `link_line_user_to_patient` 總是返回 LINK_FAILED

**排除步驟**:
1. 檢查 SoapVoice `/patient/verify` 端點是否返回預期結果:
   ```bash
   curl "http://localhost:8010/api/v1/patient/verify?name=王小明&birth_year=1975"
   ```
2. 確認 `patient_records` 表中確實存有相符的患者記錄
3. 檢查患者姓名是否完全匹配 (忽視大小寫或特殊符號差異)

---

## 未來擴展路線圖

### 短期 (1-3 個月)

- [ ] 新增 `book_appointment()` 工具 (與診所掛號系統整合)
- [ ] 新增 `check_medication_interaction()` 工具 (藥物交互作用檢查)
- [ ] 精進緊急關鍵字檢測 (定期更新 emergency.json)
- [ ] 多語言支援 (英文、簡體中文)

### 中期 (3-6 個月)

- [ ] VibeVoice-ASR 整合 (語音訊息 → 文字轉譯)
- [ ] 推播功能 (醫生開立衛教後主動推播患者)
- [ ] 回診提醒 (定期推播慢性病患者回診時程)

### 長期 (6-12 個月)

- [ ] 多診所支援 (一個 AstrBot 實例服務多家診所)
- [ ] 與院所管理系統整合 (掛號系統、電子病歷)
- [ ] 機器學習模型微調 (針對診所常見問題優化回應品質)

---

## 結論

本方案提供完整的患者-診所溝通平台，將既有的 SoapVoice 醫療工具擴展為雙向互動系統。透過本地 LLM、LINE 訊息、與隔離的患者資料管理，為診所打造 24/7 自動化衛教與掛號服務，同時維護患者隱私與資訊安全。系統可漸進式擴展，未來加入語音辨識、推播、與院務系統整合。

**首要任務**: 完成 Phase 1-6 (環境 → 外掛開發 → webhook 註冊 → 測試)，選定最佳 LLM 模型。預計 1-2 週完成 MVP，之後持續優化與擴展功能。
