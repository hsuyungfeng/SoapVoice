"""
監控儀表板 API — SSE 即時推送 + 歷史查詢端點

提供兩個主要端點：
1. GET /api/v1/metrics/stream — SSE 推送（每 2 秒推一次 GPU、VRAM、佇列指標）
2. GET /api/v1/metrics/history — 歷史指標查詢（支援分頁與粒度篩選）

用途：Phase 12-01 監控儀表板的核心 API。客戶端透過 EventSource 連接 SSE 端點，
接收實時指標；或透過 history 端點查詢過去的指標趨勢。

Requirements: DASH-01（即時指標推送需求）
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from src.db.patient_records_db import save_metrics_to_db, get_metrics_history

logger = logging.getLogger(__name__)

router = APIRouter()

# 全域 MetricsCollector 實例（由 lifespan 在 app.state 中設定）
def get_metrics_collector():
    """從應用 context 取得 MetricsCollector 實例

    注意：此函式應在 FastAPI lifespan 中初始化 app.state.metrics_collector 後呼叫。
    若 metrics_collector 未初始化，回傳 None。
    """
    # 此處暫時回傳 None，實際呼叫時由路由層從 app.state 取得
    return None


async def metrics_event_generator(
    metrics_collector,
    update_interval: float = 2.0
) -> AsyncGenerator[str, None]:
    """SSE 事件產生器 — 定期推送 GPU 指標

    每隔 update_interval 秒從 metrics_collector 取得最新指標，
    格式化為 SSE 事件 "data: {...}\n\n"，並 yield 推送至客戶端。

    Args:
        metrics_collector: MetricsCollector 實例
        update_interval: 更新週期（秒），預設 2.0

    Yields:
        SSE 格式的事件行
    """
    if metrics_collector is None:
        logger.warning("Metrics collector 未初始化")
        yield f"data: {json.dumps({'error': 'metrics_collector_unavailable'})}\n\n"
        return

    try:
        while True:
            try:
                # 取得最新指標
                metrics = metrics_collector.get_latest_metrics()

                if metrics is None:
                    # 尚未收集到指標，推送占位符
                    event_data = {
                        "status": "initializing",
                        "message": "指標收集中..."
                    }
                else:
                    # 準備指標 JSON
                    event_data = {
                        "timestamp": metrics.timestamp,
                        "gpu_percent": metrics.gpu_percent,
                        "vram_mb": metrics.vram_mb,
                        "queue_length": metrics.queue_length,
                        "gpu_memory_total_mb": metrics.gpu_memory_total_mb,
                    }

                    # 非同步保存至 DB（不阻塞推送）
                    try:
                        asyncio.create_task(
                            save_metrics_to_db(
                                metrics.timestamp,
                                metrics.gpu_percent,
                                metrics.vram_mb,
                                metrics.queue_length,
                            )
                        )
                    except Exception as e:
                        logger.warning(f"背景保存指標失敗: {e}")

                # 推送 SSE 事件
                yield f"data: {json.dumps(event_data)}\n\n"

                # 等待下一個週期
                await asyncio.sleep(update_interval)

            except asyncio.CancelledError:
                logger.info("SSE 連線已關閉（客戶端斷線或伺服器關閉）")
                break
            except Exception as e:
                logger.error(f"指標推送過程中發生錯誤: {e}")
                # 發送錯誤事件但繼續推送
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                await asyncio.sleep(update_interval)

    except GeneratorExit:
        logger.debug("SSE 生成器已終止")
    except Exception as e:
        logger.error(f"SSE 事件產生器崩潰: {e}")


@router.get("/metrics/stream", name="stream_metrics")
async def stream_metrics(request):
    """SSE 端點 — 推送實時 GPU 指標

    客戶端透過 fetch(url, { headers: { Accept: 'text/event-stream' } })
    或 EventSource(url) 連接此端點，接收每 2 秒一次的 GPU 指標。

    Response:
        text/event-stream — 格式：data: {json}\n\n

        單一事件包含：
        ```json
        {
          "timestamp": 1234567890.5,
          "gpu_percent": 45.2,
          "vram_mb": 2048.5,
          "queue_length": 3,
          "gpu_memory_total_mb": 8192.0
        }
        ```

    Returns:
        StreamingResponse，連線保持開放直到客戶端斷開或伺服器關閉
    """
    # 從 app.state 取得 metrics_collector
    metrics_collector = getattr(request.app.state, 'metrics_collector', None)

    if metrics_collector is None:
        logger.warning("Metrics collector 未在 app.state 中找到")
        return StreamingResponse(
            metrics_event_generator(None, update_interval=2.0),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 停用 nginx 緩衝
            },
        )

    return StreamingResponse(
        metrics_event_generator(metrics_collector, update_interval=2.0),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 停用 nginx 緩衝
        },
    )


@router.get("/metrics/history", name="get_metrics_history")
async def get_metrics_history_endpoint(
    limit: int = Query(100, ge=1, le=1000, description="最多回傳筆數"),
    granularity: str = Query("minute", pattern="^(minute|hour|day)$", description="聚合粒度"),
):
    """歷史指標查詢端點

    回傳最近 N 筆 metrics_history 表記錄，按時間倒序。
    granularity 參數保留用於未來實作聚合邏輯（目前回傳原始列表）。

    Query Parameters:
        limit: 最多回傳筆數（預設 100，範圍 1-1000）
        granularity: 聚合粒度（"minute"/"hour"/"day"，預設 "minute"）

    Returns:
        ```json
        {
          "metrics": [
            {
              "timestamp": 1234567890.5,
              "gpu_percent": 45.2,
              "vram_mb": 2048.5,
              "queue_length": 3,
              "created_at": "2026-04-28 12:34:56"
            },
            ...
          ],
          "granularity": "minute",
          "total": 100,
          "limit": 100
        }
        ```
    """
    try:
        records = await get_metrics_history(limit=limit, granularity=granularity)
        return {
            "metrics": records,
            "granularity": granularity,
            "total": len(records),
            "limit": limit,
        }
    except Exception as e:
        logger.error(f"查詢指標歷史失敗: {e}")
        return {
            "metrics": [],
            "granularity": granularity,
            "total": 0,
            "limit": limit,
            "error": str(e),
        }
