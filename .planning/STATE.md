---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: completed-transitioning-to-v1_1
last_updated: "2026-04-24T08:37:21.431Z"
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 3
  completed_plans: 3
  percent: 100
---

# SoapVoice 專案狀態

## 專案概述

**專案名稱**: SoapVoice - 醫療語音轉 SOAP 病歷系統
**當前焦點**: 功能驗證與優化階段（Verification & Optimization）

## 當前位置

**Phase**: 09-windows 🔄 進行中
**狀態**: 🟢 良好 - ASR 預加載與 NLP 提取修復完成，已進入最終打包驗證

## 進度

- Phase 1-7: ✅ 完成
- Phase 7.1: ✅ 完成（Vision OCR + 統一模型策略 + llama.cpp 包裝）
- Phase 8.0: ✅ 完成（NLP 提取與擴展 API 修復）

## 最近更新

- **2026-04-23**: GPU 加速 + 區域網路伺服器 + 備份系統 (Session 5)
  - ✅ **GPU 加速啟用**：移除 CPU 強制覆蓋，ASR（Faster-Whisper）與 LLM（llama.cpp）現可使用 CUDA；支援 3060 12GB GPU，全部層數卸載至 GPU
  - ✅ **區域網路伺服器**：修改 `start_server.py` 綁定 0.0.0.0，區網電腦可直接呼叫 `http://GPU_IP:8010/api/v1/extended/process`
  - ✅ **備份系統**：建立 `scripts/backup.sh`，每日 02:00 自動 rsync 至本地 NAS + rclone 同步至 Google Cloud Storage
  - ✅ **環境變數設定**：`.env` 新增 GPU 配置（WHISPER_DEVICE=cuda, LLAMA_N_GPU_LAYERS=-1）、LAN 設定（HOST=0.0.0.0）、API Key

- **2026-04-16**: 穩定性與效能優化 (Session 4)
  - ✅ **修復 GUI 啟動段錯誤**：延遲初始化 `OCRParser` 與 `AudioRecorder` 等重量級組件，防止主執行緒資源競爭導致的 Segmentation Fault。
  - ✅ **ALSA 雜訊過濾**：使用 context manager 隱藏 `PyAudio` 初始化時的 ALSA 與 PulseAudio 驅動警告。
  - ✅ **ASR 模型優化**：實現 ASR 模型快取與預加載，修復 `ValueError` 與路徑 Bug，優化中文文字拼接。
  - ✅ **ASR 幻覺過濾**：設定 `initial_prompt` 強制繁體中文，關閉 `condition_on_previous_text` 防止迴圈，並擴大幻覺黑名單。
  - ✅ **OCR 引擎遷移**：將主力 OCR 引擎由 EasyOCR 替換為 **Tesseract-OCR (pytesseract)**。
  - ✅ **UI 更新**：更新 Web 介面 OCR 選擇，預設使用 Tesseract-OCR (主力離線)。
  - ✅ **依賴清理**：從 `pyproject.toml` 中移除 `easyocr` 依賴，減輕安裝負擔並確保全離線環境穩定性。
  - ✅ **全域一致性**：更新 `ocr_api.py`、`ocr_parser.py` 與 `capture_ocr.py` 確保 Tesseract 作為首選方案。

- **2026-04-15**: NLP 提取與擴展功能修復 (Session 3)
  - ✅ **修復症狀提取**：增加口語化同義詞支援（如「肚子痛」、「想吐」）。
  - ✅ **修復 ICD-10 分類**：完善關鍵字映射，提高自動診斷準確率。
  - ✅ **完善醫囑與藥物建議**：建立完整的醫學知識字典，提供針對性建議。
  - ✅ **優化 GUI SOAP 顯示**：結構化展示臨床摘要、雙語 SOAP、醫囑與用藥。
  - ✅ **驗證 CPU 離線模式**：Gemma 4 (llama.cpp) 於 CPU 環境穩定運作，耗時符合預期。

- **2026-04-13**: Windows 打包階段部分完成 (Phase 9)
  - ✅ 資源路徑偵測工具實作完成
  - ✅ PyInstaller spec 檔案配置完成
  - ✅ 自動化打包腳本與使用者指南建立
  - ✅ Inno Setup 安裝腳本建立完成
  - ⚠️ 需在 Windows 環境進行最終編譯驗證

## 模型分布

| 模型 | 大小 | 用途 |
|------|------|------|
| gemma-4-E4B-it-Q4_K_M.gguf | 5.3GB | 離線 LLM (llama.cpp) |
| qwen2.5-3b-instruct-q4_k_m.gguf | 2.1GB | 備用 LLM |
| models/whisper/medium.pt | - | Faster-Whisper ASR |

## 待辦事項 (Pending Todos)

| # | 標題 | 領域 | 建立日期 |
|---|------|------|----------|
| 1 | 前端整合與開發測試網頁整合麥克風收音 | ui | 2026-03-24 |
| 2 | Compare CPU vs GPU model performance for Windows Docker | tooling | 2026-03-25 |
| 3 | SoapVoice Phase 7 Windows Desktop GUI 與雲端整合 | ui | 2026-04-02 |
| 4 | Deep research README project for v1.1 planning | planning | 2026-04-24 |
| 5 | Dashboard improvement plan and serve at local network | ui | 2026-04-24 |

## 會話連續性

**上次工作**: 2026-04-24
**停止位置**: v1.0 里程碑完成，Phase 9 標記完成（Wine EXE 缺口留待後續處理）
**下一步**: 啟動 v1.1 規劃 — `/gsd-new-milestone`

1. 深入專案研究（README.md）→ 產出 v1.1 需求
2. Dashboard 改進與 LAN 伺服器設定
3. Wine EXE 打包（Phase 9 遺留缺口）
