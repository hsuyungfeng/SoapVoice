# 🏥 SoapVoice 醫療語音轉 SOAP 系統

[![測試狀態](https://img.shields.io/badge/tests-105%20passed-green)]()
[![測試覆蓋率](https://img.shields.io/badge/coverage-85%25-green)]()
[![版本](https://img.shields.io/badge/version-1.8.0-blue)]()
[![授權](https://img.shields.io/badge/license-MIT-blue)]()

## 📖 專案說明

SoapVoice 是一套基於本地 LLM 的醫療語音轉 SOAP 病歷系統：

- 🎤 即時多語語音輸入（中文、英文）
- 🧠 AI 驅動的醫療語意標準化與術語專業化（100 個內建映射 + 80+ 術語）
- 📋 結構化 SOAP 病歷自動產出（英文，含 ICD-10 候選碼預填）
- 📊 ICD-10 診斷代碼映射與專科分類（96,802 代碼）
- 💊 藥務推薦與醫囑建議（12,042 藥品）
- 🏥 **整合疾病知識圖譜（8,807 疾病 + 294K 關係：症狀/藥品/飲食/檢查/科室/併發症）**
- 🔐 內網專用安全部署（API Key 認證）
- 🖥️ **支援 CLI 命令列介面**
- 🌐 **支援 Windows/Linux 離線部署（llama.cpp + Gemma 4 E4B 模型）**
- 🔗 **集成 doctor-toolbox.com（嵌入式 Widget + API）**

---

## 🎯 核心特性

### 四層架構
```
病歷語音/文字
    ↓
SOAP Generator (LLM 生成)
    ↓
LLM Database CLI (ICD-10、藥品、醫囑、疾病知識查詢)
    ↓
LocalDatabase (96,802 ICD-10 + 12,042 藥品 + 8,807 疾病 + 294K 醫療關係)
```

### 效能基準 (Gemma 4 E4B)
| 指標 | 結果 |
|------|------|
| **成功率** | 100% (5/5 醫療案例) |
| **平均生成時間** | 41.0 秒 |
| **吞吐量** | 6.7-7.8 tokens/秒 |
| **SOAP 長度** | 200-250 tokens |
| **硬體** | RTX 2080 Ti (22GB) / CPU (llama.cpp) |

---

## 🚀 快速開始

### 選項一：CLI（推薦，無需服務）

```bash
# 安裝依賴
uv sync

# 文字輸入生成 SOAP
uv run python src/cli_typer.py main --text "病人胸悶兩天伴呼吸困難"

# 使用 llama.cpp 後端（離線）
USE_LLAMA_CPP=true LLAMA_MODEL_PATH="models/gemma-4-E4B-it-Q4_K_M.gguf" \
uv run python src/cli_typer.py main --text "病人發燒"

# 列出可用模型
uv run python src/cli_typer.py models
```

**功能**：
- ✅ SOAP 病歷生成（英文）
- ✅ 術語標準化（100 個內建映射）
- ✅ ICD-10 分類（96,802 代碼）
- ✅ 藥物推薦（12,042 藥品）
- ✅ 醫囑建議（2,102 項目）
- ✅ 疾病知識圖譜（8,807 疾病 + 54K 症狀 + 74K 藥品 + 84K 飲食 + 39K 檢查 + 16K 科室 + 12K 併發症）
- ✅ RAG 病例範本檢索（1,665 範本）

### 選項二：API 伺服器

```bash
# 啟動 FastAPI 伺服器
uv run uvicorn src.main:app --host 0.0.0.0 --port 8010

# 確認服務健康
curl http://localhost:8010/api/v1/clinical/health

# 生成 SOAP
curl -X POST http://localhost:8010/api/v1/clinical/soap/generate \
  -H "Content-Type: application/json" \
  -d '{"transcript": "病人胸悶兩天"}'
```

---

## 📦 模型配置

### 推薦配置（Gemma 4 E4B）

```bash
# 使用環境變數
export USE_LLAMA_CPP=true
export LLAMA_MODEL_PATH="models/gemma-4-E4B-it-Q4_K_M.gguf"
export LLAMA_N_GPU_LAYERS=-1  # 全 GPU 卸載

uv run python src/cli_typer.py main --text "..."
```

| 模型 | 大小 | 用途 | 推薦 | 來源 |
|------|------|------|------|------|
| Gemma 4 E4B (Q4_K_M) | 9.6GB | SOAP 生成 | ⭐⭐⭐ 首選 | llama.cpp |
| Qwen2.5-7B (Q4_K_M) | 4.4GB | SOAP 生成 | ✅ 備用 | llama.cpp |
| qwen2.5:7b | 4.7GB | SOAP 生成 | ✅ 線上 | Ollama |

### 其他模型

**ASR（語音辨識）**:
- `faster-whisper-medium` - 繁體中文語音識別
- `whisper.cpp` - 離線版本

**OCR（螢幕截圖）**:
- `PaddleOCR-VL` - 繁體中文 + 英文
- `EasyOCR` - 離線備用

---

## 🔌 API 文件

### 基礎端點

| 端點 | 方法 | 說明 | 需要 API Key |
|------|------|------|-------------|
| `/health` | GET | 健康檢查 | ❌ |
| `/api/v1/clinical/health` | GET | 元件健康檢查 | ❌ |
| `/api/v1/clinical/normalize` | POST | 術語標準化 | ✅ |
| `/api/v1/clinical/icd10` | POST | ICD-10 分類 | ✅ |
| `/api/v1/clinical/soap/generate` | POST | SOAP 生成 | ✅ |
| `/api/v1/clinical/soap/generate-quick` | POST | SOAP 快速生成（嵌入式） | ✅ |

### SOAP 生成範例

```bash
# 完整 SOAP 生成
curl -X POST http://localhost:8010/api/v1/clinical/soap/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "transcript": "患者主訴胸痛三天，呼吸時加重...",
    "patient_context": {
      "age": "45",
      "gender": "M",
      "chief_complaint": "胸痛"
    }
  }'

# 快速生成（為 doctor-toolbox.com 設計）
curl -X POST http://localhost:8010/api/v1/clinical/soap/generate-quick \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"text": "患者發燒，體溫 38.5°C"}'
```

### 響應格式

```json
{
  "soap": {
    "subjective": "Patient reports...",
    "objective": "Vital signs...",
    "assessment": "Differential diagnosis...",
    "plan": "Diagnostic and treatment plan..."
  },
  "metadata": {
    "confidence": 0.92,
    "model_version": "gemma-4-e4b",
    "processing_time_ms": 41000,
    "icd10_codes": ["R07.9", "R07.1"],
    "medications": ["Ibuprofen 400mg", "..."]
  }
}
```

---

## 🔗 doctor-toolbox.com 集成

### 方式一：嵌入式 Widget

```html
<!-- 在 doctor-toolbox.com 頁面中嵌入 -->
<iframe 
  src="https://soapvoice.hospital.local/widget.html?apiKey=YOUR_API_KEY" 
  width="800" 
  height="600" 
  frameborder="0"
></iframe>
```

**Widget 功能**:
- 📝 支援文字輸入或貼上語音轉文字結果
- 📋 4 個分頁展示 SOAP (Subjective/Objective/Assessment/Plan)
- 📋 一鍵複製各個 SOAP 段落
- ⚡ 實時進度提示
- 🔐 API Key 從 URL 參數讀取

### 方式二：API 直接呼叫

```javascript
// JavaScript 中呼叫 SoapVoice API
const response = await fetch('https://soapvoice.hospital.local/api/v1/clinical/soap/generate-quick', {
  method: 'POST',
  headers: {
    'Content-Type': application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({
    text: "患者症狀描述"
  })
});

const data = await response.json();
console.log(data.soap.assessment);  // 評估段落
```

### 配置 API Key

```bash
# 在 SoapVoice 伺服器上設定
export SOAPVOICE_API_KEY="your-secure-key-here"
uv run uvicorn src.main:app --port 8010
```

---

## 💾 資料庫內容 (`data/local_db/medical.db`)

本系統使用整合了臨床知識圖譜、學術資料與疾病知識圖譜的 SQLite 資料庫 `medical.db`。

### 核心標準資料

| 資料表 | 記錄數 | 用途 | 來源 |
|--------|--------|------|------|
| `icd10_codes` | 96,802 | ICD-10 疾病分類 | 健保署標準 |
| `drugs` | 12,042 | 藥品資料（ATC 分類） | 健保署標準 |
| `medical_orders` | 2,102 | 醫療服務與診斷 | 健保署標準 |
| `case_templates` | 1,665 | SOAP 病例範本（RAG） | 自建 |

### 疾病知識圖譜（新增 v1.8.0）

| 資料表 | 記錄數 | 用途 |
|--------|--------|------|
| `disease_info` | 8,807 | 疾病描述、病因、預防、治療方式 |
| `disease_symptoms` | 54,710 | 疾病➜症狀對應（5,998 種症狀） |
| `disease_drugs` | 74,123 | 疾病➜藥品對應（3,828 種藥品） |
| `disease_foods` | 84,803 | 疾病➜飲食建議（4,870 種食物） |
| `disease_checks` | 39,531 | 疾病➜檢查項目（3,353 種檢查） |
| `disease_departments` | 16,783 | 疾病➜科室對應（54 個科室） |
| `disease_acompany` | 12,052 | 疾病➜併發症關係 |
| **小計** | **~282K 關係** | 整合自 [chatbot-base-on-Knowledge-Graph](https://github.com/baiyang2464/chatbot-base-on-Knowledge-Graph) |

### 臨床知識圖譜（自 clinic.db 同步）

| 資料表 | 用途 |
|--------|------|
| `medical_nodes` | 臨床醫學知識圖譜實體節點 |
| `medical_edges` | 臨床知識實體關聯邊 |
| `disease_details` | 疾病診斷特徵、症狀關聯 |
| `medical_terminology` | 臨床學術術語與日常口語對照表 |
| `medical_conditions` | 臨床適應症與用藥安全條件 |
| `medical_treatments` | 療程原理、修復期與處置細節 |
| `medical_guidelines` | 臨床指引與標準照護規範 |
| `medical_knowledge` | 醫學常識與知識庫 |

**動態查詢示例**:

```bash
# 查詢 ICD-10 代碼
uv run python -m src.cli_db_query query_icd10 "chest pain" --limit 5

# 查詢藥品
uv run python -m src.cli_db_query query_drugs "ibuprofen" --limit 5

# 查詢醫療服務
uv run python -m src.cli_db_query query_medical_orders "ECG" --limit 5

# 疾病知識查詢
uv run python -c "
from pathlib import Path
from src.db.local_database import LocalDatabase

db = LocalDatabase(Path('data/local_db/medical.db'))
profile = db.get_disease_profile('高血壓')
if profile:
    print(f'症狀: {profile.symptoms}')
    print(f'藥品: {profile.drugs}')
    print(f'宜吃: {profile.foods.get(\"do_eat\", [])}')
    print(f'忌吃: {profile.foods.get(\"not_eat\", [])}')
db.close()
"

# 資料庫統計
uv run python -m src.cli_db_query get_stats

# 疾病知識查詢
uv run python -c "
from pathlib import Path
from src.db.local_database import LocalDatabase
db = LocalDatabase(Path('data/local_db/medical.db'))
profile = db.get_disease_profile('高血壓')
if profile:
    print(f'症狀: {profile.symptoms}')
    print(f'藥品: {profile.drugs}')
db.close()
"
```

---

## 📁 專案結構

```
SoapVoice/
├── src/
│   ├── main.py                  # FastAPI 入口
│   ├── cli_typer.py             # Typer CLI 工具
│   ├── offline_server.py        # 離線伺服器
│   ├── api/                     # API 端點
│   │   ├── rest.py              # REST API
│   │   ├── extended_api.py      # 擴展 API
│   │   └── websocket.py
│   ├── soap/                    # SOAP 生成引擎
│   │   ├── soap_generator.py    # 核心生成器
│   │   └── prompt_builder.py
│   ├── llm/                     # LLM 引擎
│   │   ├── llama_engine.py      # llama.cpp 後端
│   │   └── ollama_engine.py     # Ollama 後端
│   ├── nlp/                     # NLP 處理
│   │   ├── terminology_mapper.py  # 術語映射
│   │   └── icd10_classifier.py
│   ├── db/                      # 資料庫
│   │   ├── local_database.py
│   │   └── llm_db_cli.py        # LLM 資料庫 CLI
│   └── asr/                     # 語音辨識
├── models/                      # GGUF 模型檔案
│   ├── gemma-4-E4B-it-Q4_K_M.gguf  # 主模型
│   └── qwen2.5-7B-Instruct-Q4_K_M.gguf
├── data/
│   ├── local_db/medical.db      # 本地醫療資料庫（含知識圖譜）
│   └── rag/                     # 病例範本
├── scripts/                     # 工具腳本
│   └── import_kg_data.py       # 疾病知識圖譜 ETL 匯入
├── static/                      # Web 前端
│   ├── index.html               # 主控制台
│   ├── widget.html              # doctor-toolbox.com Widget
│   ├── dashboard.html           # 分析儀表板
│   └── *.wav                    # 測試音檔
├── tests/                       # 測試套件
│   ├── test_soap.py
│   ├── test_llm_db_cli.py
│   └── ...
├── docs/                        # 文件
│   ├── API_INTEGRATION.md
│   ├── CLI_USAGE.md
│   ├── DEPLOYMENT.md
│   └── BENCHMARK_GUIDE.md
├── scripts/                     # 工具腳本
│   ├── import_kg_data.py       # 疾病知識圖譜 ETL 匯入
│   └── ...
├── benchmarks/                  # 效能基準
│   ├── E4B_SOAP_BENCHMARK_RECORD.md
│   └── GPUllmcompare.md
├── pyproject.toml              # UV 配置
└── README.md                   # 本檔案
```

---

## 🧪 測試

```bash
# 所有測試
uv run pytest tests/ -v

# 快速測試（不需模型）
uv run pytest tests/test_soap.py tests/test_llm_db_cli.py -v

# 帶覆蓋率
uv run pytest tests/ --cov=src --cov-report=html
```

---

## 🛠️ 技術棧

| 層次 | 技術 |
|------|------|
| API 框架 | FastAPI + uvicorn |
| LLM 推理 | llama.cpp（首選）/ Ollama（備用） |
| 語音辨識 | Faster-Whisper + whisper.cpp |
| NLP | 自建術語映射器 + ICD-10 分類器 |
| 向量資料庫 | Chroma DB + SQLite |
| 套件管理 | uv（Python） |
| 前端 | Vanilla JS + HTML5 |

---

## 🤝 DrtoolboxLocalServer 雙向整合升級

本專案已與 [DrtoolboxLocalServer](file:///home/hsuyungfeng/DrtoolboxLocalServer) 進行深度雙向整合，大幅提升 ASR 專科聽寫精準度與臨床合規性防護：

1. **ASR 詞彙熱度與詞典校正**
   * **機制**：將 `DrtoolboxLocalServer` 圖譜中的 2.6 萬個醫療實體節點（包含精準疾病、症狀、處置、藥物名稱）合併至本專案的 `keywords.json` 中。
   * **效果**：直接加載於 ASR 與術語對應中，防止專科醫學術語（如「琥乙紅黴素」）被辨識為日常生活詞彙。
2. **臨床處置與用藥合規防線 (Clinical Compliance Guard)**
   * **機制**：SOAP 模組加載 `DrtoolboxLocalServer` 的 `clinic.db`（內含 30 萬條臨床知識關係），在生成病歷時自動觸發 `ClinicalComplianceGuard`。
   * **效果**：自動比對診斷（Assessment）與計畫（Plan）中的用藥、醫囑與食物關係，如偵測到忌吃食物則發出 `CRITICAL` 警告，若使用推薦藥品則標註 `INFO` 通過，提供臨床防錯與決策輔助。

---

## 📄 授權

MIT License

---

## 🎓 參考資源

- **基準測試報告**: `benchmarks/E4B_SOAP_BENCHMARK_RECORD.md`
- **API 整合指南**: `docs/API_INTEGRATION.md`
- **CLI 使用**: `docs/CLI_USAGE.md`
- **部署指南**: `docs/DEPLOYMENT.md`
- **模型比較**: `benchmarks/GPUllmcompare.md`

---

**最後更新**: 2026-07-21
**版本**: 1.8.0
**核心模型**: Gemma 4 E4B (9.6GB, Q4_K_M)
**資料庫**: ICD-10 (96,802) + 疾病知識圖譜 (8,807 疾病, ~282K 關係) + clinic.db 臨床圖譜
**推薦部署**: llama.cpp + GPU 加速
