# 🪟 SoapVoice Windows Quick Start Guide

**For Windows 10/11 Machine** | Copy this to USB after Linux transfer completes

---

## 📋 Phase Overview

| Phase | Task | Time | Machine |
|-------|------|------|---------|
| 1 | Copy Linux → USB | 5-10 min | Linux ✅ |
| 2 | Copy USB → Windows | 5-10 min | Windows (Next) |
| 3 | Install Python & uv | 5-10 min | Windows |
| 4 | Run packaging | 10-20 min | Windows |
| 5 | Verify & test | 2-3 min | Windows |
| **Total** | | **~50-60 min** | |

---

## 🚀 Phase 2: USB → Windows Transfer

### Step 1: Insert USB & Copy Project

1. **Insert USB drive** into Windows machine
2. **Wait 5-10 seconds** for it to be recognized
3. **Open File Explorer** (Win + E)
4. **Locate USB drive** (usually `D:\`, `E:\`, or `F:\`)

**Option A: Command Line (Recommended - Faster)**
```cmd
REM Open Command Prompt as Administrator
REM Press Win + X → A (or right-click Start → Command Prompt Admin)

cd C:\
xcopy /E /I /Y D:\SoapVoice C:\SoapVoice

REM Replace D: with your USB drive letter if different
REM This copies all files including subdirectories
```

**Option B: File Explorer**
- Right-click `SoapVoice` folder on USB
- Select "Copy"
- Navigate to `C:\` in File Explorer
- Right-click → "Paste"
- Wait for completion (5-10 minutes for 27 GB)

### Step 2: Verify Transfer

```cmd
cd C:\SoapVoice
dir

REM You should see these folders:
REM   config/
REM   data/
REM   installer/
REM   models/
REM   scripts/
REM   src/
REM   .planning/
REM   pyproject.toml
REM   WINDOWS_DEPLOYMENT_SUMMARY.md
```

✅ **If all folders appear, transfer is complete!**

---

## 🐍 Phase 3: Install Python & uv

### Step 1: Install Python 3.11+

1. **Download Python**
   - Go to: https://www.python.org/downloads/windows/
   - Download **Python 3.13** (or 3.11+ latest)

2. **Run Installer**
   - Double-click downloaded `.exe` file
   - ⚠️ **CRITICAL:** Check "Add Python to PATH" ✅
   - Click "Install Now"
   - Wait 2-3 minutes

3. **Verify Installation**
   ```cmd
   python --version
   REM Should show: Python 3.13.x (or similar)
   ```

### Step 2: Install uv

```cmd
pip install uv
uv --version
REM Should show version number (e.g., 0.1.45)
```

✅ **If both show version numbers, Python is ready!**

---

## 📦 Phase 4: Run Windows Packaging

### Option A: PowerShell (Recommended - Fully Automated)

```powershell
REM Open PowerShell as Administrator
REM Press Win + X → I (or right-click Start → Windows Terminal Admin)

cd C:\SoapVoice
.\scripts\windows_package.ps1

REM If you see execution policy error:
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser
REM Then retry:
.\scripts\windows_package.ps1
```

**What this script does:**
- Runs `uv sync` (install dependencies)
- Compiles with PyInstaller
- Creates `dist\SoapVoice.exe`
- Builds Windows installer (optional)
- Shows progress and success message

### Option B: Command Prompt (Batch File)

```cmd
REM Open Command Prompt as Administrator
cd C:\SoapVoice
scripts\windows_package.bat
```

### Option C: Manual (If scripts fail)

```cmd
cd C:\SoapVoice

REM Install dependencies
uv sync

REM Add PyInstaller
uv add --group dev pyinstaller

REM Build executable
pyinstaller --clean soapvoice.spec

REM Build installer (optional)
REM Requires Inno Setup: https://jrsoftware.org/isdl.php
```

**Expected runtime:** 10-20 minutes (depends on system speed)

---

## ✅ Phase 5: Verify & Test

### Step 1: Check Output Files

```cmd
cd C:\SoapVoice

REM List executable
dir dist\SoapVoice.exe
REM Should show file size: ~50-100 MB

REM List installer (optional)
dir installer\SoapVoiceSetup.exe
REM Should show file size: ~15-20 MB
```

### Step 2: Test Executable

```cmd
REM Test with --help flag
.\dist\SoapVoice.exe --help
REM Should show help information without errors

REM Or double-click to launch GUI
REM GUI window should appear in 5-10 seconds
```

### Step 3: Verify Models Loaded

When GUI launches, you should see:
- ✅ ASR model (Whisper Medium) - loading message
- ✅ OCR engine (Tesseract) - ready
- ✅ LLM (Gemma-4) - initializing
- ✅ Web interface accessible at `http://localhost:5000`

---

## 📊 What You Get

### Main Executable
- **File:** `dist\SoapVoice.exe`
- **Size:** 50-100 MB
- **Usage:** Double-click or run from command line
- **Network:** None required (fully offline)

### Windows Installer (Optional)
- **File:** `installer\SoapVoiceSetup.exe`
- **Size:** 15-20 MB
- **Usage:** Professional installation with Start Menu shortcuts
- **Command:** `SoapVoiceSetup.exe /SILENT /SUPPRESSMSGBOXES` (silent install)

### Included Models
| Model | Size | Purpose |
|-------|------|---------|
| Whisper Medium | 1.5 GB | Speech-to-text (ASR) |
| Gemma-4 | 5.3 GB | Main LLM for SOAP generation |
| Qwen2.5 | 2-4 GB | Secondary LLM option |
| Tesseract | ~100 MB | OCR for HIS capture |

---

## ⏱️ Performance Expectations

| Component | Load Time | Per-Use Time |
|-----------|-----------|--------------|
| **First Launch** | 30-40 sec | (model loading) |
| **ASR (per 1 min audio)** | 2-3 sec | 3-5 sec |
| **OCR (screen capture)** | 1-2 sec | 0.5-1 sec |
| **LLM (SOAP generation)** | 5-10 sec | 5-15 sec |
| **Typical Consultation** | - | 15-25 sec |

✅ **Suitable for real-time clinical use**

---

## 🆘 Troubleshooting

### "Python not found" Error
```cmd
python --version
REM If shows "command not found":
REM 1. Re-run Python installer
REM 2. Check "Add Python to PATH" during install
REM 3. Restart Command Prompt
REM 4. Retry
```

### "Execution Policy Error" (PowerShell)
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser
REM Then retry: .\scripts\windows_package.ps1
```

### "uv command not found"
```cmd
pip install --upgrade uv
uv --version
REM Should now work
```

### PyInstaller Build Fails
```cmd
REM Check warnings log
type build\soapvoice\warn-soapvoice.txt

REM Try with more verbose output
pyinstaller -v --clean soapvoice.spec
```

### Low Disk Space
- Ensure **60+ GB free** on C:\ drive
- Delete `build\` folder if packaging completes successfully
- Models are stored in: `C:\SoapVoice\models\`

### EXE Won't Start
```cmd
REM Check dependencies
.\dist\SoapVoice.exe --help
REM Or run with debug flag
set DEBUG=1
.\dist\SoapVoice.exe
```

---

## 📚 File Locations

### On Windows Machine
```
C:\SoapVoice\
├── config/                    ← Configuration files
├── data/                      ← Data storage
├── models/                    ← Pre-downloaded models
├── scripts/
│   ├── windows_package.ps1   ← Use this (PowerShell)
│   └── windows_package.bat   ← Or this (Batch)
├── src/                       ← Source code
├── dist/
│   └── SoapVoice.exe         ← Final executable (after packaging)
├── installer/
│   └── SoapVoiceSetup.exe    ← Installer (optional, after packaging)
├── soapvoice.spec            ← PyInstaller spec file
├── pyproject.toml            ← Project configuration
└── WINDOWS_DEPLOYMENT_SUMMARY.md  ← Reference guide
```

---

## 🎯 Success Checklist

- [ ] USB transferred to Windows machine
- [ ] Project copied to `C:\SoapVoice\`
- [ ] Folder structure verified
- [ ] Python 3.11+ installed (`python --version` works)
- [ ] uv installed (`uv --version` works)
- [ ] Packaging script executed
- [ ] `dist\SoapVoice.exe` created (50-100 MB)
- [ ] EXE launches without errors
- [ ] GUI displays correctly
- [ ] Models load in background

---

## 💡 Tips & Tricks

### Fast Packaging on Slow Systems
```cmd
REM Skip Inno Setup (installer) to save time
REM Edit scripts\windows_package.ps1 and comment out the Inno Setup section
```

### Deploy to Multiple Windows Machines
```cmd
REM After packaging, copy these files:
REM - dist\SoapVoice.exe (main executable)
REM - models\ folder (5.3 GB models)
REM - config\ folder (configuration)

REM On target machine:
REM 1. Ensure Python 3.11+ installed
REM 2. Copy files to destination folder
REM 3. Run: .\SoapVoice.exe
```

### Uninstall
```cmd
REM If using installer
REM - Control Panel → Programs → Uninstall a program
REM - Search for "SoapVoice"
REM - Click "Uninstall"

REM If using standalone EXE
REM - Delete C:\SoapVoice folder
REM - Delete shortcut from Desktop/Start Menu (if created)
```

---

## 📞 Need Help?

### Check Logs
```cmd
REM PyInstaller warnings
type build\soapvoice\warn-soapvoice.txt

REM Runtime errors
REM Run with verbose output
set PYTHONVERBOSE=1
.\dist\SoapVoice.exe
```

### Verify Package Integrity
```cmd
REM Check critical files exist
dir config\models.yaml
dir src\main.py
dir scripts\windows_package.ps1
REM All should exist
```

---

**Version:** 0.8.0  
**Last Updated:** 2026-04-23  
**Total Time:** ~50-60 minutes from start to finish  

🎉 **Good luck!**
