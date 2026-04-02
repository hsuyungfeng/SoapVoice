---
created: 2026-04-02T03:14:26.174Z
title: SoapVoice Phase 7 Windows Desktop GUI 與雲端整合
area: ui
files:
  - src/gui/desktop_app.py (建立 Tkinter 永遠置頂浮動視窗)
  - src/nlp/ocr_parser.py (EasyOCR 螢幕截圖識別)
  - src/api/cloud_api.py (Cloud Sync API)
  - src/db/local_database.py (診所與醫師資料表)
  - SoapVoice.spec (PyInstaller 包裝)
---

## Problem

Phase 7 需要實作以下功能以支援診所第一線使用：

1. **Windows 浮動視窗 (GUI)**：Tkinter Always-on-top、可拖曳、內含巨型「開始錄音」與「設定」按鈕
2. **互動狀態與顏色提示**：預備藍 → 錄音閃紅 → 處理黃 → 完成綠 + 自動複製剪貼簿
3. **診所與醫師多重註冊**：診所名稱、機構代碼、多位醫師姓名與 ID
4. **螢幕截圖與 OCR 識別**：mss 截圖 + EasyOCR 文字提取 + Qwen2.5 結構化 JSON
5. **自動比對醫師**：從 OCR 結果比對已註冊醫師
6. **TXT Tag 格式輸出**：純文字 + #診所名稱 #醫師姓名 #日期 Tag
7. **雲端 API 端點**：POST /api/v1/cloud/sync_wav, GET /api/v1/cloud/export_md

## Solution

已全部完成實作並驗證通過。所有檢查清單項目均已完成。

### 完成項目

- [x] pyproject.toml 加入 easyocr, Pillow, mss 套件
- [x] clinic_info 與 doctors 資料表建立
- [x] src/nlp/ocr_parser.py 截圖與 OCR 處理器
- [x] src/api/cloud_api.py 雲端同步 API
- [x] src/gui/desktop_app.py Tkinter 浮動視窗 (Always on Top)
- [x] 狀態顏色切換流 (藍→紅閃→黃→綠)
- [x] TXT Tag 輸出與剪貼簿自動複製
- [x] SoapVoice.spec 更新為 GUI 進入點

### 相關檔案

- `src/gui/desktop_app.py` - Windows GUI 主程式
- `src/nlp/ocr_parser.py` - OCR 處理模組
- `src/api/cloud_api.py` - 雲端 API
- `src/db/local_database.py` - 本機資料庫
- `SoapVoice.spec` - PyInstaller 包裝腳本