"""
WebSocket API 端點

提供即時語音轉文字的 WebSocket 接口
支援音頻串流傳輸與即時轉錄結果回傳
"""

import json
import asyncio
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

from src.asr.whisper_model import WhisperModel
from src.asr.stream_transcriber import StreamTranscriber


# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 全局變數
_websocket_config: Dict[str, Any] = {}
_active_transcribers: Dict[str, StreamTranscriber] = {}


# APIRouter
router = APIRouter()


def set_websocket_config(config: Dict[str, Any]) -> None:
    """設置 WebSocket 配置

    Args:
        config: WebSocket 配置字典
    """
    global _websocket_config
    _websocket_config = config


def get_websocket_config() -> Dict[str, Any]:
    """獲取 WebSocket 配置

    Returns:
        WebSocket 配置字典
    """
    return _websocket_config


class ConnectionManager:
    """WebSocket 連接管理器

    管理和追蹤所有活跃的 WebSocket 連接
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_count = 0

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """接受新的 WebSocket 連接

        Args:
            websocket: WebSocket 連接
            client_id: 客戶端 ID
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_count += 1
        logger.info(
            f"Client {client_id} connected. Total connections: {len(self.active_connections)}"
        )

    def disconnect(self, client_id: str) -> None:
        """斷開 WebSocket 連接

        Args:
            client_id: 客戶端 ID
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(
                f"Client {client_id} disconnected. Total connections: {len(self.active_connections)}"
            )

    async def send_message(self, client_id: str, message: Dict[str, Any]) -> bool:
        """發送訊息到客戶端

        Args:
            client_id: 客戶端 ID
            message: 訊息內容

        Returns:
            是否發送成功
        """
        if client_id not in self.active_connections:
            return False

        try:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Error sending message to {client_id}: {e}")
            self.disconnect(client_id)
            return False

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """廣播訊息到所有連接

        Args:
            message: 訊息內容
        """
        disconnected = []
        for client_id in self.active_connections:
            success = await self.send_message(client_id, message)
            if not success:
                disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)


# 全局連接管理器
manager = ConnectionManager()


def get_transcriber(client_id: str) -> Optional[StreamTranscriber]:
    """獲取客戶端的轉錄器

    Args:
        client_id: 客戶端 ID

    Returns:
        StreamTranscriber 或 None
    """
    return _active_transcribers.get(client_id)


def create_transcriber(client_id: str, whisper_model: WhisperModel, **kwargs) -> StreamTranscriber:
    """為客戶端創建轉錄器

    Args:
        client_id: 客戶端 ID
        whisper_model: Whisper 模型
        **kwargs: 額外參數

    Returns:
        StreamTranscriber 實例
    """
    transcriber = StreamTranscriber(whisper_model=whisper_model, **kwargs)
    _active_transcribers[client_id] = transcriber
    return transcriber


def remove_transcriber(client_id: str) -> None:
    """移除客戶端的轉錄器

    Args:
        client_id: 客戶端 ID
    """
    if client_id in _active_transcribers:
        del _active_transcribers[client_id]


@router.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    """WebSocket 即時語音轉文字端點

    支援以下訊號類型:
    - start: 開始新的轉錄會話
    - chunk: 傳送音頻塊
    - end: 結束轉錄會話

    訊息格式 (客戶端 -> 服務器):
    {
        "type": "start|chunk|end",
        "data": {...},
        "client_id": "optional-client-id"
    }

    訊息格式 (服務器 -> 客戶端):
    {
        "type": "result|error|status",
        "data": {...}
    }
    """
    client_id = None

    try:
        # 接受 WebSocket 連接
        await websocket.accept()

        logger.info(f"WebSocket 連接已接受：{id(websocket)}")

        # 接收客戶端識別資訊
        initial_data = await websocket.receive_text()
        try:
            initial_json = json.loads(initial_data)
            client_id = initial_json.get("client_id", f"client_{id(websocket)}")
        except json.JSONDecodeError:
            client_id = f"client_{id(websocket)}"

        # 添加到管理器
        manager.connect(websocket, client_id)

        logger.info(f"客戶端 {client_id} 已連接")

        # 發送連接成功訊息
        await manager.send_message(
            client_id,
            {
                "type": "status",
                "data": {
                    "status": "connected",
                    "client_id": client_id,
                    "message": "WebSocket 連接已建立",
                },
            },
        )

        logger.info(f"已發送連接確認訊息到 {client_id}")

        # 創建轉錄器（延遲初始化 Whisper 模型）
        transcriber = create_transcriber(
            client_id=client_id,
            whisper_model=None,  # 延遲載入
            language=None,
            task="transcribe",
            beam_size=5,
        )

        logger.info(f"轉錄器已創建（模型未載入）：{client_id}")

        # 持續處理訊息
        model_loaded = False

        while True:
            try:
                # 接收文字訊息（使用超時）
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                await manager.send_message(
                    client_id,
                    {
                        "type": "status",
                        "data": {"status": "timeout", "message": "連接超時，準備斷開"},
                    },
                )
                break

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await manager.send_message(
                    client_id, {"type": "error", "data": {"error": "Invalid JSON format"}}
                )
                continue
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                break

            message_type = message.get("type")
            message_data = message.get("data", {})

            if message_type == "start":
                # 開始新的轉錄會話 - 載入模型
                if not model_loaded:
                    logger.info("收到 start 訊息，正在載入 Whisper 模型...")
                    from src.asr.whisper_model import WhisperModel
                    whisper_model = WhisperModel(model_id="large-v3", device="cuda", compute_type="float16")
                    transcriber.load_model(whisper_model)
                    model_loaded = True
                    logger.info("✓ Whisper 模型載入完成")

                # 開始轉錄會話
                try:
                    result = transcriber.start_stream()
                    await manager.send_message(
                        client_id,
                        {
                            "type": "status",
                            "data": {
                                "status": "stream_started",
                                "message": "轉錄會話已開始",
                                **result,
                            },
                        },
                    )
                    logger.info(f"已發送 stream_started 到 {client_id}")
                except RuntimeError as e:
                    await manager.send_message(
                        client_id, {"type": "error", "data": {"error": str(e)}}
                    )

            elif message_type == "chunk":
                # 處理音頻塊
                audio_data = message_data.get("audio")

                if audio_data:
                    # 解碼 base64 音頻
                    import base64

                    try:
                        audio_bytes = base64.b64decode(audio_data)
                        logger.debug(f"收到音頻塊：{len(audio_bytes)} bytes")
                    except Exception as e:
                        logger.error(f"音頻解碼失敗：{e}")
                        await manager.send_message(
                            client_id,
                            {
                                "type": "error",
                                "data": {"error": f"Failed to decode audio: {str(e)}"},
                            },
                        )
                        continue

                    # 處理音頻塊
                    try:
                        result = transcriber.process_chunk(audio_bytes)
                        logger.debug(f"轉錄結果：{result}")
                        await manager.send_message(client_id, {"type": "result", "data": result})
                    except Exception as e:
                        logger.error(f"音頻處理失敗：{e}")
                        await manager.send_message(
                            client_id,
                            {"type": "error", "data": {"error": f"Processing error: {str(e)}"}},
                        )
                else:
                    logger.warning("收到 chunk 但沒有音頻數據")
                    await manager.send_message(
                        client_id, {"type": "error", "data": {"error": "No audio data provided"}}
                    )

            elif message_type == "end":
                # 結束轉錄會話
                logger.info(f"收到結束訊息：{client_id}")
                try:
                    result = transcriber.end_stream()
                    logger.info(f"轉錄會話結束：{result}")
                    await manager.send_message(client_id, {"type": "result", "data": result})
                except Exception as e:
                    logger.error(f"結束串流失敗：{e}")
                    await manager.send_message(
                        client_id,
                        {"type": "error", "data": {"error": f"End stream error: {str(e)}"}},
                    )
                finally:
                    # 清理轉錄器
                    logger.info(f"清理轉錄器：{client_id}")
                    remove_transcriber(client_id)

            else:
                await manager.send_message(
                    client_id,
                    {"type": "error", "data": {"error": f"Unknown message type: {message_type}"}},
                )

    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await manager.send_message(client_id, {"type": "error", "data": {"error": str(e)}})
        except:
            pass
    finally:
        # 清理資源
        if client_id:
            manager.disconnect(client_id)
            remove_transcriber(client_id)


@router.get("/health")
async def websocket_health():
    """WebSocket 服務健康檢查"""
    return JSONResponse(
        {
            "status": "healthy",
            "service": "websocket",
            "active_connections": len(manager.active_connections),
            "total_connections": manager.connection_count,
        }
    )


@router.get("/stats")
async def websocket_stats():
    """WebSocket 服務統計資訊"""
    return JSONResponse(
        {
            "active_connections": len(manager.active_connections),
            "total_connections": manager.connection_count,
            "active_transcribers": len(_active_transcribers),
        }
    )
