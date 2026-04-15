# SoapVoice 專案狀態

## 專案概述

**專案名稱**: SoapVoice - 醫療語音轉 SOAP 病歷系統
**當前焦點**: 功能驗證與優化階段（Verification & Optimization）

## 當前位置

**Phase**: 08-voice-recording 🔄 進行中
**狀態**: 🟢 良好 - 核心 Pipeline 於 CPU 離線模式下運作正常

## 進度

- Phase 1-7: ✅ 完成
- Phase 7.1: ✅ 完成（Vision OCR + 統一模型策略 + llama.cpp 包裝）
- Phase 8.0: ✅ 完成（NLP 提取與擴展 API 修復）

## 最近更新

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

## 會話連續性

**上次工作**: 2026-04-15
**停止位置**: 完成 NLP 擴展功能修復與 GUI 顯示優化
**下一步**: 
1. 繼續 ASR 優化 (Faster-Whisper 模型預加載)
2. 進行 Windows 最終打包與 PyInstaller 資源路徑驗證
