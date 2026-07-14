"""
SoapVoice FastAPI 主入口

醫療語音轉 SOAP 病歷系統
"""

import os
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# 載入環境變數（必須在所有模組導入之前）
load_dotenv()

# Forced reload trigger

# GPU 模式現已支援 — 環境變數由 .env 控制
# 見 config/models.yaml 與 .env 中的 WHISPER_DEVICE、WHISPER_COMPUTE_TYPE、LLAMA_N_GPU_LAYERS

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from src.api.websocket import router as websocket_router
from src.api.rest import router as rest_router
from src.api.consultation_api import router as consultation_router
from src.api.extended_api import router as extended_router
from src.api.webhook_api import router as webhook_router
from src.api.file_monitor_api import router as file_monitor_router
from src.api.cloud_api import router as cloud_router
from src.api.ocr_api import router as ocr_router
from src.api.patient_records_api import router as patient_records_router
from src.api.lan_health_api import router as lan_health_router
from src.api.lan_process_api import router as lan_process_router
from src.api.metrics_api import router as metrics_router
from src.api.alerts_api import router as alerts_router
from src.llm.ollama_engine import initialize_engine, ModelConfig

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# 全域配置
APP_CONFIG = {
    "title": "SoapVoice API",
    "description": "醫療語音轉 SOAP 病歷系統",
    "version": "0.1.0",
    "cors_origins": os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://192.168.1.100:3000"
    ).split(",") + [
        "https://doctor-toolbox.com",
        "https://www.doctor-toolbox.com",
    ],
    "llm_model": os.getenv("LLM_MODEL", "Qwen/Qwen3-32B-Instruct"),
    "llm_gpu_memory": float(os.getenv("LLM_GPU_MEMORY", "0.9")),
    "api_key": os.getenv("SOAPVOICE_API_KEY", ""),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    # 啟動時初始化
    logger.info("Starting SoapVoice API...")

    # 初始化 LLM 引擎（可選，按需啟用）
    if os.getenv("INITIALIZE_LLM", "false").lower() == "true":
        try:
            logger.info("Initializing LLM engine...")
            config = ModelConfig(
                model_id=APP_CONFIG["llm_model"],
                gpu_memory_utilization=APP_CONFIG["llm_gpu_memory"],
            )
            initialize_engine(config)
            logger.info("LLM engine initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM engine: {e}")

    # 預加載 Extended Pipeline (ASR + NLP)
    try:
        from src.api.extended_api import get_extended_engine
        logger.info("Pre-loading Extended SOAP Pipeline...")
        engine = await get_extended_engine()
        if hasattr(engine, "_whisper"):
             logger.info(f"Extended SOAP Pipeline pre-loaded successfully (Whisper object: {engine._whisper.model})")
        else:
             logger.info("Extended SOAP Pipeline pre-loaded successfully")
    except Exception as e:
        logger.warning(f"Failed to pre-load Extended SOAP Pipeline: {e}")

    # 初始化病患記錄 DB
    try:
        from src.db.patient_records_db import get_patient_records_db, init_schema
        db = await get_patient_records_db()
        await init_schema(db)
        logger.info("Patient records DB initialized (WAL mode, 5 tables)")
    except Exception as e:
        logger.warning(f"Patient records DB init failed (non-fatal): {e}")

    # Phase 12-01：啟動 MetricsCollector 背景任務
    try:
        from src.utils.metrics_collector import MetricsCollector
        metrics_collector = MetricsCollector(update_interval=2.0)
        await metrics_collector.start_background_task()
        app.state.metrics_collector = metrics_collector
        logger.info("Metrics collector started (2s update interval)")
    except Exception as e:
        logger.warning(f"Failed to start metrics collector: {e}")

    # Phase 12-03：初始化 AlertManager 與警報 DB
    try:
        from src.utils.alert_manager import AlertManager
        from src.db.alerts_db import init_alerts_schema
        from src.db.patient_records_db import get_patient_records_db
        alert_manager = AlertManager(auto_clear_enabled=True)
        app.state.alert_manager = alert_manager
        # 在同一個 DB 連線上初始化警報表
        db = await get_patient_records_db()
        await init_alerts_schema(db)
        app.state.alerts_db = db
        logger.info("AlertManager 初始化完成，警報表 Schema 已建立")
    except Exception as e:
        logger.warning(f"AlertManager 初始化失敗（非致命）: {e}")

    yield

    # 關閉時清理
    logger.info("Shutting down SoapVoice API...")

    # Phase 12-01：停止 MetricsCollector 背景任務
    try:
        metrics_collector = getattr(app.state, "metrics_collector", None)
        if metrics_collector is not None:
            await metrics_collector.stop_background_task()
            logger.info("Metrics collector stopped")
    except Exception as e:
        logger.warning(f"Failed to stop metrics collector: {e}")

    # 關閉病患記錄 DB
    try:
        from src.db.patient_records_db import close_patient_records_db
        await close_patient_records_db()
        logger.info("Patient records DB closed")
    except Exception as e:
        logger.warning(f"Patient records DB close failed: {e}")


# 建立 FastAPI 應用程式
app = FastAPI(
    title=APP_CONFIG["title"],
    description=APP_CONFIG["description"],
    version=APP_CONFIG["version"],
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=APP_CONFIG["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── LAN 白名單 IP 驗證 ─────────────────────────────────────────
# 只允許區域網路（192.168.x.x / 10.x.x.x / 127.0.0.1）呼叫 /api/v1/lan/* 端點
# 對應 threat_model T-11-01 (Spoofing) 緩解
def is_lan_ip(ip: str) -> bool:
    """檢查 IP 是否屬於允許的 LAN 範圍

    允許範圍：
    - 192.168.0.0 - 192.168.255.255
    - 10.0.0.0 - 10.255.255.255
    - 127.0.0.1（本機開發/測試）
    - localhost（測試環境別名）

    Args:
        ip: 客戶端 IP 字串（從 request.client.host 取得）

    Returns:
        True 表示在白名單內，False 表示應拒絕
    """
    if not ip:
        return False
    # 本機別名（含 FastAPI TestClient 預設 'testclient' 主機名）
    if ip in {"127.0.0.1", "localhost", "::1", "testclient"}:
        return True
    # 192.168.x.x
    if ip.startswith("192.168."):
        return True
    # 10.x.x.x
    if ip.startswith("10."):
        return True
    return False


@app.middleware("http")
async def lan_whitelist_middleware(request: Request, call_next):
    """LAN 端點白名單 middleware

    僅針對 /api/v1/lan/* 與 /api/v1/health 端點檢查 IP 白名單。
    其他端點（websocket、clinical、records）走既有的 api_key_middleware 路徑。

    決策邏輯：
    - 路徑非 /api/v1/lan/* 也非 /api/v1/health → 直接放行
    - 客戶端 IP 屬 LAN 範圍 → 放行
    - 否則回傳 403 含明確錯誤訊息
    """
    path = request.url.path
    # 只攔截 LAN 相關路徑
    if path.startswith("/api/v1/lan") or path == "/api/v1/health":
        client_ip = request.client.host if request.client else ""
        if not is_lan_ip(client_ip):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "lan_whitelist_denied",
                    "detail": f"IP {client_ip} not in LAN whitelist",
                    "allowed_ranges": ["192.168.x.x", "10.x.x.x", "127.0.0.1"],
                },
            )
    return await call_next(request)


# API Key 驗證中間件
@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """驗證 /api/v1/clinical/* 端點的 API Key（本地網路免驗證）"""
    # 跳過不需要驗證的路徑
    skip_paths = {"/health", "/api/v1/health", "/", "/test.html", "/api/v1"}
    if request.url.path in skip_paths or request.url.path.startswith("/static"):
        return await call_next(request)

    # 只檢查 /api/v1/clinical/* 端點
    if request.url.path.startswith("/api/v1/clinical"):
        # 本地網路（localhost, 127.0.0.1, 192.168.x.x）免驗證
        client_host = request.client.host if request.client else ""
        is_local = client_host in {"localhost", "127.0.0.1", "testclient"} or client_host.startswith("192.168.") or client_host.startswith("10.")

        if not is_local:
            api_key = request.headers.get("X-API-Key", "")
            if not api_key or api_key != APP_CONFIG["api_key"]:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key"},
                )

    return await call_next(request)

# 靜態檔案服務
import pathlib

static_dir = pathlib.Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 註冊路由
# Phase 11-01：LAN 健康檢查必須優先註冊，搶在 websocket_router 之前佔用 /api/v1/health
app.include_router(lan_health_router, prefix="/api/v1", tags=["LAN Health"])
# Phase 12-01：監控指標 SSE 與歷史查詢端點（在 websocket 之前，避免路由衝突）
app.include_router(metrics_router, prefix="/api/v1", tags=["Metrics"])
# Phase 12-03：警報管理端點
app.include_router(alerts_router)
app.include_router(websocket_router, prefix="/api/v1", tags=["WebSocket"])
app.include_router(rest_router, prefix="/api/v1", tags=["Clinical NLP"])
app.include_router(consultation_router, prefix="/api/v1", tags=["Consultation Flow"])
app.include_router(extended_router, prefix="/api/v1", tags=["Extended Pipeline"])
app.include_router(webhook_router, tags=["Webhooks"])
app.include_router(file_monitor_router, tags=["File Monitor"])
app.include_router(cloud_router, prefix="/api/v1", tags=["Cloud Integration"])
app.include_router(ocr_router, prefix="/api/v1", tags=["OCR"])
app.include_router(patient_records_router, prefix="/api/v1", tags=["Patient Records"])
# Phase 11-01：LAN 瘦客戶端 process 端點（健康檢查已於頂端優先註冊）
app.include_router(lan_process_router, prefix="/api/v1", tags=["LAN Processing"])


@app.get("/")
async def root():
    """根路徑 - 服務首頁"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "service": "SoapVoice API",
        "version": APP_CONFIG["version"],
        "status": "running",
    }


@app.get("/test.html")
async def test_page():
    """測試頁面"""
    test_file = static_dir / "test.html"
    if test_file.exists():
        return FileResponse(str(test_file))
    return {"error": "test.html not found"}


@app.get("/health")
async def health_check():
    """健康檢查"""
    return {
        "status": "healthy",
        "service": "SoapVoice API",
        "version": APP_CONFIG["version"],
    }


@app.get("/api/v1")
async def api_v1_root():
    """API v1 根路徑"""
    return {
        "service": "SoapVoice API v1",
        "endpoints": {
            "websocket": "/api/v1/ws/transcribe",
            "health": "/api/v1/health",
            "stats": "/api/v1/stats",
            "clinical": {
                "normalize": "/api/v1/clinical/normalize",
                "icd10": "/api/v1/clinical/icd10",
                "soap_classify": "/api/v1/clinical/classify/soap",
                "soap_generate": "/api/v1/clinical/soap/generate",
            },
            "consultation": {
                "start": "/api/v1/consultation/start",
                "end": "/api/v1/consultation/end",
                "soap_generate": "/api/v1/consultation/soap/generate",
                "search": "/api/v1/consultation/search",
                "stats": "/api/v1/consultation/stats",
                "sessions": "/api/v1/consultation/sessions",
                "websocket": "/api/v1/consultation/ws",
            },
            "records": {
                "search": "/api/v1/records/search?name=&date_from=&date_to=&page=1&page_size=20",
                "detail": "/api/v1/records/{id}",
                "audit": "/api/v1/records/{id}/audit",
                "amend_soap": "/api/v1/records/{id}/soap",
            },
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8010,  # 使用 8010 避免與 Docker 容器衝突
        reload=os.getenv("DEV_MODE", "false").lower() == "true",
    )
