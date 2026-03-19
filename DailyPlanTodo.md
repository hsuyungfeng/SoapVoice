# 📋 SoapVoice 每日計畫與待辦事項

**專案名稱:** SoapVoice - Medical Voice-to-SOAP System  
**建立日期:** 2026-03-19  
**當前階段:** 🟢 Phase 6 完成，進入功能強化與維護期  
**測試狀態:** 92/92 通過 ✅

---

## 📅 2026-03-19 — 今日計畫

### 🔴 高優先（P0）— 必須完成

- [x] 建立 `AGENTS.md` — AI 開發助手指引檔案（192 行）
- [x] 更新預設模型 `qwen3.5:35b` → `qwen3.5:9b`（主力）/ `qwen3.5:27b`（備用）
  - [x] `src/llm/ollama_engine.py` — ModelConfig 預設值 + docstring
  - [x] `src/soap/soap_generator.py` — SOAPConfig 預設值
  - [x] `tests/test_soap.py` — 測試斷言更新
  - [x] `.env.example` — LLM_MODEL 變數
  - [x] `config/models.yaml` — 主模型設定
  - [x] `scripts/setup_ollama.sh` — 模型清單
  - [x] `scripts/deploy.sh` — 部署腳本
  - [x] `README.md` — 6 處引用更新
  - [x] `docs/DEPLOYMENT.md` — 3 處引用更新
  - [x] `docs/PERFORMANCE_OPTIMIZATION.md` — 1 處引用更新
  - [x] `DailyProgress.md` — 3 處歷史紀錄保留不動（為歷史事實）
- [x] 建立 `DailyPlanTodo.md`（本檔案）

### 🟡 中優先（P1）— 盡快處理

- [x] 實作語音與逐字稿儲存功能
  - [x] 建立 `src/asr/recording_session.py` — RecordingSession + Manager
  - [x] 建立 `data/recordings/` 目錄結構
  - [x] 實作 WAV 音檔儲存（PCM 16-bit, 16kHz, mono）
  - [x] 實作 JSON 逐字稿儲存（含時間戳、分段）
  - [x] 整合至 WebSocket `start/chunk/end` 流程
  - [x] 新增 `tests/test_recording.py`（15 個測試，15/15 通過 ✅）
  - [x] 修復 WebSocket chunk handler 既有 bug（audio_bytes 作用域錯誤）
- [ ] 加入 CLI 互動介面（支援以較小模型生成 SOAP 病歷）

### 🟢 低優先（P2）— 有空再做

- [ ] 補充 API 文件（Swagger/OpenAPI 範例完善）
- [ ] 效能基準測試報告更新（qwen3.5:9b vs 35b 對比）
- [ ] 前端整合文件更新（配合新模型設定）

---

## 📌 近期待辦總覽

### 功能開發

| ID | 功能 | 優先級 | 狀態 | 預估時間 |
|----|------|--------|------|----------|
| F-001 | 語音與逐字稿自動儲存 | P1 | 📋 待開始 | 3-4h |
| F-002 | CLI 互動介面 | P1 | 📋 待開始 | 4-6h |
| F-003 | 多專科 SOAP 模板支援 | P2 | 📋 待開始 | 4-6h |
| F-004 | 病歷歷史查詢 API | P2 | 📋 待開始 | 2-3h |

### 技術債與優化

| ID | 項目 | 優先級 | 狀態 | 備註 |
|----|------|--------|------|------|
| T-001 | LSP 型別錯誤修復 | P2 | 📋 待開始 | soap_generator.py, websocket.py 等 4 檔 |
| T-002 | 測試覆蓋率提升至 ≥80% | P1 | 📋 待開始 | 目前約 70% |
| T-003 | qwen3.5:9b 效能驗證 | P1 | 📋 待開始 | 確認小模型 SOAP 品質 |

### 文件更新

| ID | 項目 | 優先級 | 狀態 |
|----|------|--------|------|
| D-001 | OpnusPlan.md 更新模型資訊 | P2 | 📋 待開始 |
| D-002 | DailyProgress.md 補充 03-19 紀錄 | P1 | 📋 待開始 |

---

## ✅ 已完成項目歷程

### 2026-03-19

- ✅ 建立 AGENTS.md（AI 開發助手指引）
- ✅ 全面更新預設模型 qwen3.5:35b → qwen3.5:9b（11 個檔案）
- ✅ 建立 DailyPlanTodo.md
- ✅ 實作語音與逐字稿自動儲存功能
  - 新增 `src/asr/recording_session.py`（RecordingSession + RecordingSessionManager）
  - WebSocket 整合：start → 建立 session，chunk → 寫入音頻，end → 儲存 WAV + JSON
  - 每次錄音自動保存原始音檔（WAV）與逐字稿（JSON）至 `data/recordings/{timestamp}_{uuid}/`
  - 新增 15 個測試，全部通過 ✅
  - 修復既有 chunk handler bug（audio_bytes 變數作用域錯誤）

---

## 📝 備註

- **模型策略：** `qwen3.5:9b` 為主力模型（VRAM 需求低、推理快），`qwen3.5:27b` 為備用（品質更高）
- **語音儲存需求：** 每次錄音須保存原始音檔（WAV/PCM）與 ASR 逐字稿至 `data/recordings/`
- **開發工具：** 使用 `uv` 管理依賴，所有指令以 `uv run` 執行
- **文件語言：** 所有文件以繁體中文為主

---

**最後更新:** 2026-03-19  
**下次更新:** 2026-03-20
