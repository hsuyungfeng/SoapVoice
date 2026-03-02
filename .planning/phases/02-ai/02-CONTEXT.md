# Phase 2: AI 模型部署 - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

部署 ASR (Faster-Whisper) 與 LLM (GLM-4.7-Flash) 推理引擎，使系統可進行語音辨識與文字生成。Phase 3 會在此基礎上建立醫療 NLP 引擎。

</domain>

<decisions>
## Implementation Decisions

### 模型服務架構
- **模型組合**: Faster-Whisper large-v3 + GLM-4.7-Flash
- **服務方式**: vLLM (OpenAI 相容格式)
- **GPU 配置**: GLM-4.7-Flash (~10GB VRAM) + Whisper (~8GB) 可同時載入
- **未來擴充**: Qwen3-32B 可能在未來部署（目前先用 GLM）

### API 介面設計
- **格式**: OpenAI 相容格式 (/v1/chat/completions)
- **端點**:
  - `/v1/audio/transcriptions` - 語音串流辨識
  - `/v1/chat/completions` - 文字聊天
  - `/v1/soap/generate` - 醫療 SOAP 生成
- **認證**: 暫時無認證（內網部署）

### 效能目標
- **ASR 延遲**: < 500ms (RTF < 0.3)
- **LLM 延遲**: < 1s
- **處理模式**: 順序處理（單一請求）
- **未來優化**: 可擴充至並發處理

### 錯誤處理
- **模型失敗**: 自動重試 3 次
- **GPU OOM**: 優雅處理，回傳錯誤訊息
- **日誌記錄**: 錯誤日誌需包含 retry 次數與失敗原因

</decisions>

<specifics>
## Specific Ideas

- "amd base model may change later" - 未來可能使用 AMD GPU
- GLM-4.7-Flash 為主模型，Qwen3-32B 以後再評估

</specifics>

<deferred>
## Deferred Ideas

- Qwen3-32B 部署 - 未來 Phase 考量
- 並發處理優化 - Phase 2 完成後評估
- 認證機制 - Phase 4 或部署時加入

</deferred>

---

*Phase: 02-ai*
*Context gathered: 2026-03-02*
