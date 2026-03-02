# SoapVoice v1 需求規格

## 需求追蹤矩陣

| ID | 類別 | 需求描述 | 優先級 | 狀態 |
|----|------|----------|--------|------|
| SETUP-01 | 基礎設施 | 硬體環境驗證 (GPU, RAM, 儲存) | P0 | Pending |
| SETUP-02 | 基礎設施 | GPU 驅動與 CUDA 12.1+ 安裝 | P0 | Pending |
| SETUP-03 | 基礎設施 | uv + Python 3.11 環境建置 | P0 | Pending |
| SETUP-04 | 基礎設施 | Docker + Docker Compose 環境 | P0 | ✅ Complete |
| SETUP-05 | 基礎設施 | Git repository 設定 | P0 | ✅ Complete |
| ASR-01 | 語音辨識 | Faster-Whisper large-v3 部署 | P0 | Pending |
| ASR-02 | 語音辨識 | 醫療詞彙優化 (custom vocabulary) | P0 | Pending |
| ASR-03 | 語音辨識 | WebSocket 即時串流 pipeline | P0 | Pending |
| ASR-04 | 語音辨識 | 多語言支援 (中文/英文) | P0 | Pending |
| LLM-01 | 推理引擎 | Qwen3-32B-Instruct vLLM 部署 | P0 | Pending |
| LLM-02 | 推理引擎 | GLM-4.7-Flash 快速路由 | P1 | Pending |
| LLM-03 | 推理引擎 | 推理延遲優化 (<2s @ 95th percentile) | P0 | Pending |
| NLP-01 | 醫療 NLP | 錯字自動修正 (typo correction) | P0 | Pending |
| NLP-02 | 醫療 NLP | 醫療術語標準化 (synonym mapping) | P0 | Pending |
| NLP-03 | 醫療 NLP | SOAP 自動分類 (S/O/A/P) | P0 | Pending |
| NLP-04 | 醫療 NLP | ICD-10 診斷代碼映射 | P1 | Pending |
| NLP-05 | 醫療 NLP | 專科自動分類 (specialty detection) | P1 | Pending |
| API-01 | API 閘道 | FastAPI REST endpoints | P0 | Pending |
| API-02 | API 閘道 | WebSocket 串流端點 | P0 | Pending |
| API-03 | API 閘道 | API Key 認證機制 | P0 | Pending |
| API-04 | API 閘道 | Rate Limiting (100 req/min) | P0 | Pending |
| API-05 | API 閘道 | OpenAPI/Swagger 文件 | P0 | Pending |
| API-06 | API 閘道 | 審計日誌 (audit logging) | P1 | Pending |
| SOAP-01 | SOAP 輸出 | 結構化 JSON 格式 | P0 | Pending |
| SOAP-02 | SOAP 輸出 | 繁體中文對話摘要 | P0 | Pending |
| SOAP-03 | SOAP 輸出 | SOAP 分段顯示 (S/O/A/P) | P0 | Pending |
| FRONT-01 | 前端整合 | 醫師 toolkit 網站整合 | P0 | Pending |
| FRONT-02 | 前端整合 | 語音錄製 UI 元件 | P0 | Pending |
| FRONT-03 | 前端整合 | 即時轉文字顯示 | P0 | Pending |
| FRONT-04 | 前端整合 | SOAP 編輯器元件 | P0 | Pending |
| TEST-01 | 測試優化 | 單元測試 (coverage ≥80%) | P0 | Pending |
| TEST-02 | 測試優化 | 整合測試 (coverage ≥70%) | P0 | Pending |
| TEST-03 | 測試優化 | 負載測試 (100+ concurrent) | P0 | Pending |
| TEST-04 | 測試優化 | 醫療準確率驗證 (≥95%) | P0 | Pending |
| DEPLOY-01 | 部署 | Docker Compose 生產配置 | P0 | Pending |
| DEPLOY-02 | 部署 | Nginx 反向代理設定 | P0 | Pending |
| DEPLOY-03 | 部署 | 監控儀表板 (Prometheus + Grafana) | P0 | Pending |
| DEPLOY-04 | 部署 | 健康檢查端點 | P0 | Pending |

## 需求類別統計

| 類別 | P0 數量 | P1 數量 | 總數 |
|------|---------|---------|------|
| 基礎設施 (SETUP) | 5 | 0 | 5 |
| 語音辨識 (ASR) | 4 | 0 | 4 |
| 推理引擎 (LLM) | 2 | 1 | 3 |
| 醫療 NLP (NLP) | 3 | 2 | 5 |
| API 閘道 (API) | 5 | 1 | 6 |
| SOAP 輸出 (SOAP) | 3 | 0 | 3 |
| 前端整合 (FRONT) | 4 | 0 | 4 |
| 測試優化 (TEST) | 4 | 0 | 4 |
| 部署 (DEPLOY) | 4 | 0 | 4 |
| **總計** | **34** | **4** | **38** |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SETUP-01 | Phase 1 | Complete |
| SETUP-02 | Phase 1 | Complete |
| SETUP-03 | Phase 1 | Complete |
| SETUP-04 | Phase 1 | Pending |
| SETUP-05 | Phase 1 | Pending |
| ASR-01 | Phase 2 | Pending |
| ASR-02 | Phase 2 | Pending |
| ASR-03 | Phase 2 | Pending |
| ASR-04 | Phase 2 | Pending |
| LLM-01 | Phase 2 | Pending |
| LLM-02 | Phase 2 | Pending |
| LLM-03 | Phase 2 | Pending |
| NLP-01 | Phase 3 | Pending |
| NLP-02 | Phase 3 | Pending |
| NLP-03 | Phase 3 | Pending |
| NLP-04 | Phase 3 | Pending |
| NLP-05 | Phase 3 | Pending |
| API-01 | Phase 4 | Pending |
| API-02 | Phase 4 | Pending |
| API-03 | Phase 4 | Pending |
| API-04 | Phase 4 | Pending |
| API-05 | Phase 4 | Pending |
| API-06 | Phase 4 | Pending |
| SOAP-01 | Phase 4 | Pending |
| SOAP-02 | Phase 4 | Pending |
| SOAP-03 | Phase 4 | Pending |
| FRONT-01 | Phase 5 | Pending |
| FRONT-02 | Phase 5 | Pending |
| FRONT-03 | Phase 5 | Pending |
| FRONT-04 | Phase 5 | Pending |
| TEST-01 | Phase 6 | Pending |
| TEST-02 | Phase 6 | Pending |
| TEST-03 | Phase 6 | Pending |
| TEST-04 | Phase 6 | Pending |
| DEPLOY-01 | Phase 7 | Pending |
| DEPLOY-02 | Phase 7 | Pending |
| DEPLOY-03 | Phase 7 | Pending |
| DEPLOY-04 | Phase 7 | Pending |

## 備註

- 本需求基於 OpnusPlan.md v0.1.0
- P0 = Must Have (MVP 必要功能)
- P1 = Should Have (重要但非緊急)
- 所有 P1 需求將在 v1 完成後考慮
