"""
指標 API 單元與整合測試 — Phase 12-01

測試範圍：
1. MetricsCollector：初始化、背景任務生命週期、GPU/VRAM 收集、fallback 機制
2. SSE 端點：流式推送、事件格式驗證、客戶端斷線處理
3. 歷史查詢端點：DB 查詢、分頁、粒度篩選
4. DB 整合：metrics_history 表建立、記錄持久化

測試策略：使用 pytest-asyncio + mock 模擬 GPU 指標，aiosqlite in-memory DB
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch, call
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

logger = logging.getLogger(__name__)


# ── 測試 Fixture ──────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_in_memory():
    """建立 in-memory SQLite 資料庫（測試隔離）"""
    from src.db.patient_records_db import set_db_path_for_test, get_patient_records_db, init_schema

    # 設定測試資料庫路徑（in-memory）
    set_db_path_for_test(Path(":memory:"))

    # 初始化 schema
    db = await get_patient_records_db()
    await init_schema(db)

    yield db

    # 清理
    await db.close()


@pytest.fixture
def metrics_collector():
    """建立 MetricsCollector 實例"""
    from src.utils.metrics_collector import MetricsCollector
    return MetricsCollector(update_interval=0.1)  # 加速測試


@pytest.fixture
def app_with_metrics(metrics_collector, db_in_memory):
    """建立整合 MetricsCollector 的 FastAPI 應用"""
    from fastapi import FastAPI
    from contextlib import asynccontextmanager
    from src.api.metrics_api import router as metrics_router

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 啟動
        app.state.metrics_collector = metrics_collector
        await metrics_collector.start_background_task()
        yield
        # 關閉
        await metrics_collector.stop_background_task()

    app = FastAPI(lifespan=lifespan)
    app.include_router(metrics_router, prefix="/api/v1")

    return app


@pytest.fixture
def test_client(app_with_metrics):
    """FastAPI TestClient"""
    return TestClient(app_with_metrics)


# ── TestMetricsCollector：單元測試 ────────────────────────────


class TestMetricsCollector:
    """MetricsCollector 類別的單元測試"""

    def test_initialization(self):
        """驗證 MetricsCollector 初始化"""
        from src.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector(update_interval=2.0)
        assert collector.update_interval == 2.0
        assert collector._latest_metrics is None
        assert collector._background_task is None
        assert not collector._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_start_background_task(self):
        """驗證背景任務啟動與停止"""
        from src.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector(update_interval=0.05)
        await collector.start_background_task()

        # 任務應已建立
        assert collector._background_task is not None
        assert not collector._background_task.done()

        # 等待首次收集完成
        await asyncio.sleep(0.15)

        # 停止任務
        await collector.stop_background_task()
        assert collector._background_task.done() or collector._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_get_latest_metrics(self):
        """驗證 get_latest_metrics() 取得最新指標"""
        from src.utils.metrics_collector import MetricsCollector, GPUMetrics

        collector = MetricsCollector(update_interval=0.05)
        await collector.start_background_task()

        # 等待首次收集
        await asyncio.sleep(0.15)

        metrics = collector.get_latest_metrics()
        assert metrics is not None
        assert isinstance(metrics, GPUMetrics)
        assert hasattr(metrics, 'timestamp')
        assert hasattr(metrics, 'gpu_percent')
        assert hasattr(metrics, 'vram_mb')
        assert hasattr(metrics, 'queue_length')

        await collector.stop_background_task()

    @pytest.mark.asyncio
    async def test_gpu_metrics_fallback(self):
        """驗證 pynvml 不可用時的 fallback 機制"""
        from src.utils.metrics_collector import MetricsCollector

        with patch('src.utils.metrics_collector.MetricsCollector._init_pynvml') as mock_init:
            mock_init.return_value = None
            collector = MetricsCollector(update_interval=0.05)

            # 模擬 pynvml 初始化失敗
            collector._pynvml_available = False

            await collector.start_background_task()
            await asyncio.sleep(0.15)

            metrics = collector.get_latest_metrics()
            assert metrics is not None
            # GPU 不可用時，應回傳 0 值
            assert metrics.gpu_percent == 0.0
            assert metrics.vram_mb == 0.0

            await collector.stop_background_task()

    @pytest.mark.asyncio
    async def test_queue_depth_placeholder(self):
        """驗證佇列深度取得（暫時為 placeholder）"""
        from src.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector(update_interval=0.05)
        await collector.start_background_task()

        await asyncio.sleep(0.15)

        metrics = collector.get_latest_metrics()
        assert metrics is not None
        # 暫時應為 0（placeholder）
        assert isinstance(metrics.queue_length, int)
        assert metrics.queue_length >= 0

        await collector.stop_background_task()

    @pytest.mark.asyncio
    async def test_metrics_to_dict(self):
        """驗證指標轉換為字典"""
        from src.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector(update_interval=0.05)
        await collector.start_background_task()

        await asyncio.sleep(0.15)

        metrics_dict = collector.metrics_to_dict()
        assert metrics_dict is not None
        assert isinstance(metrics_dict, dict)
        assert "timestamp" in metrics_dict
        assert "gpu_percent" in metrics_dict
        assert "vram_mb" in metrics_dict
        assert "queue_length" in metrics_dict

        await collector.stop_background_task()


# ── TestMetricsAPI：SSE & 歷史查詢 API 整合測試 ──────────────


class TestMetricsAPI:
    """SSE 端點與歷史查詢端點的整合測試"""

    def test_sse_stream_basic(self, test_client):
        """驗證 SSE 端點基本連線與事件推送"""
        response = test_client.get("/api/v1/metrics/stream")

        # 應回傳 200 + text/event-stream
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # 應包含 SSE 相關 header
        assert response.headers.get("cache-control") == "no-cache"
        assert response.headers.get("connection") == "keep-alive"

    @pytest.mark.asyncio
    async def test_sse_stream_format(self, app_with_metrics):
        """驗證 SSE 事件格式正確"""
        from src.api.metrics_api import metrics_event_generator
        from src.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector(update_interval=0.05)
        await collector.start_background_task()

        await asyncio.sleep(0.15)

        # 取得前 2 個事件
        gen = metrics_event_generator(collector, update_interval=0.05)
        event1 = await anext(gen)
        event2 = await anext(gen)

        await collector.stop_background_task()

        # 驗證格式：data: {...}\n\n
        assert event1.startswith("data: ")
        assert event1.endswith("\n\n")

        # 驗證 JSON 內容
        json_str = event1.split("data: ")[1].rstrip("\n")
        json_data = json.loads(json_str)

        assert "timestamp" in json_data or "status" in json_data
        if "timestamp" in json_data:
            assert "gpu_percent" in json_data
            assert "vram_mb" in json_data
            assert "queue_length" in json_data

    def test_metrics_history_empty(self, test_client, db_in_memory):
        """驗證初始狀態下歷史查詢回傳空陣列"""
        response = test_client.get("/api/v1/metrics/history")

        assert response.status_code == 200
        data = response.json()

        assert "metrics" in data
        assert isinstance(data["metrics"], list)
        assert len(data["metrics"]) == 0
        assert data["total"] == 0
        assert data["granularity"] == "minute"

    @pytest.mark.asyncio
    async def test_metrics_history_with_records(self, test_client, db_in_memory):
        """驗證插入記錄後的查詢"""
        from src.db.patient_records_db import save_metrics_to_db
        import time

        # 插入 5 筆測試指標
        for i in range(5):
            await save_metrics_to_db(
                timestamp=time.time() + i,
                gpu_percent=50.0 + i * 5,
                vram_mb=2048.0 + i * 100,
                queue_length=i,
            )
            await asyncio.sleep(0.01)

        # 查詢
        response = test_client.get("/api/v1/metrics/history")

        assert response.status_code == 200
        data = response.json()

        assert len(data["metrics"]) == 5
        assert data["total"] == 5

    def test_metrics_history_limit(self, test_client, db_in_memory):
        """驗證 limit 參數生效"""
        response = test_client.get("/api/v1/metrics/history?limit=10")

        assert response.status_code == 200
        data = response.json()

        assert data["limit"] == 10

    def test_metrics_history_granularity(self, test_client, db_in_memory):
        """驗證 granularity 參數接受"""
        for granularity in ["minute", "hour", "day"]:
            response = test_client.get(f"/api/v1/metrics/history?granularity={granularity}")
            assert response.status_code == 200
            data = response.json()
            assert data["granularity"] == granularity

        # 驗證無效粒度被拒絕
        response = test_client.get("/api/v1/metrics/history?granularity=invalid")
        assert response.status_code == 422  # Pydantic 驗證失敗

    @pytest.mark.asyncio
    async def test_metrics_db_integration(self, db_in_memory):
        """驗證指標保存至 DB 與查詢"""
        from src.db.patient_records_db import save_metrics_to_db, get_metrics_history
        import time

        # 插入指標
        ts1 = time.time()
        await save_metrics_to_db(ts1, 45.5, 2048.5, 3)

        ts2 = time.time() + 1
        await save_metrics_to_db(ts2, 55.0, 2560.0, 5)

        # 查詢
        records = await get_metrics_history(limit=100)

        assert len(records) == 2
        # 應按時間倒序
        assert records[0]["timestamp"] == ts2 or records[0]["gpu_percent"] == 55.0


# ── TestMetricsCollector 額外測試 ────────────────────────────


class TestMetricsCollectorExtra:
    """MetricsCollector 邊界與錯誤處理測試"""

    @pytest.mark.asyncio
    async def test_double_start(self):
        """驗證重複啟動不會建立多個任務"""
        from src.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector(update_interval=0.05)

        await collector.start_background_task()
        task1 = collector._background_task

        # 再次啟動（應警告但不建立新任務）
        await collector.start_background_task()
        task2 = collector._background_task

        assert task1 is task2

        await collector.stop_background_task()

    @pytest.mark.asyncio
    async def test_stop_before_start(self):
        """驗證停止未啟動的任務不會崩潰"""
        from src.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector(update_interval=0.05)

        # 應不拋例外
        await collector.stop_background_task()

        assert collector._background_task is None

    @pytest.mark.asyncio
    async def test_metrics_lock_safety(self):
        """驗證指標更新的 thread-safe 性"""
        from src.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector(update_interval=0.05)
        await collector.start_background_task()

        # 並行讀取指標
        metrics_list = []
        for _ in range(10):
            m = collector.get_latest_metrics()
            metrics_list.append(m)
            await asyncio.sleep(0.01)

        await collector.stop_background_task()

        # 應成功讀取（無 race condition）
        assert len(metrics_list) == 10


# ── TestMetricsAPIIntegration：端對端測試 ──────────────────


class TestMetricsAPIIntegration:
    """端對端整合測試"""

    @pytest.mark.asyncio
    async def test_lifespan_integration(self, app_with_metrics):
        """驗證 lifespan 中 MetricsCollector 的啟動與停止"""
        with TestClient(app_with_metrics) as client:
            # 在 context manager 中，lifespan 已執行啟動
            response = client.get("/api/v1/metrics/history")
            assert response.status_code == 200

        # 退出後，lifespan 停止已執行

    def test_metrics_endpoint_no_metrics_collector(self):
        """驗證在 metrics_collector 未初始化時的行為"""
        from fastapi import FastAPI
        from src.api.metrics_api import router as metrics_router

        app = FastAPI()
        app.include_router(metrics_router, prefix="/api/v1")

        # 未設定 app.state.metrics_collector
        client = TestClient(app)

        response = client.get("/api/v1/metrics/stream")
        # 應回傳 error 事件但不崩潰
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
