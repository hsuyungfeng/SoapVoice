# ✅ SoapVoice Windows Deployment Checklist

**Phase:** 9/9 (Final Windows Packaging)  
**Status:** USB Transfer In Progress  
**Last Updated:** 2026-04-23

---

## 📋 Pre-Transfer Verification (Linux)

- [x] Project size verified: 27 GB
- [x] USB mounted: `/media/hsu/B2D7-3956`
- [x] Transfer script ready: `USB_COPY_COMMAND.sh`
- [x] Windows scripts ready: `windows_package.ps1` & `.bat`
- [x] Configuration optimized: ASR=medium, OCR=Tesseract
- [x] Models downloaded: 6.8 GB (Whisper, Gemma-4, Qwen2.5)
- [x] Windows guides created: `WINDOWS_QUICK_START.md`
- [ ] Transfer to USB completed (IN PROGRESS)

---

## 🚀 Transfer Phase (Linux → USB)

- [ ] Start transfer: `rsync -av --progress ~/Desktop/SoapVoice /media/hsu/B2D7-3956/`
  - Status: ✅ Started (5.8 GB transferred so far)
  - Est. time remaining: ~5-10 minutes
  - Speed: ~200-500 MB/s

- [ ] Verify USB contents:
  ```bash
  du -sh /media/hsu/B2D7-3956/SoapVoice
  # Expected: 27 GB
  ```

- [ ] Sync and eject USB:
  ```bash
  sync
  umount /media/hsu/B2D7-3956
  ```

---

## 💾 USB → Windows Transfer (Next Phase)

**Prerequisites on Windows:**
- [ ] Windows 10 or 11 (any version)
- [ ] Admin access to C:\ drive
- [ ] 60+ GB free disk space on C:\
- [ ] 4+ GB RAM available

**Transfer Steps:**
- [ ] Insert USB into Windows machine
- [ ] Wait 5-10 seconds for recognition
- [ ] Open Command Prompt (Admin)
- [ ] Run: `xcopy /E /I /Y D:\SoapVoice C:\SoapVoice`
  - (Replace `D:` if USB is different letter)
- [ ] Wait for "X file(s) copied" message
- [ ] Verify: `dir C:\SoapVoice\`

---

## 🐍 Python & uv Installation (Windows)

- [ ] Download Python 3.11+ from https://www.python.org/downloads/windows/
- [ ] Run installer
  - ✅ Check "Add Python to PATH"
  - ✅ Click "Install Now"
  - ✅ Wait 2-3 minutes
- [ ] Verify: `python --version` (should show 3.11+)
- [ ] Install uv: `pip install uv`
- [ ] Verify: `uv --version` (should show version)

---

## 📦 Packaging & Build (Windows)

**Option A: PowerShell (Recommended)**
- [ ] Open PowerShell (Admin)
- [ ] Navigate: `cd C:\SoapVoice`
- [ ] Run: `.\scripts\windows_package.ps1`
- [ ] If execution policy error: `Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser`
- [ ] Wait 10-20 minutes for completion
- [ ] Watch for: `[SUCCESS] 打包完成！` message

**Option B: Command Prompt**
- [ ] Open Command Prompt (Admin)
- [ ] Navigate: `cd C:\SoapVoice`
- [ ] Run: `scripts\windows_package.bat`
- [ ] Wait 10-20 minutes

**Option C: Manual**
- [ ] `uv sync`
- [ ] `uv add --group dev pyinstaller`
- [ ] `pyinstaller --clean soapvoice.spec`

---

## ✅ Verification & Testing (Windows)

**Output Files:**
- [ ] `dist\SoapVoice.exe` exists (50-100 MB)
- [ ] `installer\SoapVoiceSetup.exe` exists (15-20 MB) — optional

**Executable Test:**
- [ ] Run: `.\dist\SoapVoice.exe --help` (no errors)
- [ ] Or double-click `SoapVoice.exe`
- [ ] Wait 30-40 seconds for first launch
- [ ] GUI window appears

**Models Verification:**
- [ ] ASR (Whisper) loads: "Loading ASR model..."
- [ ] OCR (Tesseract) ready: "OCR engine initialized"
- [ ] LLM (Gemma-4) initializes: "Loading language model..."
- [ ] Web interface: Open http://localhost:5000 in browser

---

## 📊 Final System Check (Windows)

- [ ] CPU usage normal (< 50% idle)
- [ ] RAM usage: 6-8 GB for LLM
- [ ] Disk usage: ~15 GB installed + models
- [ ] No error messages in console
- [ ] All models cached and ready

---

## 📚 Documentation Files (On USB After Transfer)

- [x] `WINDOWS_QUICK_START.md` — Step-by-step Windows setup (READ FIRST)
- [x] `WINDOWS_DEPLOYMENT_SUMMARY.md` — Complete reference guide
- [x] `TRANSFER_STATUS.md` — Real-time transfer monitor
- [x] `DEPLOYMENT_CHECKLIST.md` — This checklist
- [x] `USB_COPY_COMMAND.sh` — Linux transfer script
- [x] `config/models.yaml` — Optimized model configuration
- [x] `scripts/windows_package.ps1` — Windows PowerShell build script
- [x] `scripts/windows_package.bat` — Windows batch build script

---

## 🎯 Success Criteria

✅ **Phase Complete When:**

1. ✅ USB transfer finished (27 GB copied)
2. ✅ Project copied to C:\SoapVoice
3. ✅ Python 3.11+ installed and verified
4. ✅ uv package manager working
5. ✅ Packaging script executed successfully
6. ✅ dist\SoapVoice.exe created (50-100 MB)
7. ✅ EXE runs without errors
8. ✅ GUI launches within 30-40 seconds
9. ✅ All models load successfully
10. ✅ Web interface accessible at http://localhost:5000

---

## 📞 Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| USB not detected (Linux) | `lsblk` to find device, `mount /dev/sdXX /media/usb` |
| Transfer slow | Check USB 3.0 (not 2.0), ensure no other writes |
| Python not found (Windows) | Re-run installer, check "Add Python to PATH" |
| PowerShell execution error | `Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser` |
| uv not installed | `pip install --upgrade uv` |
| PyInstaller fails | Check `build\soapvoice\warn-soapvoice.txt` |
| EXE won't launch | Run `.\dist\SoapVoice.exe --help` for errors |
| Models not loading | Verify `models/` folder exists and has all 3 subdirs |
| Out of disk space | Ensure 60+ GB free, delete `build/` after completion |

---

## ⏱️ Total Timeline

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 1 | Linux → USB transfer | 10-15 min | 🟡 In Progress |
| 2 | USB → Windows copy | 5-10 min | ⏳ Pending |
| 3 | Python + uv install | 5-10 min | ⏳ Pending |
| 4 | Packaging script | 10-20 min | ⏳ Pending |
| 5 | Verify & test | 2-3 min | ⏳ Pending |
| **TOTAL** | | **~50-60 min** | 🟡 In Progress |

---

## 🎉 When Complete

**On Windows Machine:**
- ✅ `dist\SoapVoice.exe` is your main executable
- ✅ Double-click or run from Command Prompt
- ✅ No internet required (fully offline)
- ✅ All models included (~6.8 GB)
- ✅ Suitable for real-time clinical use

**Optional:**
- ✅ `installer\SoapVoiceSetup.exe` for professional installation
- ✅ Deploy to other Windows machines: copy EXE + models folder

---

**Version:** 0.8.0  
**Last Updated:** 2026-04-23  
**Created:** Phase 9 Windows Packaging Handoff  

🚀 **Ready to deploy!**

