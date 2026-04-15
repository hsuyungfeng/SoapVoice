# SoapVoice Windows 離線版優化進度表 (WinPlanToDo)

本文件紀錄針對 Windows CPU 環境進行離線優化的各項任務。

---

## ✅ 已完成 (Session 2026-04-10)

### LLM 引擎升級
- [x] 升級至 **Gemma 4:E4B (Q4_K_M)** 作為主力 LLM。
- [x] 更新 `llama-cpp-python` 至 `0.3.20` 支援 Gemma 4 架構。
- [x] 實作 Adaptive Prompt Template（`<start_of_turn>` 控制標記）。
- [x] 增加 Hallucination Filter 過濾 LLM 贅餘輸出。

### OCR 輕量化
- [x] 將主力 OCR 引擎由 EasyOCR 替換為 **Tesseract-OCR**（`pytesseract`）。
- [x] 確認 `mss` 截圖庫與 `pytesseract 0.3.13` 正常運作。
- [x] Ollama Vision (gemma4:e2b) 作為備援 OCR，成功擷取畫面內容。
- [x] **根據離線配置禁用 Ollama Vision**：當 `USE_LLAMA_CPP=true` 時自動跳過 Ollama Vision，確保全離線運行。

### 桌面 GUI 重構（右側邊欄）
- [x] 從固定視窗重構為**雙階段右側邊欄 (Dual-Stage Sidebar)**。
- [x] 採用 `ttkbootstrap` Superhero 主題，大幅提升視覺美觀度。
- [x] 使用 `ttk.Window` 作為根視窗，解決 `bootstyle` 屬性相容性問題。
- [x] 視窗尺寸：緊湊模式 `420×240`，展開模式 `420×900`。
- [x] 自動計算靠右停靠座標（`x = screen_width - 440`）。
- [x] 修復 `btn_test` AttributeError 啟動崩潰問題。
- [x] 移除舊版 `ResultPopup` 彈出視窗，改為嵌入式展開面板。
- [x] 修復 GUI 啟動錯誤 (`unknown option "-bootstyle"`)，將 `ttk.LabelFrame` 改為 `ttk.Labelframe` 並移除 `bootstyle` 參數。
- [x] 修復啟動時段錯誤 (記憶體區段錯誤)，避免在啟動測試中實例化 OCRParser，防止資源衝突。

### 專案整理
- [x] 刪除所有根目錄的冗餘測試腳本（`test_ocr*.py`, `test_llama_soap*.py` 等）。
- [x] 刪除舊版 benchmark 結果 JSON 與開發日誌。

### OCR 段錯誤修復
- [x] **修復 GUI 啟動記憶體區段錯誤**：OCR 解析器嘗試連接 Ollama Vision API 導致段錯誤。
  - **根本原因**：Ollama Vision 嘗試連線 `localhost:11434`時發生衝突。
- [x] **離線 OCR 配置**：當 `USE_LLAMA_CPP=true` 時自動禁用 Ollama Vision 與 EasyOCR。
- [x] **影像縮小優化**：對超過 1920px 的截圖進行 50% 縮小。
- [x] **執行緒安全 UI 更新**：使用 `root.after()` 進行主執行緒 UI 更新。
- [x] **GUI 穩定啟動驗證**：測試確認 GUI 啟動無段錯誤。

### NLP 與 API 擴展功能修復 (Session 2026-04-15)
- [x] **修復症狀提取 (Extract Symptoms)**：擴充 `terminology_mapper.py` 同義詞表，支援「肚子痛」、「想吐」等口語化表達。
- [x] **修復 ICD-10 分類**：擴充 `icd10_classifier.py` 關鍵字，確保常見症狀能正確對應到 ICD-10 代碼。
- [x] **完善醫囑與藥物建議**：在 `extended_soapvoice.py` 中建立完整的字典映射，根據 ICD-10 代碼與症狀提供精確建議。
- [x] **優化 GUI SOAP 顯示**：重構 `desktop_app.py` 中的 `on_process_complete`，以結構化方式顯示診斷摘要、SOAP 內容（中英雙語）、建議醫囑及用藥。
- [x] **驗證全離線 CPU 模式**：確認在 `USE_LLAMA_CPP=true` 下，Gemma 4 模型於 CPU 環境運行流暢（端到端耗時 < 10秒）。

---

## ✅ 已完成 (Session 2026-04-15)

### ASR 優化 (Faster-Whisper)
- [x] **驗證 `distil-large-v3` 效能**：CPU (int8) 載入速度僅需 **1.49 秒**，優於舊版 medium 模型。
- [x] **實作模型預加載機制**：在 FastAPI `lifespan` 中整合 `get_extended_engine()`，確保服務啟動即完成 ASR 與 NLP 模型加載，消除首錄延遲。
- [x] **環境變數配置**：支援透過 `.env` 動態切換 ASR 模型與計算精度。

### Windows 打包準備
- [x] **優化 PyInstaller Spec**：重新編寫 `soapvoice.spec`，正確納入 `fastapi`、`uvicorn`、`requests` 等核心依賴，並精簡非必要大型套件。
- [x] **加入版本資訊**：建立 `version_info.txt` 供 EXE 詳細資料使用。
- [x] **Tesseract 路徑支援**：在 `ocr_parser.py` 加入 `TESSERACT_CMD` 環境變數支援，方便 Windows 使用者自定義路徑。

---

## 📅 下一步 (Final Release)

- [ ] **Windows 環境最終編譯**
    - [ ] 執行 `pyinstaller soapvoice.spec` 產生單一 EXE。
    - [ ] 執行 `iscc installer/soapvoice.iss` 產生安裝檔。
- [ ] **驗證清單**
    - [ ] 完全拔除網路線後的 8-WAV 基準測試。
    - [ ] 確認 `VCRuntime140.dll` 缺失時的安裝程式提醒。

## 🧪 驗證清單

- [ ] 完全拔除網路線後的 8-WAV 基準測試。
- [ ] 於 Windows 10/11 (i5 10代, 8GB RAM) 的啟動時間測試（目標: < 15秒）。
- [ ] 記憶體佔用監控（目標峰值: < 4GB）。
- [ ] 確認雙階段 GUI 在全螢幕 HIS 系統旁的視覺層疊 (topmost) 行為。

---

*Last Updated: 2026-04-10 (Session 2)*
