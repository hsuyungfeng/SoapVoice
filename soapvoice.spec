# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT_DIR = Path(SPECPATH)

a = Analysis(
    ['src/gui/desktop_app.py'],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=[
        (str(ROOT_DIR / 'models'), 'models'),
        (str(ROOT_DIR / 'data'), 'data'),
        (str(ROOT_DIR / '.env'), '.'),
    ],
    hiddenimports=[
        'llama_cpp', 'llama_cpp.llama', 'llama_cpp._internals',
        'faster_whisper', 'ctranslate2',
        'ttkbootstrap', 'tkinter', 'PIL',
        'pyaudio', 'pyperclip', 'mss',
        'sentence_transformers', 'chromadb',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'torch', 'torchaudio', 'torchvision', 'transformers', 'numba', 'sklearn', 'pandas', 'opentelemetry', 'triton', 'grpc', 'onnxruntime', 'librosa', 'cv2', 'av', 'sounddevice', 'soundfile', 'easyocr', 'shapely', 'imageio', 'skimage', 'opencc', 'soynlp', 'nagisa', 'pydub', 'psutil', 'gevent', 'zope', 'lxml', 'jinja2', 'rich', 'anyio', 'orjson', 'uvicorn', 'websockets', 'fastapi', 'pydantic', 'httpx', 'requests', 'aiohttp', 'chromadb', 'sentence_transformers', 'llama_cpp', 'faster_whisper', 'ctranslate2'],
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
)
