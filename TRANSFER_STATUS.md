# 🚀 USB Transfer Status — Real-Time Monitor

**Started:** 2026-04-23 (Linux → USB)  
**USB Mount:** `/media/hsu/B2D7-3956`  
**Transfer Size:** 27 GB → USB

---

## 📊 Progress

| Component | Status | Details |
|-----------|--------|---------|
| **Transfer Started** | ✅ | rsync running in background |
| **Current USB Size** | ✅ 5.8 GB | ~22% complete (growing) |
| **Source Size** | ✅ 27 GB | All files ready |
| **Windows Guide** | ✅ | `WINDOWS_QUICK_START.md` created |

---

## ⏱️ Estimated Timeline

- **Transfer Speed:** ~200-500 MB/s (USB 3.0)
- **Total Time:** ~10-15 minutes
- **Expected Completion:** Next 5-10 minutes

---

## ✅ Verification After Transfer Completes

```bash
# On Linux (after rsync finishes):
du -sh /media/hsu/B2D7-3956/SoapVoice
# Should show: ~27 GB (matches source)

ls -la /media/hsu/B2D7-3956/SoapVoice/
# Should show: config/, data/, installer/, models/, scripts/, src/, .planning/
```

---

## 🔌 Next Steps (When Transfer Shows ✅ Complete)

1. **Sync USB:** `sync` (ensures all writes complete)
2. **Unmount USB:** `umount /media/hsu/B2D7-3956`
3. **Eject USB:** Remove from Linux machine
4. **Transfer to Windows:** Insert into Windows machine

---

## 📂 Files Ready on USB

After transfer completes, USB will contain:

```
/SoapVoice/
├── WINDOWS_QUICK_START.md     ← Windows setup guide (READ FIRST)
├── WINDOWS_DEPLOYMENT_SUMMARY.md
├── USB_COPY_COMMAND.sh
├── config/
│   └── models.yaml            ← Optimized config (ASR: medium, OCR: Tesseract)
├── data/
├── installer/
├── models/                     ← Pre-downloaded models (6.8 GB total)
│   ├── gemma-4-E4B-it-Q4_K_M.gguf (5.3 GB)
│   ├── qwen2.5-3b-instruct-q4_k_m.gguf (2.1 GB)
│   └── whisper/ (1.5 GB)
├── scripts/
│   ├── windows_package.ps1    ← Run this on Windows (PowerShell)
│   └── windows_package.bat    ← Or this (Command Prompt)
└── src/
```

---

## 🎯 When Transfer Completes

**On Linux:**
```bash
# Verify transfer
du -sh /media/hsu/B2D7-3956/SoapVoice
# Expected: 27G (or 26-27 GB range)

# Check for all critical folders
ls /media/hsu/B2D7-3956/SoapVoice/{config,models,scripts,src}

# Sync and eject
sync
umount /media/hsu/B2D7-3956
```

**On Windows Machine (Next):**
1. Insert USB → Wait 5-10s
2. Copy `D:\SoapVoice` to `C:\SoapVoice`
3. Read `C:\SoapVoice\WINDOWS_QUICK_START.md`
4. Follow Phase 3-5 instructions

---

**Check status:** `du -sh /media/hsu/B2D7-3956/SoapVoice` (shows current size, should approach 27 GB)

