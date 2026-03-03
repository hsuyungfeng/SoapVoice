#!/usr/bin/env python3
"""
快速啟動腳本 - 帶詳細日誌
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# 設置詳細日誌
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('/tmp/soapvoice_debug.log'),
        logging.StreamHandler()
    ]
)

from fastapi import FastAPI
from src.api.websocket import router as websocket_router
from src.api.rest import router as rest_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SoapVoice API (Debug Mode)",
    description="醫療語音轉 SOAP 病歷系統 - 調試模式",
    version="0.1.0-debug",
)

app.include_router(websocket_router, prefix="/api/v1", tags=["WebSocket"])
app.include_router(rest_router, prefix="/api/v1", tags=["Clinical NLP"])

@app.on_event("startup")
async def startup_event():
    logger.info("="*60)
    logger.info("SoapVoice API 啟動（調試模式）")
    logger.info("="*60)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "SoapVoice API (Debug)", "version": "0.1.0-debug"}

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("SoapVoice API 關閉")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "quick_start:app",
        host="0.0.0.0",
        port=8000,
        log_level="debug"
    )
