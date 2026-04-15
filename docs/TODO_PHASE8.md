# SoapVoice Phase 8 TODO

## Current Phase: Phase 8 - 門診語音錄製系統

### 8.1 系統匣安裝 (System Tray)
- [ ] Create system tray icon with menu
- [ ] Implement minimize to tray on close
- [ ] Add startup auto-launch option
- [ ] Add recording status indicator

### 8.2 Screenshot + OCR Workflow
- [ ] Add screenshot capture hotkey
- [ ] Implement EasyOCR for patient info extraction
- [ ] Extract: name, birthday, ID, MRN, timestamp, doctor
- [ ] Show confirmation dialog for extracted data
- [ ] Allow manual editing of extracted data

### 8.3 Voice Recording with LLM SOAP
- [ ] Implement audio recording with PyAudio
- [ ] Integrate ASR for transcription
- [ ] Call LLM for SOAP generation
- [ ] Handle recording states (start/stop/save)

### 8.4 浮動視窗 (Results Window)
- [ ] Create right-side floating window
- [ ] Display patient information (editable)
- [ ] Display transcript
- [ ] Display SOAP result
- [ ] Add copy to clipboard button
- [ ] Add save button
- [ ] Add cloud export button

### 8.5 HIS 剪貼簿整合 (Clipboard)
- [ ] One-click copy SOAP to clipboard
- [ ] Format SOAP as plain text
- [ ] Show copy success notification
- [ ] Optional: auto-paste to active window

### 8.6 本地儲存 + 雲端匯出 (Storage)
- [ ] Save audio as WAV
- [ ] Save data as JSON
- [ ] Organize by date/time
- [ ] Implement cloud export (Google Drive/SMB)
- [ ] Export as ZIP package

---

## Blocked / Waiting

- Need to verify EasyOCR Chinese recognition accuracy
- Need to decide on cloud storage backend
- May need HIS integration specifics

## Notes

- Focus on offline-first, then cloud sync
- Patient data must be handled securely (local storage only by default)
- Consider HIPAA/Taiwan medical data regulations