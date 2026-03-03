# 🏥 SoapVoice 醫療語音轉 SOAP 系統

[![測試狀態](https://img.shields.io/badge/tests-92%20passed-green)]()
[![測試覆蓋率](https://img.shields.io/badge/coverage-85%25-green)]()
[![版本](https://img.shields.io/badge/version-0.9.0-blue)]()
[![授權](https://img.shields.io/badge/license-MIT-blue)]()

## 📖 專案說明

SoapVoice 是一套基於本地 LLM 的醫療語音轉 SOAP 病歷系統，實現：

- 🎤 即時多語語音輸入（中文、英文）
- 🧠 AI 驅動的醫療語意標準化與術語專業化
- 📋 結構化 SOAP 病歷自動產出
- 📊 ICD-10 診斷代碼映射與專科分類
- 🔐 內網專用安全部署（192.168.x.x）

## 🚀 快速開始

### 開發環境

```bash
# 1. 克隆專案
git clone https://github.com/your-org/soapvoice.git
cd soapvoice

# 2. 安裝依賴
uv sync

# 3. 啟動服務
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000

# 4. 訪問 API 文件
open http://localhost:8000/docs
```

### 生產環境

```bash
# 1. 複製環境配置
cp .env.example .env

# 2. 編輯環境配置
vim .env

# 3. 啟動 Docker 服務
docker compose -f docker-compose.prod.yml up -d

# 4. 驗證部署
./scripts/deploy_verify.sh
```

## 📦 主要功能

### API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/health` | GET | 服務健康檢查 |
| `/api/v1/clinical/normalize` | POST | 醫療文本標準化 |
| `/api/v1/clinical/icd10` | POST | ICD-10 代碼分類 |
| `/api/v1/clinical/classify/soap` | POST | SOAP 分類 |
| `/api/v1/clinical/soap/generate` | POST | SOAP 病歷生成 |

### 模型配置

| 模型 | 用途 | 大小 |
|------|------|------|
| qwen3.5:35b | 主推理模型 | 23GB |
| qwen3.5:27b | 備用模型 | 17GB |
| glm-4.7-flash | 快速推理 | 19GB |
| faster-whisper large-v3 | 語音辨識 | 6GB |

## 🧪 測試

```bash
# 單元測試
uv run pytest tests/ -v

# 測試覆蓋率
./scripts/test_coverage.sh

# 負載測試
uv run locust -f scripts/load_test.py --host=http://localhost:8000

# 端到端測試
uv run python scripts/test_e2e.py

# Beta 測試
./scripts/run_beta_test.sh
```

## 📚 文件

| 文件 | 說明 |
|------|------|
| [API 整合指南](docs/API_INTEGRATION.md) | 前端開發者整合文件 |
| [部署指南](docs/DEPLOYMENT.md) | 生產環境部署步驟 |
| [效能優化](docs/PERFORMANCE_OPTIMIZATION.md) | 效能優化策略 |
| [Beta 測試計畫](docs/BETA_TEST_PLAN.md) | 醫師測試計畫 |

## 🔐 安全認證

### API Key 認證

```bash
# 請求時加入 API Key
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/...
```

### JWT Token 認證

```bash
# 請求時加入 Bearer Token
curl -H "Authorization: Bearer your-jwt-token" http://localhost:8000/api/v1/...
```

## 📊 效能指標

| 指標 | 目標 | 實測 |
|------|------|------|
| ASR 延遲 | <500ms | ~300ms |
| LLM 推理 | <2s | ~1.5s |
| API 回應 | <3s | ~1s |
| 測試覆蓋率 | ≥80% | 85% |

## 🛠️ 技術棧

| 層次 | 技術 |
|------|------|
| API 框架 | FastAPI |
| 語音辨識 | Faster-Whisper |
| LLM | Ollama (Qwen3.5, GLM-4.7) |
| 快取 | Redis |
| 容器 | Docker + Compose |
| 監控 | Prometheus + Grafana |

## 📈 專案進度

| Phase | 名稱 | 狀態 |
|-------|------|------|
| Phase 0 | 專案準備期 | ✅ 完成 |
| Phase 1 | 核心模型部署 | ✅ 完成 |
| Phase 2 | NLP Engine | ✅ 完成 |
| Phase 3 | FastAPI Backend | ✅ 完成 |
| Phase 4 | Frontend 整合 | ✅ 完成 |
| Phase 5 | 測試優化 | ✅ 完成 |
| Phase 6 | 部署上線 | 🔄 進行中 |

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

## 📄 授權

MIT License

## 📞 聯絡

- 網站：https://doctor-toolbox.com
- Email: tech@soapvoice.com
