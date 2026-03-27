"""
SoapVoice FastAPI 主入口

醫療語音轉 SOAP 病歷系統
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from src.api.websocket import router as websocket_router
from src.api.rest import router as rest_router
from src.api.consultation_api import router as consultation_router
from src.api.extended_api import router as extended_router
from src.api.webhook_api import router as webhook_router
from src.api.file_monitor_api import router as file_monitor_router
from src.llm.ollama_engine import initialize_engine, ModelConfig


# 載入環境變數
load_dotenv()

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
    ).split(","),
    "llm_model": os.getenv("LLM_MODEL", "Qwen/Qwen3-32B-Instruct"),
    "llm_gpu_memory": float(os.getenv("LLM_GPU_MEMORY", "0.9")),
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

    yield

    # 關閉時清理
    logger.info("Shutting down SoapVoice API...")


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

# 靜態檔案服務
import pathlib

static_dir = pathlib.Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 註冊路由
app.include_router(websocket_router, prefix="/api/v1", tags=["WebSocket"])
app.include_router(rest_router, prefix="/api/v1", tags=["Clinical NLP"])
app.include_router(consultation_router, prefix="/api/v1", tags=["Consultation Flow"])
app.include_router(extended_router, prefix="/api/v1", tags=["Extended Pipeline"])
app.include_router(webhook_router, tags=["Webhooks"])
app.include_router(file_monitor_router, tags=["File Monitor"])


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
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("DEV_MODE", "false").lower() == "true",
    )
