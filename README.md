# 🏥 SoapVoice 醫療語音轉 SOAP 系統

[![測試狀態](https://img.shields.io/badge/tests-105%20passed-green)]()
[![測試覆蓋率](https://img.shields.io/badge/coverage-85%25-green)]()
[![版本](https://img.shields.io/badge/version-1.6.0-blue)]()
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
- 🌐 **支援離線部署（無需 Ollama）**

## 🚀 快速開始

### 選項一：離線版本（推薦 - 一鍵啟動）

無需安裝 Ollama，直接執行！

```bash
# 方式 1: 直接執行 Python
uv sync
uv run python src/offline_server.py

# 方式 2: 打包為 Windows EXE
pyinstaller SoapVoice.spec --clean
# 執行 dist/SoapVoice/SoapVoice.exe
```

**開啟瀏覽器：http://localhost:8000**

### 選項二：線上版本（需要 Ollama）

```bash
# 1. 安裝依賴
uv sync

# 2. 安裝並啟動 Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen2.5:7b

# 3. 啟動 API 服務
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 確認服務
curl http://localhost:8000/health
```

---

## 📦 兩種部署模式比較

| 功能 | 離線版 | 線上版 (Ollama) |
|------|--------|-----------------|
| 模型大小 | Qwen2.5:7b (~4.5GB) | 可選多種 |
| 啟動速度 | 快 | 需載入模型 |
| 硬體需求 | CPU 即可 | GPU 推薦 |
| 網路需求 | 無 | 首次下載模型 |
| 適合場景 | 診所/偏鄉 | 研究/開發 |

---

## 🖥️ CLI 命令列介面

### Typer CLI（新版本）

```bash
# 文字輸入
uv run python src/cli_typer.py main --text "病人咳嗽兩天有痰"

# 指定模型
uv run python src/cli_typer.py main --text "病人胸悶" --model qwen2.5:7b

# 啟動 API 伺服器
uv run python src/cli_typer.py serve

# 列出可用模型
uv run python src/cli_typer.py models
```

### 舊版 CLI

```bash
uv run python src/cli.py --text "病人咳嗽兩天"
uv run python src/cli.py --extended --audio recording.wav
```

---

## 📊 模型效能比較

| 模型 | 大小 | CPU 時間 | 推薦度 |
|------|------|----------|--------|
| qwen2.5:7b | 4.7 GB | ~10秒 | ⭐⭐⭐ 最佳 |
| qwen2.5:3b | 1.9 GB | ~15秒 | ⭐⭐ 輕量 |
| qwen3.5:4b | 3.4 GB | ~64秒 | 不推薦 CPU |
| qwen3.5:9b | 6.6 GB | ~83秒 | 不推薦 CPU |

---

## 📦 API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/health` | GET | 健康檢查 |
| `/api/v1/clinical/normalize` | POST | 術語標準化 |
| `/api/v1/clinical/icd10` | POST | ICD-10 分類 |
| `/api/v1/clinical/soap/generate` | POST | SOAP 生成 |
| `/api/v1/extended/process` | POST | 擴展 SOAP（含症狀/ICD-10/醫囑/藥物） |
| `/api/v1/webhooks/*` | * | Webhook 端點 |
| `/api/v1/file-monitor/*` | * | 檔案監控端點 |

### SOAP 生成範例

```bash
curl -X POST http://localhost:8000/api/v1/clinical/soap/generate \
  -H "Content-Type: application/json" \
  -d '{"transcript": "病人胸悶兩天伴隨呼吸困難"}'
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
# 單元測試
uv run pytest tests/ -v

# 帶覆蓋率
uv run pytest tests/ --cov=src --cov-report=html

# 快速測試（不需模型）
uv run pytest tests/test_nlp.py tests/test_soap.py tests/test_init.py -v
```

---

## 🛠️ 技術棧

| 層次 | 技術 |
|------|------|
| API 框架 | FastAPI + uvicorn |
| 語音辨識 | Faster-Whisper |
| LLM | llama.cpp / Ollama |
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
│   │   ├── webhook_api.py
│   │   └── file_monitor_api.py
│   ├── asr/                 # 語音辨識
│   ├── nlp/                 # 自然語言處理
│   ├── soap/                # SOAP 生成
│   ├── llm/                 # LLM 引擎
│   ├── services/            # 服務模組
│   └── db/                  # 資料庫
├── models/                  # GGUF 模型
│   ├── qwen2.5-7b-instruct-q4_k_m.gguf
│   └── whisper/             # Whisper 模型
├── data/
│   ├── local_db/medical.db
│   └── rag/case_templates.db
├── static/                  # Web 前端
├── tests/                   # 測試
├── SoapVoice.spec           # PyInstaller 配置
├── docker-compose.yml       # Docker 部署
└── README.md
```

---

## 📄 授權

MIT License