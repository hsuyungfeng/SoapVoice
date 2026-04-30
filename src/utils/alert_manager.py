"""
警報管理模組 — GPU/VRAM/佇列閾值偵測與狀態管理

AlertManager 負責根據即時指標觸發警報、去重複、
自動清除恢復警報，並維護完整的警報歷史紀錄。

用途：Phase 12-03 即時警報系統的核心引擎。
"""

import logging
import time
import uuid
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 警報嚴重程度與類型枚舉 ────────────────────────────────────

class AlertSeverity(str, Enum):
    """警報嚴重程度"""
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """警報類型"""
    GPU_HIGH = "gpu_high"
    VRAM_HIGH = "vram_high"
    QUEUE_LONG = "queue_long"


# ── 預設閾值配置 ───────────────────────────────────────────────

ALERT_THRESHOLDS: Dict[str, float] = {
    "gpu_high_warning": 80.0,
    "gpu_high_critical": 95.0,
    "vram_high_warning": 75.0,    # VRAM 使用率百分比（需要 gpu_memory_total_mb）
    "vram_high_critical": 90.0,
    "queue_long_warning": 10.0,
    "queue_long_critical": 20.0,
}


# ── 警報資料結構 ───────────────────────────────────────────────

@dataclass
class Alert:
    """警報資料結構

    Attributes:
        id: UUID 字串，每個警報唯一識別符
        type: 警報類型（AlertType 值）
        severity: 警報嚴重程度（AlertSeverity 值）
        threshold: 觸發此警報的閾值
        current_value: 觸發時的實際測量值
        triggered_at: 觸發時間（Unix 時間戳，浮點數）
        acknowledged_at: 確認時間（Unix 時間戳），None 表示未確認
        acknowledged_by: 確認者名稱，None 表示未確認
        message: 人類可讀的警報訊息
        cleared_at: 清除時間（Unix 時間戳），None 表示尚未清除
    """
    id: str
    type: str
    severity: str
    threshold: float
    current_value: float
    triggered_at: float
    message: str
    acknowledged_at: Optional[float] = None
    acknowledged_by: Optional[str] = None
    cleared_at: Optional[float] = None


def _build_alert_key(alert_type: str, severity: str) -> str:
    """建立警報去重複鍵（類型 + 嚴重程度）"""
    return f"{alert_type}:{severity}"


def _build_alert_message(alert_type: str, severity: str, current_value: float, threshold: float) -> str:
    """建立警報訊息字串"""
    type_labels = {
        AlertType.GPU_HIGH: "GPU 使用率",
        AlertType.VRAM_HIGH: "VRAM 使用率",
        AlertType.QUEUE_LONG: "請求佇列長度",
    }
    severity_labels = {
        AlertSeverity.WARNING: "警告",
        AlertSeverity.CRITICAL: "嚴重",
    }
    label = type_labels.get(alert_type, alert_type)
    sev_label = severity_labels.get(severity, severity)

    if alert_type == AlertType.VRAM_HIGH:
        return f"[{sev_label}] {label} {current_value:.1f}% 超過閾值 {threshold:.1f}%"
    elif alert_type == AlertType.QUEUE_LONG:
        return f"[{sev_label}] {label} {int(current_value)} 超過閾值 {int(threshold)}"
    else:
        return f"[{sev_label}] {label} {current_value:.1f}% 超過閾值 {threshold:.1f}%"


# ── 主要管理類別 ───────────────────────────────────────────────

class AlertManager:
    """警報管理器 — 閾值偵測、去重複、確認、歷史記錄

    設計原則：
    - active_alerts 以警報鍵（type:severity）為索引，確保同類型同嚴重程度只保留一個
    - alert_history 保留所有曾觸發的警報（包含已清除的）
    - auto_clear_enabled=True 時，指標恢復正常後自動清除對應警報

    Usage:
        >>> manager = AlertManager()
        >>> new_alerts = manager.check_metrics({"gpu_percent": 98, "vram_mb": 2048, "queue_length": 3, "gpu_memory_total_mb": 8192})
        >>> active = manager.get_active_alerts()
        >>> manager.acknowledge_alert(alert_id, user="admin")
    """

    def __init__(self, thresholds: Optional[Dict] = None, auto_clear_enabled: bool = True):
        """初始化警報管理器

        Args:
            thresholds: 自訂閾值字典（部分覆蓋 ALERT_THRESHOLDS）
            auto_clear_enabled: 指標恢復正常時是否自動清除警報
        """
        self.thresholds = {**ALERT_THRESHOLDS}
        if thresholds:
            self.thresholds.update(thresholds)

        self.auto_clear_enabled = auto_clear_enabled

        # 活躍警報：key = "type:severity"，value = Alert
        self._active_alerts: Dict[str, Alert] = {}

        # 完整警報歷史（所有曾觸發的警報）
        self._alert_history: List[Alert] = []

        logger.info(f"AlertManager 初始化（auto_clear={auto_clear_enabled}，閾值：{self.thresholds}）")

    def check_metrics(self, metrics: Dict) -> List[Alert]:
        """檢查指標是否超過閾值並觸發警報

        對 gpu_percent、vram（計算百分比）、queue_length 分別比對 warning/critical 閾值。
        新警報加入 active_alerts 與 alert_history；
        若 auto_clear_enabled，也會清除已恢復正常的警報。

        Args:
            metrics: 含以下欄位的字典：
                - gpu_percent: GPU 使用率（0-100）
                - vram_mb: VRAM 使用量（MB）
                - queue_length: 佇列長度
                - gpu_memory_total_mb: 總 VRAM（MB），用於計算 VRAM 使用率

        Returns:
            此次新觸發的警報列表（不含已存在的重複警報）
        """
        new_alerts: List[Alert] = []

        gpu_percent = float(metrics.get("gpu_percent", 0))
        vram_mb = float(metrics.get("vram_mb", 0))
        queue_length = int(metrics.get("queue_length", 0))
        gpu_memory_total_mb = float(metrics.get("gpu_memory_total_mb", 0))

        # 計算 VRAM 使用率百分比
        vram_percent = 0.0
        if gpu_memory_total_mb > 0:
            vram_percent = (vram_mb / gpu_memory_total_mb) * 100.0

        # ── GPU 使用率警報 ─────────────────────────────────────
        gpu_new = self._check_single_metric(
            value=gpu_percent,
            alert_type=AlertType.GPU_HIGH,
            warning_threshold=self.thresholds["gpu_high_warning"],
            critical_threshold=self.thresholds["gpu_high_critical"],
        )
        new_alerts.extend(gpu_new)

        # ── VRAM 使用率警報 ────────────────────────────────────
        if gpu_memory_total_mb > 0:
            vram_new = self._check_single_metric(
                value=vram_percent,
                alert_type=AlertType.VRAM_HIGH,
                warning_threshold=self.thresholds["vram_high_warning"],
                critical_threshold=self.thresholds["vram_high_critical"],
            )
            new_alerts.extend(vram_new)

        # ── 佇列長度警報 ───────────────────────────────────────
        queue_new = self._check_single_metric(
            value=float(queue_length),
            alert_type=AlertType.QUEUE_LONG,
            warning_threshold=self.thresholds["queue_long_warning"],
            critical_threshold=self.thresholds["queue_long_critical"],
        )
        new_alerts.extend(queue_new)

        # ── 自動清除已恢復的警報 ───────────────────────────────
        if self.auto_clear_enabled:
            self._auto_clear_recovered(
                gpu_percent=gpu_percent,
                vram_percent=vram_percent,
                queue_length=float(queue_length),
                has_vram_data=(gpu_memory_total_mb > 0),
            )

        if new_alerts:
            logger.info(f"新觸發 {len(new_alerts)} 個警報：{[a.type + ':' + a.severity for a in new_alerts]}")

        return new_alerts

    def _check_single_metric(
        self,
        value: float,
        alert_type: str,
        warning_threshold: float,
        critical_threshold: float,
    ) -> List[Alert]:
        """檢查單一指標並回傳新觸發的警報（去重複）"""
        new_alerts = []
        now = time.time()

        # 判斷應觸發哪個嚴重程度（critical 優先）
        if value >= critical_threshold:
            key = _build_alert_key(alert_type, AlertSeverity.CRITICAL)
            if key not in self._active_alerts:
                alert = Alert(
                    id=str(uuid.uuid4()),
                    type=alert_type,
                    severity=AlertSeverity.CRITICAL,
                    threshold=critical_threshold,
                    current_value=value,
                    triggered_at=now,
                    message=_build_alert_message(alert_type, AlertSeverity.CRITICAL, value, critical_threshold),
                )
                self._active_alerts[key] = alert
                self._alert_history.append(alert)
                new_alerts.append(alert)

            # 若有 warning 級別的相同類型警報，清除它（升級為 critical）
            warning_key = _build_alert_key(alert_type, AlertSeverity.WARNING)
            if warning_key in self._active_alerts:
                self._active_alerts[warning_key].cleared_at = now
                del self._active_alerts[warning_key]

        elif value >= warning_threshold:
            key = _build_alert_key(alert_type, AlertSeverity.WARNING)
            if key not in self._active_alerts:
                # 若已有 critical 警報則不新增 warning
                critical_key = _build_alert_key(alert_type, AlertSeverity.CRITICAL)
                if critical_key not in self._active_alerts:
                    alert = Alert(
                        id=str(uuid.uuid4()),
                        type=alert_type,
                        severity=AlertSeverity.WARNING,
                        threshold=warning_threshold,
                        current_value=value,
                        triggered_at=now,
                        message=_build_alert_message(alert_type, AlertSeverity.WARNING, value, warning_threshold),
                    )
                    self._active_alerts[key] = alert
                    self._alert_history.append(alert)
                    new_alerts.append(alert)

        return new_alerts

    def _auto_clear_recovered(
        self,
        gpu_percent: float,
        vram_percent: float,
        queue_length: float,
        has_vram_data: bool,
    ) -> None:
        """自動清除已恢復正常的警報"""
        now = time.time()
        keys_to_clear = []

        for key, alert in self._active_alerts.items():
            should_clear = False

            if alert.type == AlertType.GPU_HIGH:
                # GPU 恢復到 warning 閾值以下
                if gpu_percent < self.thresholds["gpu_high_warning"]:
                    should_clear = True

            elif alert.type == AlertType.VRAM_HIGH:
                if has_vram_data and vram_percent < self.thresholds["vram_high_warning"]:
                    should_clear = True

            elif alert.type == AlertType.QUEUE_LONG:
                if queue_length < self.thresholds["queue_long_warning"]:
                    should_clear = True

            if should_clear:
                alert.cleared_at = now
                keys_to_clear.append(key)
                logger.info(f"警報自動清除（指標恢復正常）: {key}")

        for key in keys_to_clear:
            del self._active_alerts[key]

    def get_active_alerts(self) -> List[Alert]:
        """取得所有未確認的活躍警報

        Returns:
            依觸發時間排序的活躍警報列表（最新在前）
        """
        return sorted(
            self._active_alerts.values(),
            key=lambda a: a.triggered_at,
            reverse=True,
        )

    def acknowledge_alert(self, alert_id: str, user: str) -> Optional[Alert]:
        """確認指定警報

        將警報標記為已確認，記錄確認者與時間。
        確認後警報仍保留在 active_alerts 中，但 acknowledged_at 不為 None。

        Args:
            alert_id: 警報 UUID 字串
            user: 確認者名稱

        Returns:
            已確認的 Alert 物件，若找不到則回傳 None
        """
        for key, alert in self._active_alerts.items():
            if alert.id == alert_id:
                alert.acknowledged_at = time.time()
                alert.acknowledged_by = user
                logger.info(f"警報已確認: {alert_id} by {user}")
                return alert

        # 也搜尋歷史紀錄
        for alert in self._alert_history:
            if alert.id == alert_id:
                if alert.acknowledged_at is None:
                    alert.acknowledged_at = time.time()
                    alert.acknowledged_by = user
                return alert

        logger.warning(f"嘗試確認不存在的警報: {alert_id}")
        return None

    def clear_alert(self, alert_id: str) -> bool:
        """清除指定警報（從活躍警報中移除）

        Args:
            alert_id: 警報 UUID 字串

        Returns:
            True 表示成功清除，False 表示找不到
        """
        now = time.time()
        for key, alert in list(self._active_alerts.items()):
            if alert.id == alert_id:
                alert.cleared_at = now
                del self._active_alerts[key]
                logger.info(f"警報已清除: {alert_id}")
                return True

        logger.warning(f"嘗試清除不存在的警報: {alert_id}")
        return False

    def get_history(self, limit: int = 100, severity: Optional[str] = None) -> List[Alert]:
        """取得警報歷史紀錄

        Args:
            limit: 最多回傳筆數（預設 100）
            severity: 篩選嚴重程度（"warning"/"critical"），None 表示全部

        Returns:
            依觸發時間排序的警報列表（最新在前）
        """
        history = sorted(
            self._alert_history,
            key=lambda a: a.triggered_at,
            reverse=True,
        )

        if severity is not None:
            history = [a for a in history if a.severity == severity]

        return history[:limit]

    def get_alert_by_id(self, alert_id: str) -> Optional[Alert]:
        """依 ID 查找警報（活躍或歷史）

        Args:
            alert_id: 警報 UUID 字串

        Returns:
            Alert 物件或 None
        """
        # 先搜尋活躍警報
        for alert in self._active_alerts.values():
            if alert.id == alert_id:
                return alert

        # 再搜尋歷史
        for alert in self._alert_history:
            if alert.id == alert_id:
                return alert

        return None
