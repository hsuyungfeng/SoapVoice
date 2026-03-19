# 🏥 SoapVoice 醫療語音轉 SOAP 系統

[![測試狀態](https://img.shields.io/badge/tests-92%20passed-green)]()
[![測試覆蓋率](https://img.shields.io/badge/coverage-85%25-green)]()
[![版本](https://img.shields.io/badge/version-1.2.0-blue)]()
[![授權](https://img.shields.io/badge/license-MIT-blue)]()

## 📖 專案說明

SoapVoice 是一套基於本地 LLM 的醫療語音轉 SOAP 病歷系統：

- 🎤 即時多語語音輸入（中文、英文）
- 🧠 AI 驅動的醫療語意標準化與術語專業化（73 個內建映射）
- 📋 結構化 SOAP 病歷自動產出（含 ICD-10 候選碼預填）
- 📊 ICD-10 診斷代碼映射與專科分類
- 🔐 內網專用安全部署（192.168.x.x）
- 🔄 **支援多 ASR 引擎切換**（Faster-Whisper / Qwen3-ASR）

**Pipeline 說明：**
```
語音輸入 → [可選 ASR 引擎] → 術語標準化 → ICD-10 對應 → Qwen3.5 LLM → SOAP 病歷
                ↓
        Faster-Whisper (繁體) 或 Qwen3-ASR (簡體→繁體)
```Goal: add Cli-anything and skill use smaller model for SOAP record

---

## 🚀 快速開始

### 前置需求

| 元件 | 最低要求 | 建議 |
|------|---------|------|
| Python | 3.11+ | 3.11 |
| uv | 最新版 | `pip install uv` |
| VRAM | 20GB | 44GB (RTX 2080 Ti × 2) |
| RAM | 32GB | 48GB |
| 磁碟 | 100GB | 500GB+ |
| OS | Ubuntu 20.04+ | Ubuntu 22.04 |
| CUDA | 11.8+ | 12.x |
| Ollama | 0.5+ | 最新版 |

### 開發環境快速啟動

```bash
# 1. 克隆專案
git clone https://github.com/your-org/soapvoice.git
cd soapvoice

# 2. 安裝依賴（uv 管理）
uv sync

# 3. 安裝並啟動 Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen3.5:9b

# 4. 啟動 API 服務
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 5. 確認服務
curl http://localhost:8000/health
```

### 驗證 API 可用

```bash
# 術語標準化測試
curl -s -X POST http://localhost:8000/api/v1/clinical/normalize \
  -H "Content-Type: application/json" \
  -d '{"text": "病人胸悶兩天呼吸困難"}' | python3 -m json.tool

# 預期輸出：
# { "normalized_text": "病人chest tightness兩天dyspnea",
#   "terms": [{"original": "胸悶", "standard": "chest tightness", "icd10_candidates": ["R07.89"]}, ...] }
```

---

## 🖥️ 生產環境部署

### 方案一：本地直接部署（推薦用於內網）

```bash
# Step 1: 複製環境配置
cp .env.example .env

# Step 2: 編輯關鍵設定
vim .env
# 必填：
#   JWT_SECRET_KEY=<產生方式見下方>
#   API_KEY=<your-api-key>
#   OLLAMA_BASE_URL=http://localhost:11434

# Step 3: 產生 JWT 金鑰
python3 -c "import secrets; print(secrets.token_hex(32))"

# Step 4: 下載模型（約需 60GB 磁碟空間）
ollama pull qwen3.5:9b       # 主模型 6GB
ollama pull qwen3.5:27b      # 備用模型 17GB（可選）
ollama pull glm-4.7-flash    # 快速推理 19GB（可選）

# Step 5: 部署並驗證
./scripts/deploy.sh
./scripts/deploy_verify.sh
```

### 方案二：Docker Compose 部署

```bash
# Step 1: 環境配置
cp .env.example .env
vim .env

# Step 2: 建構映像
docker compose -f docker-compose.prod.yml build

# Step 3: 啟動全部服務（含 Ollama + Nginx + Redis + Prometheus）
docker compose -f docker-compose.prod.yml up -d

# Step 4: 驗證部署
./scripts/deploy_verify.sh

# 查看服務狀態
docker compose -f docker-compose.prod.yml ps
```

### 服務端口對照

| 服務 | 內部端口 | 說明 |
|------|---------|------|
| FastAPI | 8000 | API 主服務 |
| Nginx | 80 / 443 | 反向代理（生產用） |
| Ollama | 11434 | LLM 服務 |
| Redis | 6379 | 快取 |
| Prometheus | 9090 | 指標收集 |
| Grafana | 3000 | 監控儀表板 |

### Nginx 配置要點

```nginx
# /etc/nginx/conf.d/soapvoice.conf
server {
    listen 80;
    server_name 192.168.x.x;

    # Rate Limiting: 100 req/min per IP
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
    limit_req zone=api burst=20 nodelay;

    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket 語音串流
    location /api/v1/voice/stream {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
    }
}
```

### 硬體資源分配

```
GPU0 (RTX 2080 Ti, 22GB VRAM):
  └── Ollama: qwen3.5:9b (6GB) + qwen3.5:27b (17GB，備用)

GPU1 (RTX 2080 Ti, 22GB VRAM):
  └── Faster-Whisper large-v3 (6GB)

CPU (Ryzen 9 5950X, 16C/32T):
  └── FastAPI (uvicorn workers × 4)
  └── Redis

RAM (48GB):
  └── 模型載入緩衝、API 快取
```

---

## 📦 API 端點

### 核心端點

| 端點 | 方法 | Request Body | 說明 |
|------|------|-------------|------|
| `/health` | GET | — | 服務健康檢查 |
| `/api/v1/clinical/normalize` | POST | `{"text": "..."}` | 術語標準化 |
| `/api/v1/clinical/icd10` | POST | `{"text": "...", "context": {...}}` | ICD-10 分類 |
| `/api/v1/clinical/classify/soap` | POST | `{"text": "..."}` | SOAP 分類 |
| `/api/v1/clinical/soap/generate` | POST | `{"transcript": "...", "patient_context": {...}}` | SOAP 生成 |
| `/api/v1/clinical/health` | GET | — | NLP 元件狀態 |
| `/api/v1/voice/stream` | WS | 音頻串流 | 即時語音轉錄 |

### SOAP 生成範例

```bash
curl -X POST http://localhost:8000/api/v1/clinical/soap/generate \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "病人胸悶兩天伴隨呼吸困難",
    "patient_context": {
      "age": 45,
      "gender": "M",
      "chief_complaint": "chest discomfort"
    }
  }'
```

**回應格式（含術語標準化資訊）：**
```json
{
  "soap": {
    "subjective": "45yo male with chest tightness × 2 days and dyspnea",
    "objective": "",
    "assessment": "R07.89 Chest tightness; R06.02 Dyspnea",
    "plan": "",
    "conversation_summary": "病患主訴胸悶兩天伴隨呼吸困難，建議進一步心肺評估。"
  },
  "metadata": {
    "model_version": "qwen3.5:9b",
    "normalized_terms": [
      {"original": "胸悶", "standard": "chest tightness", "icd10_candidates": ["R07.89"]},
      {"original": "呼吸困難", "standard": "dyspnea", "icd10_candidates": ["R06.02"]}
    ],
    "confidence": {"subjective": 0.97, "objective": 0.0, "assessment": 0.05, "plan": 0.0}
  },
  "processing_time_ms": 1823.5
}
```

---

## 🎛️ ASR 引擎選擇

SoapVoice 支援多種 ASR 引擎，可在 WebSocket 連線時選擇：

### 支援的引擎

| 引擎 | 輸出語系 | 延遲 | 特色 |
|------|---------|------|------|
| `whisper` | 繁體中文 | ~4.5s | 預設首選，穩定輸出繁體 |
| `qwen3asr` | 簡體→繁體 | ~6.5s | 語義最準確，需 opencc 轉換 |

### 使用方式

```javascript
// WebSocket 連線時選擇引擎
const ws = new WebSocket('ws://localhost:8000/api/v1/voice/stream');

// 開始轉錄，指定 ASR 引擎
ws.send(JSON.stringify({
  type: 'start',
  asr_backend: 'qwen3asr',        // 或 'whisper'
  convert_to_traditional: true     // Qwen3-ASR 輸出轉繁體
}));

// 傳送音頻塊...
ws.send(JSON.stringify({
  type: 'chunk',
  audio: 'base64-encoded-audio'
}));

// 結束轉錄
ws.send(JSON.stringify({ type: 'end' }));
```

### 基準測試結果（8 個醫療場景）

| 引擎 | 平均延遲 | 準確率 | 備註 |
|------|---------|--------|------|
| 🥇 Faster-Whisper | ~4,500ms | 良好 | 繁體輸出，生產首選 |
| 🥈 Qwen3-ASR | ~6,500ms | 最佳 | 簡體輸出，需轉繁體 |

 安全認證---

## 🔐

### API Key 認證

```bash
curl -H "X-API-Key: your-api-key" \
     http://localhost:8000/api/v1/clinical/normalize \
     -d '{"text": "病人發燒"}'
```

### JWT Token 認證

```bash
# 產生 Token（開發用）
uv run python -c "
from src.security.auth import create_jwt_token
print(create_jwt_token({'user': 'doctor01', 'role': 'physician'}))
"

# 使用 Token
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/v1/clinical/soap/generate \
     -d '{"transcript": "..."}'
```

---

## 🧪 測試

```bash
# 單元測試（92 個測試）
uv run pytest tests/ -v

# 帶覆蓋率報告
./scripts/test_coverage.sh

# 端到端整合測試
uv run python scripts/test_e2e.py

# WebSocket 語音串流測試
uv run python scripts/test_websocket_simple.py

# 麥克風錄音測試
uv run python scripts/test_recording.py

# 負載測試（需 Locust）
uv run locust -f scripts/load_test.py --host=http://localhost:8000

# ASR 基準測試（4 引擎比較）
uv run python scripts/asr_bench.py list           # 列出所有場景
uv run python scripts/asr_bench.py record        # 錄製測試音頻
uv run python scripts/asr_bench.py batch         # 批次測試所有引擎
uv run python scripts/asr_bench.py report        # 顯示最新報告
```

---

## 📊 效能指標

| 指標 | 目標 | 實測 |
|------|------|------|
| ASR 延遲 | <500ms | ~300ms |
| 術語標準化 | <10ms | ~0.03ms |
| LLM 推理 | <2s | ~1.5s |
| API 回應 | <3s | ~2s |
| 測試覆蓋率 | ≥80% | 85% |
| 並發負載 | 10 users | 138 req/0 fail |

---

## 🛠️ 技術棧

| 層次 | 技術 |
|------|------|
| API 框架 | FastAPI + uvicorn |
| **語音辨識** | **Faster-Whisper large-v3 + Qwen3-ASR-0.6B** |
| LLM | Ollama (qwen3.5:9b, qwen3.5:27b, GLM-4.7-Flash) |
| NLP | 自建術語映射器 + ICD-10 分類器 |
| 簡繁轉換 | opencc |
| 快取 | Redis |
| 代理 | Nginx |
| 容器 | Docker Compose |
| 監控 | Prometheus + Grafana |
| 套件管理 | uv |

---

## 📈 專案進度

| Phase | 名稱 | 狀態 | 完成日 |
|-------|------|------|--------|
| Phase 0 | 專案準備期 | ✅ 完成 | 2026-03-05 |
| Phase 1 | 核心模型部署 | ✅ 完成 | 2026-03-07 |
| Phase 2 | NLP Engine | ✅ 完成 | 2026-03-05 |
| Phase 3 | FastAPI Backend | ✅ 完成 | 2026-03-10 |
| Phase 4 | Frontend 整合 | ✅ 完成 | 2026-03-11 |
| Phase 5 | 測試優化 | ✅ 完成 | 2026-03-13 |
| Phase 6 | 部署上線 | ✅ 完成 | 2026-03-15 |
| Sprint 7 | 術語標準化整合 | ✅ 完成 | 2026-03-03 |
| **Sprint 8** | **ASR 多引擎整合** | ✅ 完成 | **2026-03-04** |

---

## 📚 文件

| 文件 | 說明 |
|------|------|
| [API 整合指南](docs/API_INTEGRATION.md) | 前端開發者整合文件 |
| [部署指南](docs/DEPLOYMENT.md) | 生產環境完整部署步驟 |
| [效能優化](docs/PERFORMANCE_OPTIMIZATION.md) | 效能調校策略 |
| [Beta 測試計畫](docs/BETA_TEST_PLAN.md) | 醫師 Beta 測試 |
| [OpnusPlan.md](OpnusPlan.md) | 完整專案執行計畫書 |
| [DailyProgress.md](DailyProgress.md) | 每日開發進度 |

---

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

## 📄 授權

MIT License

## 📞 聯絡

- 網站：https://doctor-toolbox.com
- Email: tech@soapvoice.com
