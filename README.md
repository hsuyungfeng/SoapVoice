# 🏥 SoapVoice 醫療語音轉 SOAP 系統

[![測試狀態](https://img.shields.io/badge/tests-105%20passed-green)]()
[![測試覆蓋率](https://img.shields.io/badge/coverage-85%25-green)]()
[![版本](https://img.shields.io/badge/version-1.7.0-blue)]()
[![授權](https://img.shields.io/badge/license-MIT-blue)]()

## 📖 專案說明

SoapVoice 是一套基於本地 LLM 的醫療語音轉 SOAP 病歷系統：

- 🎤 即時多語語音輸入（中文、英文）
- 🧠 AI 驅動的醫療語意標準化與術語專業化（73 個內建映射 + 80+ 術語）
- 📋 結構化 SOAP 病歷自動產出（含 ICD-10 候選碼預填）
- 📊 ICD-10 診斷代碼映射與專科分類
- 💊 藥物推薦與醫囑建議
- 🔐 內網專用安全部署
- 🖥️ **支援 CLI 命令列介面**
- 🌐 **支援離線部署（llama.cpp + GGUF 模型）**

## 🚀 快速開始

### 選項一：離線版本（推薦）

```bash
# 執行 Python
uv sync
uv run python src/offline_server.py
```

**開啟瀏覽器：http://localhost:8010**

### 選項二：線上版本（需要 Ollama）

```bash
# 1. 安裝依賴
uv sync

# 2. 安裝並啟動 Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen2.5:7b

# 3. 啟動 API 服務
uv run uvicorn src.main:app --host 0.0.0.0 --port 8010 --reload

# 4. 確認服務
curl http://localhost:8010/api/v1/clinical/health
```

---

## 📦 模型配置

### LLM 模型（SOAP 生成）

| 模型 | 大小 | 用途 | 推薦 |
|------|------|------|------|
| qwen2.5:7b | 4.7 GB | SOAP 生成 | ✅ 預設 |
| qwen2.5:3b | 1.9 GB | 快速推理 | ⭐ 輕量 |

### OCR 模型

| 模型 | 大小 | 用途 |
|------|------|------|
| glm-ocr | 2.2 GB | 螢幕截圖 OCR（預設） |

### ASR 模型

| 模型 | 大小 | 用途 |
|------|------|------|
| qwen2.5:3b | 1.9 GB | 語音轉文字 |
| faster-whisper | - | 備用語音辨識 |

---

## 🖥️ CLI 使用方式

```bash
# 文字輸入生成 SOAP
uv run python src/cli_typer.py main --text "病人咳嗽兩天有痰"

# 指定模型
uv run python src/cli_typer.py main --text "病人胸悶" --model qwen2.5:3b

# 啟動 API 伺服器
uv run python src/cli_typer.py serve

# 列出可用模型
uv run python src/cli_typer.py models
```

---

## 📦 API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/health` | GET | 健康檢查 |
| `/api/v1/clinical/normalize` | POST | 術語標準化 |
| `/api/v1/clinical/icd10` | POST | ICD-10 分類 |
| `/api/v1/clinical/soap/generate` | POST | SOAP 生成 |
| `/api/v1/extended/process` | POST | 擴展 SOAP（含症狀/ICD-10/醫囑/藥物） |

### SOAP 生成範例

```bash
# 使用 qwen2.5:3b
curl -X POST http://localhost:8010/api/v1/clinical/soap/generate \
  -H "Content-Type: application/json" \
  -d '{"transcript": "病人胸悶兩天伴隨呼吸困難", "model": "qwen2.5:3b"}'

# 使用 qwen2.5:7b
curl -X POST http://localhost:8010/api/v1/clinical/soap/generate \
  -H "Content-Type: application/json" \
  -d '{"transcript": "病人胸悶兩天伴隨呼吸困難", "model": "qwen2.5:7b"}'
```

---

## 💾 資料庫內容

| 資料表 | 記錄數 | 用途 |
|--------|--------|------|
| icd10_codes | 96,802 | ICD-10 疾病分類 |
| drugs | 12,042 | 藥品資料 |
| medical_orders | 2,102 | 醫療服務 |
| case_templates | 1,665 | 病例範本（RAG） |

---

## 🧪 測試

```bash
# 所有測試
uv run pytest tests/ -v

# 快速測試（不需模型）
uv run pytest tests/test_nlp.py tests/test_soap.py tests/test_init.py -v

# 帶覆蓋率
uv run pytest tests/ --cov=src --cov-report=html
```

---

## 🛠️ 技術棧

| 層次 | 技術 |
|------|------|
| API 框架 | FastAPI + uvicorn |
| 語音辨識 | Faster-Whisper |
| LLM | Ollama / llama.cpp |
| NLP | 自建術語映射器 + ICD-10 分類器 |
| 向量資料庫 | Chroma + SQLite |
| 套件管理 | uv |

---

## 📁 專案結構

```
SoapVoice/
├── src/
│   ├── main.py              # FastAPI 入口
│   ├── cli.py               # 舊版 CLI
│   ├── cli_typer.py         # Typer CLI
│   ├── offline_server.py    # 離線伺服器
│   ├── api/                 # API 端點
│   │   ├── rest.py
│   │   ├── extended_api.py
│   │   └── websocket.py
│   ├── asr/                 # 語音辨識
│   ├── nlp/                 # 自然語言處理
│   │   ├── terminology_mapper.py
│   │   ├── icd10_classifier.py
│   │   ├── soap_classifier.py
│   │   └── ocr_parser.py
│   ├── soap/                # SOAP 生成
│   ├── llm/                 # LLM 引擎
│   │   ├── ollama_engine.py
│   │   └── llamacpp_engine.py
│   └── db/                  # 資料庫
├── models/                  # GGUF 模型
│   ├── qwen2.5-3b-instruct-q4_k_m.gguf
│   ├── llama-cpp/           # Linux llama.cpp
│   └── windows/             # Windows 執行檔
├── data/
│   ├── local_db/medical.db
│   └── rag/case_templates.db
├── static/                  # Web 前端
├── tests/                   # 測試
├── docs/                   # 文件
│   └── archives/            # 歸檔文件
├── SoapVoice.spec          # PyInstaller 配置
├── docker-compose.yml      # Docker 部署
└── README.md
```

---

## 📄 授權

MIT License