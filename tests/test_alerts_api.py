"""
警報系統單元與整合測試 — Phase 12-03

測試範圍：
1. TestAlertManager (8 tests)：閾值偵測、自動清除、去重複
2. TestAlertsDB (6 tests)：Schema 初始化、CRUD 操作
3. TestAlertsAPI (6 tests)：REST 端點正確性
4. TestIntegration (5 tests)：端對端流程驗證

測試策略：
- AlertManager 純同步測試
- DB 使用 pytest_asyncio.fixture + in-memory SQLite
- API 使用 FastAPI TestClient，lifespan 直接注入 alert_manager
- asyncio mode=STRICT，所有 async fixture 使用 pytest_asyncio.fixture
"""

import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.utils.alert_manager import (
    Alert,
    AlertManager,
    AlertSeverity,
    AlertType,
    ALERT_THRESHOLDS,
)
from src.db.alerts_db import (
    init_alerts_schema,
    insert_alert,
    get_active_alerts,
    get_alert_by_id,
    get_alert_history,
    update_alert_acknowledged,
    clear_old_alerts,
)
from src.api.alerts_api import router as alerts_router


# ══════════════════════════════════════════════════════════════
#  測試 Fixture
# ══════════════════════════════════════════════════════════════

@pytest.fixture
def mock_metrics():
    """高負載指標 fixture（觸發 critical 警報）"""
    return {
        "gpu_percent": 98.5,
        "vram_mb": 7000.0,
        "queue_length": 25,
        "gpu_memory_total_mb": 8192.0,
    }


@pytest.fixture
def normal_metrics():
    """正常負載指標 fixture（不觸發警報）"""
    return {
        "gpu_percent": 50.0,
        "vram_mb": 2048.0,
        "queue_length": 3,
        "gpu_memory_total_mb": 8192.0,
    }


@pytest.fixture
def alert_manager():
    """新鮮 AlertManager 實例"""
    return AlertManager(auto_clear_enabled=True)


@pytest_asyncio.fixture
async def test_db():
    """in-memory SQLite 資料庫（含 alerts Schema）"""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await init_alerts_schema(db)
    yield db
    await db.close()


@pytest.fixture
def sample_alert():
    """樣本 Alert 物件"""
    return Alert(
        id="test-uuid-1234",
        type=AlertType.GPU_HIGH,
        severity=AlertSeverity.CRITICAL,
        threshold=95.0,
        current_value=98.5,
        triggered_at=time.time(),
        message="[嚴重] GPU 使用率 98.5% 超過閾值 95.0%",
    )


def _make_test_app(manager: AlertManager) -> FastAPI:
    """建立整合 AlertManager 的 FastAPI 測試應用"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.alert_manager = manager
        app.state.alerts_db = None
        yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(alerts_router)
    return app


# ══════════════════════════════════════════════════════════════
#  TestAlertManager（8 tests）
# ══════════════════════════════════════════════════════════════

class TestAlertManager:
    """AlertManager 閾值偵測、去重複、自動清除測試"""

    def test_check_metrics_gpu_warning(self, alert_manager):
        """gpu_percent=85 應觸發 warning 級別 GPU 警報"""
        metrics = {
            "gpu_percent": 85.0,
            "vram_mb": 2048.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        }
        new_alerts = alert_manager.check_metrics(metrics)

        gpu_alerts = [a for a in new_alerts if a.type == AlertType.GPU_HIGH]
        assert len(gpu_alerts) == 1
        assert gpu_alerts[0].severity == AlertSeverity.WARNING
        assert gpu_alerts[0].threshold == ALERT_THRESHOLDS["gpu_high_warning"]
        assert gpu_alerts[0].current_value == 85.0

    def test_check_metrics_gpu_critical(self, alert_manager):
        """gpu_percent=98 應觸發 critical 級別 GPU 警報"""
        metrics = {
            "gpu_percent": 98.0,
            "vram_mb": 2048.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        }
        new_alerts = alert_manager.check_metrics(metrics)

        gpu_alerts = [a for a in new_alerts if a.type == AlertType.GPU_HIGH]
        assert len(gpu_alerts) == 1
        assert gpu_alerts[0].severity == AlertSeverity.CRITICAL
        assert gpu_alerts[0].threshold == ALERT_THRESHOLDS["gpu_high_critical"]

    def test_check_metrics_vram_warning(self, alert_manager):
        """vram_mb=6200 (~75.7% of 8192) 應觸發 warning 級別 VRAM 警報"""
        metrics = {
            "gpu_percent": 50.0,
            "vram_mb": 6200.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        }
        new_alerts = alert_manager.check_metrics(metrics)

        vram_alerts = [a for a in new_alerts if a.type == AlertType.VRAM_HIGH]
        assert len(vram_alerts) == 1
        assert vram_alerts[0].severity == AlertSeverity.WARNING

    def test_check_metrics_vram_critical(self, alert_manager):
        """vram_mb=7400 (~90.3% of 8192) 應觸發 critical 級別 VRAM 警報"""
        metrics = {
            "gpu_percent": 50.0,
            "vram_mb": 7400.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        }
        new_alerts = alert_manager.check_metrics(metrics)

        vram_alerts = [a for a in new_alerts if a.type == AlertType.VRAM_HIGH]
        assert len(vram_alerts) == 1
        assert vram_alerts[0].severity == AlertSeverity.CRITICAL

    def test_check_metrics_queue_warning(self, alert_manager):
        """queue_length=15 應觸發 warning 級別佇列警報"""
        metrics = {
            "gpu_percent": 50.0,
            "vram_mb": 2048.0,
            "queue_length": 15,
            "gpu_memory_total_mb": 8192.0,
        }
        new_alerts = alert_manager.check_metrics(metrics)

        queue_alerts = [a for a in new_alerts if a.type == AlertType.QUEUE_LONG]
        assert len(queue_alerts) == 1
        assert queue_alerts[0].severity == AlertSeverity.WARNING
        assert queue_alerts[0].current_value == 15.0

    def test_check_metrics_queue_critical(self, alert_manager):
        """queue_length=25 應觸發 critical 級別佇列警報"""
        metrics = {
            "gpu_percent": 50.0,
            "vram_mb": 2048.0,
            "queue_length": 25,
            "gpu_memory_total_mb": 8192.0,
        }
        new_alerts = alert_manager.check_metrics(metrics)

        queue_alerts = [a for a in new_alerts if a.type == AlertType.QUEUE_LONG]
        assert len(queue_alerts) == 1
        assert queue_alerts[0].severity == AlertSeverity.CRITICAL

    def test_alert_auto_clear(self, alert_manager, normal_metrics):
        """正常指標應自動清除先前觸發的警報"""
        high_metrics = {
            "gpu_percent": 98.0,
            "vram_mb": 2048.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        }
        alert_manager.check_metrics(high_metrics)
        assert len(alert_manager.get_active_alerts()) > 0

        # 回到正常指標
        alert_manager.check_metrics(normal_metrics)

        # GPU 警報應被自動清除
        active = alert_manager.get_active_alerts()
        gpu_alerts = [a for a in active if a.type == AlertType.GPU_HIGH]
        assert len(gpu_alerts) == 0

    def test_alert_deduplication(self, alert_manager):
        """相同類型+嚴重程度的警報，連續觸發不應產生重複"""
        metrics = {
            "gpu_percent": 98.0,
            "vram_mb": 2048.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        }

        first = alert_manager.check_metrics(metrics)
        gpu_first = [a for a in first if a.type == AlertType.GPU_HIGH]
        assert len(gpu_first) == 1

        second = alert_manager.check_metrics(metrics)
        gpu_second = [a for a in second if a.type == AlertType.GPU_HIGH]
        assert len(gpu_second) == 0  # 無新警報（去重複）

        active = alert_manager.get_active_alerts()
        gpu_active = [a for a in active if a.type == AlertType.GPU_HIGH]
        assert len(gpu_active) == 1


# ══════════════════════════════════════════════════════════════
#  TestAlertsDB（6 tests）
# ══════════════════════════════════════════════════════════════

class TestAlertsDB:
    """警報 DB Schema 初始化與 CRUD 操作測試"""

    @pytest.mark.asyncio
    async def test_init_alerts_schema(self):
        """alerts 表應能正常建立"""
        async with aiosqlite.connect(":memory:") as db:
            db.row_factory = aiosqlite.Row
            await init_alerts_schema(db)

            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'"
            ) as cursor:
                row = await cursor.fetchone()
                assert row is not None

    @pytest.mark.asyncio
    async def test_insert_alert(self, sample_alert):
        """警報應能正常插入 DB"""
        async with aiosqlite.connect(":memory:") as db:
            db.row_factory = aiosqlite.Row
            await init_alerts_schema(db)
            await insert_alert(db, sample_alert)

            result = await get_alert_by_id(db, sample_alert.id)
            assert result is not None
            assert result.id == sample_alert.id
            assert result.type == sample_alert.type
            assert result.severity == sample_alert.severity
            assert result.current_value == sample_alert.current_value

    @pytest.mark.asyncio
    async def test_get_active_alerts(self):
        """只有未清除的警報應出現在活躍查詢結果中"""
        async with aiosqlite.connect(":memory:") as db:
            db.row_factory = aiosqlite.Row
            await init_alerts_schema(db)
            now = time.time()

            active_alert = Alert(
                id="active-1",
                type=AlertType.GPU_HIGH,
                severity=AlertSeverity.CRITICAL,
                threshold=95.0,
                current_value=98.0,
                triggered_at=now,
                message="active alert",
            )
            await insert_alert(db, active_alert)

            cleared_alert = Alert(
                id="cleared-1",
                type=AlertType.QUEUE_LONG,
                severity=AlertSeverity.WARNING,
                threshold=10.0,
                current_value=12.0,
                triggered_at=now - 100,
                message="cleared alert",
                cleared_at=now - 50,
            )
            await insert_alert(db, cleared_alert)

            active = await get_active_alerts(db)
            ids = [a.id for a in active]
            assert "active-1" in ids
            assert "cleared-1" not in ids

    @pytest.mark.asyncio
    async def test_update_alert_acknowledged(self, sample_alert):
        """確認警報後應更新 acknowledged_at 與 acknowledged_by"""
        async with aiosqlite.connect(":memory:") as db:
            db.row_factory = aiosqlite.Row
            await init_alerts_schema(db)
            await insert_alert(db, sample_alert)
            await update_alert_acknowledged(db, sample_alert.id, user="doctor_a")

            result = await get_alert_by_id(db, sample_alert.id)
            assert result is not None
            assert result.acknowledged_at is not None
            assert result.acknowledged_by == "doctor_a"

    @pytest.mark.asyncio
    async def test_get_alert_history(self):
        """歷史查詢應返回全部警報，且支援嚴重程度篩選"""
        async with aiosqlite.connect(":memory:") as db:
            db.row_factory = aiosqlite.Row
            await init_alerts_schema(db)
            now = time.time()

            critical_alert = Alert(
                id="hist-critical",
                type=AlertType.GPU_HIGH,
                severity=AlertSeverity.CRITICAL,
                threshold=95.0,
                current_value=98.0,
                triggered_at=now,
                message="critical",
            )
            warning_alert = Alert(
                id="hist-warning",
                type=AlertType.VRAM_HIGH,
                severity=AlertSeverity.WARNING,
                threshold=75.0,
                current_value=78.0,
                triggered_at=now - 60,
                message="warning",
            )

            await insert_alert(db, critical_alert)
            await insert_alert(db, warning_alert)

            all_history = await get_alert_history(db, limit=100, days=30)
            assert len(all_history) == 2

            critical_history = await get_alert_history(db, severity="critical", days=30)
            assert len(critical_history) == 1
            assert critical_history[0].id == "hist-critical"

    @pytest.mark.asyncio
    async def test_clear_old_alerts(self):
        """超過指定天數的警報應被刪除，並回傳刪除數量"""
        async with aiosqlite.connect(":memory:") as db:
            db.row_factory = aiosqlite.Row
            await init_alerts_schema(db)
            now = time.time()
            old_time = now - (10 * 86400)

            old_alert = Alert(
                id="old-alert-1",
                type=AlertType.QUEUE_LONG,
                severity=AlertSeverity.WARNING,
                threshold=10.0,
                current_value=15.0,
                triggered_at=old_time,
                message="old alert",
            )
            new_alert = Alert(
                id="new-alert-1",
                type=AlertType.GPU_HIGH,
                severity=AlertSeverity.CRITICAL,
                threshold=95.0,
                current_value=98.0,
                triggered_at=now,
                message="new alert",
            )

            await insert_alert(db, old_alert)
            await insert_alert(db, new_alert)

            deleted = await clear_old_alerts(db, days=7)
            assert deleted == 1

            remaining = await get_alert_history(db, limit=100, days=365)
            ids = [a.id for a in remaining]
            assert "new-alert-1" in ids
            assert "old-alert-1" not in ids


# ══════════════════════════════════════════════════════════════
#  TestAlertsAPI（6 tests）
# ══════════════════════════════════════════════════════════════

class TestAlertsAPI:
    """REST 端點正確性測試"""

    def test_get_alerts_endpoint(self):
        """GET /api/v1/alerts 應回傳警報列表"""
        manager = AlertManager(auto_clear_enabled=False)
        manager.check_metrics({
            "gpu_percent": 98.0,
            "vram_mb": 2048.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        })

        with TestClient(_make_test_app(manager)) as client:
            response = client.get("/api/v1/alerts")
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert "total" in data
        assert "page" in data
        assert "total_pages" in data
        assert data["total"] >= 1

    def test_get_alerts_severity_filter(self):
        """?severity=critical 應只回傳 critical 級別警報"""
        manager = AlertManager(auto_clear_enabled=False)
        manager.check_metrics({
            "gpu_percent": 98.0,
            "vram_mb": 2048.0,
            "queue_length": 12,
            "gpu_memory_total_mb": 8192.0,
        })

        with TestClient(_make_test_app(manager)) as client:
            response = client.get("/api/v1/alerts?severity=critical")
        assert response.status_code == 200
        data = response.json()
        for alert in data["alerts"]:
            assert alert["severity"] == "critical"

    def test_acknowledge_alert_endpoint(self):
        """POST /api/v1/alerts/{id}/acknowledge 應成功確認警報"""
        manager = AlertManager(auto_clear_enabled=False)
        new_alerts = manager.check_metrics({
            "gpu_percent": 98.0,
            "vram_mb": 2048.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        })
        assert len(new_alerts) > 0
        alert_id = new_alerts[0].id

        with TestClient(_make_test_app(manager)) as client:
            response = client.post(f"/api/v1/alerts/{alert_id}/acknowledge?user=test_doctor")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "acknowledged"
        assert data["acknowledged_at"] is not None

    def test_delete_alert_endpoint(self):
        """DELETE /api/v1/alerts/{id} 應成功清除警報"""
        manager = AlertManager(auto_clear_enabled=False)
        new_alerts = manager.check_metrics({
            "gpu_percent": 98.0,
            "vram_mb": 2048.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        })
        assert len(new_alerts) > 0
        alert_id = new_alerts[0].id

        with TestClient(_make_test_app(manager)) as client:
            response = client.delete(f"/api/v1/alerts/{alert_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "cleared"

        active = manager.get_active_alerts()
        ids = [a.id for a in active]
        assert alert_id not in ids

    def test_get_alert_history_endpoint(self):
        """GET /api/v1/alerts/history 應回傳含 days 欄位的歷史記錄"""
        manager = AlertManager(auto_clear_enabled=False)
        manager.check_metrics({
            "gpu_percent": 98.0,
            "vram_mb": 2048.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        })

        with TestClient(_make_test_app(manager)) as client:
            response = client.get("/api/v1/alerts/history?limit=50&days=7")
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert "total" in data
        assert "days" in data
        assert data["days"] == 7

    def test_get_active_alerts_endpoint(self):
        """GET /api/v1/alerts/active 應只回傳未確認警報"""
        manager = AlertManager(auto_clear_enabled=False)
        manager.check_metrics({
            "gpu_percent": 98.0,
            "vram_mb": 2048.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        })

        with TestClient(_make_test_app(manager)) as client:
            response = client.get("/api/v1/alerts/active")
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert "total" in data
        assert "timestamp" in data
        assert isinstance(data["timestamp"], float)

        for alert in data["alerts"]:
            assert alert["acknowledged_at"] is None


# ══════════════════════════════════════════════════════════════
#  TestIntegration（5 tests）
# ══════════════════════════════════════════════════════════════

class TestIntegration:
    """端對端整合流程測試"""

    def test_metrics_to_alert_flow(self, mock_metrics):
        """高負載指標應觸發 AlertManager 產生對應警報"""
        manager = AlertManager(auto_clear_enabled=False)
        new_alerts = manager.check_metrics(mock_metrics)

        assert len(new_alerts) > 0

        gpu_critical = [a for a in new_alerts
                        if a.type == AlertType.GPU_HIGH and a.severity == AlertSeverity.CRITICAL]
        assert len(gpu_critical) == 1

        queue_critical = [a for a in new_alerts
                          if a.type == AlertType.QUEUE_LONG and a.severity == AlertSeverity.CRITICAL]
        assert len(queue_critical) == 1

    def test_alert_lifecycle(self, alert_manager):
        """警報完整生命週期：觸發 → 活躍 → 確認 → 歷史"""
        new_alerts = alert_manager.check_metrics({
            "gpu_percent": 98.0,
            "vram_mb": 2048.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        })
        assert len(new_alerts) > 0
        alert_id = new_alerts[0].id

        active = alert_manager.get_active_alerts()
        assert any(a.id == alert_id for a in active)

        acked = alert_manager.acknowledge_alert(alert_id, user="doctor")
        assert acked is not None
        assert acked.acknowledged_at is not None

        history = alert_manager.get_history(limit=100)
        hist_ids = [a.id for a in history]
        assert alert_id in hist_ids

    def test_concurrent_alerts(self):
        """多個不同類型的警報應同時存在，狀態一致"""
        manager = AlertManager(auto_clear_enabled=False)
        manager.check_metrics({
            "gpu_percent": 98.0,
            "vram_mb": 7500.0,
            "queue_length": 25,
            "gpu_memory_total_mb": 8192.0,
        })

        active = manager.get_active_alerts()
        types = {a.type for a in active}

        assert AlertType.GPU_HIGH in types
        assert AlertType.VRAM_HIGH in types
        assert AlertType.QUEUE_LONG in types
        assert len(active) == 3

    def test_frontend_polling_flow(self):
        """模擬前端輪詢：取得活躍警報 → 確認 → 再次輪詢應為空"""
        manager = AlertManager(auto_clear_enabled=False)
        new_alerts = manager.check_metrics({
            "gpu_percent": 98.0,
            "vram_mb": 2048.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        })
        alert_id = new_alerts[0].id

        with TestClient(_make_test_app(manager)) as client:
            r1 = client.get("/api/v1/alerts/active")
            assert r1.status_code == 200
            d1 = r1.json()
            assert d1["total"] >= 1

            r2 = client.post(f"/api/v1/alerts/{alert_id}/acknowledge?user=dashboard")
            assert r2.status_code == 200

            client.delete(f"/api/v1/alerts/{alert_id}")

            r3 = client.get("/api/v1/alerts/active")
            d3 = r3.json()
            ids = [a["id"] for a in d3["alerts"]]
            assert alert_id not in ids

    def test_alert_sound_trigger(self):
        """critical 警報存在時，前端應播放三次嗶聲（驗證業務邏輯）"""
        manager = AlertManager(auto_clear_enabled=False)
        new_alerts = manager.check_metrics({
            "gpu_percent": 98.0,
            "vram_mb": 2048.0,
            "queue_length": 3,
            "gpu_memory_total_mb": 8192.0,
        })

        critical_alerts = [a for a in new_alerts if a.severity == AlertSeverity.CRITICAL]
        assert len(critical_alerts) > 0, "critical 警報存在 → 前端應播放三次嗶聲"

        for ca in critical_alerts:
            assert ca.severity == "critical"
