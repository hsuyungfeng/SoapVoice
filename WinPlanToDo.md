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

---

## 📅 短期目標 (Next Sprint)

- [ ] **ASR 優化 (Faster-Whisper)**
    - [ ] 確認 `distil-large-v3` 模型在 CPU 上的啟動速度。
    - [ ] 實施模型權重預加載機制，減少初次轉錄延遲。
- [ ] **Windows 最終打包 (PyInstaller)**
    - [ ] 確認 `VCRuntime140.dll` 已包含或提醒安裝。
    - [ ] 確認 Tesseract 二進位檔路徑配置正確。
    - [ ] 加入 `version_info.txt` 與 SoapVoice 圖示。
    - [ ] 壓縮非必要依賴 (`torch`, `cv2.gui`)。

## 🧪 驗證清單

- [ ] 完全拔除網路線後的 8-WAV 基準測試。
- [ ] 於 Windows 10/11 (i5 10代, 8GB RAM) 的啟動時間測試（目標: < 15秒）。
- [ ] 記憶體佔用監控（目標峰值: < 4GB）。
- [ ] 確認雙階段 GUI 在全螢幕 HIS 系統旁的視覺層疊 (topmost) 行為。

---

*Last Updated: 2026-04-10 (Session 2)*
