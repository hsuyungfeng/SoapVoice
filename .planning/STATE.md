# SoapVoice 專案狀態

## 專案概述

**專案名稱**: SoapVoice - 醫療語音轉 SOAP 病歷系統
**當前焦點**: 功能測試階段（functional-testing） - 端到端流程驗證

## 當前位置

**Phase**: functional-testing (功能測試) ✅ 完成
**狀態**: ✅ 已完成

## 進度

- Phase 1-7: ✅ 完成
- Phase 7.1: ✅ 完成（Vision OCR + 統一模型策略 + llama.cpp 包裝）

## 最近更新

- **2026-04-13**: Windows 打包階段進行中 (Phase 9)
  - ✅ 資源路徑偵測工具實作完成 (Plan 1)
  - ✅ PyInstaller spec 檔案配置完成 (Plan 1)
  - 🔄 EXE 打包測試進行中（Linux 環境警告待處理）
  - ✅ Inno Setup 安裝腳本建立完成 (Plan 2)
  - 📋 待完成：Windows 環境 EXE 建置與 DLL 相依性解決
  - 📋 待完成：Windows 環境 Inno Setup 編譯與安裝測試

- **2026-04-13**: 功能測試階段完成
  - ✅ 錄音功能測試通過
  - ✅ ASR 轉錄測試通過
  - ✅ 術語標準化與 ICD-10 分類測試通過
  - ✅ SOAP 生成測試通過

- **2026-04-13**: p8-voice-recorder 檢查點測試完成
  - ✅ 後端啟動問題已解決（環境變數載入順序修正）
  - ✅ CPU Whisper 轉錄功能正常
  - ✅ SOAP 病歷生成功能正常
  - ⚠️ 症狀提取與 ICD-10 分類模組未返回結果（空陣列）
  - ⚠️ 醫囑與藥物建議模組未返回結果（空陣列）
  - 🔄 轉移至功能測試階段（functional-testing）

- 2026-04-07: Phase 7.1 完成
  - 更新 OCRParser 支援多模型輪詢
  - 測試統一模型策略
  - 下載 llama.cpp b7725
  - 包裝 Windows x64 可執行檔

## 模型分布

| 模型 | 大小 | 用途 |
|------|------|------|
| qwen2.5-3b-instruct-q4_k_m.gguf | 2GB | 離線 LLM |
| models/windows/*.exe | - | Windows 執行檔 |
| models/llama-cpp/* | - | Linux 執行檔 |

## 會話連續性

**上次工作**: 2026-04-13
**停止位置**: Phase 9 Plan 2 完成（Inno Setup 腳本建立）
**恢復於**: 2026-04-13
**狀態**: 部分完成 - Inno Setup 安裝腳本就緒，但編譯與測試需 Windows 環境
**下一步**: Windows 環境 EXE 建置與安裝程式編譯

---

## 相關檔案

- `.planning/phases/p7.1-vision-ocr/.continue-here.md` - Phase 7.1 完成記錄
- `.planning/phases/p7-gui-optimization/.continue-here.md` - Phase 7 詳細資訊
- `.planning/phases/p4-windows-exe/.continue-here.md` - Phase 4 完成記錄