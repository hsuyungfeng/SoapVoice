# SoapVoice Phase 8 TODO

## Current Phase: Phase 8 - 門診語音錄製系統 (Completed & Stabilized)

### 8.1 系統匣安裝 (System Tray)
- [x] Create system tray icon with menu (`TrayIconManager`)
- [x] Implement minimize to tray on close
- [x] Add status indicator (Idle/Recording/Processing/Error)
- [x] Integrate with desktop app

### 8.2 Screenshot + OCR Workflow
- [x] Add screenshot capture (via `mss`)
- [x] Implement Tesseract-OCR for patient info extraction (replaced EasyOCR for offline speed)
- [x] Extract: name, birthday, ID, MRN, timestamp, doctor
- [x] Confirmation dialog for extracted data in GUI
- [x] Manual editing of extracted data

### 8.3 Voice Recording with LLM SOAP
- [x] Implement audio recording with PyAudio (`AudioRecorder`)
- [x] Integrate ASR (Qwen3-ASR for speed, Whisper for accuracy)
- [x] Call LLM for SOAP generation (Gemma-4 / Qwen2.5 via llama.cpp)
- [x] Handle recording states (start/stop/save)

### 8.4 浮動視窗 (Results Window)
- [x] Create "Ultimate" Sidebar GUI (`src/gui/desktop_app.py`)
- [x] Display patient information (editable)
- [x] Display transcript
- [x] Display SOAP result (Medical English)
- [x] Add copy to clipboard button

### 8.5 HIS 剪貼簿整合 (Clipboard)
- [x] One-click copy SOAP to clipboard
- [x] Format SOAP as plain text
- [x] Auto-paste functionality (via `keyboard` module)

### 8.6 本地儲存 + 雲端匯出 (Storage)
- [x] Save audio as WAV (`data/recordings/`)
- [x] Save data as JSON
- [x] Organize by date/time
- [x] Cloud export logic (Local JSON/WAV bundle, ready for extension)

---

## ✅ Phase 8 Status: READY FOR COMPILATION

All core features for Phase 8 are implemented and verified in the unified "Ultimate" GUI. The system is optimized for Windows CPU offline use.

## 📅 Next Steps (Final Release)

- [ ] **Windows Final Compilation**
- [ ] **Installer Generation (Inno Setup)**
- [ ] **Final Offline Benchmark (8-WAV suite)**
- [ ] **Startup Time & Memory Validation**