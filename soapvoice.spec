# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os

ROOT_DIR = Path(SPECPATH)

# 排除非必要的大型套件以壓縮體積
# 保持 fastapi, uvicorn, requests, faster_whisper 等核心依賴
EXCLUDES = [
    'matplotlib', 'scipy', 'torchvision', 'transformers', 
    'numba', 'sklearn', 'pandas', 'opentelemetry', 'triton', 'grpc', 
    'onnxruntime', 'librosa', 'av', 'sounddevice', 'soundfile', 
    'shapely', 'imageio', 'skimage', 'soynlp', 'nagisa', 'pydub', 
    'psutil', 'gevent', 'zope', 'lxml', 'jinja2', 'rich'
]

# 偵測是否在 Wine/Windows 環境
is_windows = os.name == 'nt' or os.getenv('WINEPREFIX') is not None

a = Analysis(
    ['src/gui/desktop_app.py'],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=[
        (str(ROOT_DIR / 'models'), 'models'),
        (str(ROOT_DIR / 'data'), 'data'),
        (str(ROOT_DIR / '.env'), '.'),
        (str(ROOT_DIR / 'prompt.md'), '.'),
        (str(ROOT_DIR / 'keywords.json'), '.'),
        (str(ROOT_DIR / 'config'), 'config'),
    ],
    hiddenimports=[
        'llama_cpp', 'llama_cpp.llama', 'llama_cpp._internals',
        'faster_whisper', 'ctranslate2',
        'ttkbootstrap', 'tkinter', 'PIL',
        'pyaudio', 'pyperclip', 'mss',
        'sentence_transformers', 'chromadb',
        'fastapi', 'uvicorn', 'requests', 'pydantic', 'httpx',
        'websockets', 'starlette', 'typing_extensions'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SoapVoice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
)
