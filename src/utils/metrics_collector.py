"""
伺服器端即時 GPU 指標收集與管理模組

MetricsCollector 負責在背景非同步任務中定期收集 GPU 使用率、VRAM、請求佇列長度等指標，
並透過 thread-safe 的最新指標存儲提供即時存取。

用途：Phase 12-01 監控儀表板的核心數據收集引擎。SSE 推送端點每 2 秒查詢最新指標並推送至客戶端。
"""

import asyncio
import logging
import time
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GPUMetrics:
    """GPU 即時指標資料結構

    Attributes:
        timestamp: Unix 時戳（秒），用於前端時間軸對齊
        gpu_percent: GPU 使用率（0-100）
        vram_mb: VRAM 使用量（MB），絕對值
        queue_length: 當前待處理請求佇列長度
        gpu_memory_total_mb: GPU 總可用 VRAM（MB），用於計算使用比率
    """
    timestamp: float
    gpu_percent: float
    vram_mb: float
    queue_length: int
    gpu_memory_total_mb: float = 0.0


class MetricsCollector:
    """GPU 指標收集器 — 背景非同步任務管理

    啟動後於背景維持一個非同步任務，每隔 update_interval 秒收集一次指標。
    提供 thread-safe 的最新指標快照存取，以及正常啟動/停止生命週期管理。

    Features:
    - Graceful pynvml fallback：若 GPU 庫不可用，回傳 0 值而不拋例外
    - asyncio.Lock 保護最新指標存儲，避免 race condition
    - 自動任務崩潰恢復：若收集邏輯異常，記 error log 但繼續執行
    - 可配置更新間隔（預設 2 秒）

    Usage:
        >>> collector = MetricsCollector(update_interval=2.0)
        >>> await collector.start_background_task()
        >>> metrics = collector.get_latest_metrics()
        >>> await collector.stop_background_task()
    """

    def __init__(self, update_interval: float = 2.0):
        """初始化指標收集器

        Args:
            update_interval: 收集週期（秒），預設 2.0
        """
        self.update_interval = update_interval
        self._latest_metrics: Optional[GPUMetrics] = None
        self._metrics_lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._background_task: Optional[asyncio.Task] = None
        self._pynvml_available = False
        self._gpu_device = None

        # 嘗試初始化 pynvml（非致命失敗）
        self._init_pynvml()

    def _init_pynvml(self) -> None:
        """初始化 pynvml GPU 庫（graceful fallback）

        試圖匯入並初始化 nvidia-ml-py，若失敗記錄 warning 但不拋例外。
        此舉允許在非 NVIDIA GPU 環境（或未裝驅動）下安全運行。
        """
        try:
            import pynvml
            pynvml.nvmlInit()
            self._gpu_device = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._pynvml_available = True
            logger.info("pynvml 初始化成功，GPU 指標收集已啟用")
        except ImportError:
            logger.warning("nvidia-ml-py 未安裝，GPU 指標收集將回傳預設值 0")
        except Exception as e:
            logger.warning(f"pynvml 初始化失敗（可能非 NVIDIA GPU 或驅動未安裝）: {e}")

    def _get_gpu_metrics(self) -> tuple[float, float, float]:
        """取得 GPU 使用率、VRAM 使用量、總 VRAM（私有方法）

        Returns:
            (gpu_percent, vram_mb, gpu_memory_total_mb) 三元組
            - 若 pynvml 不可用或查詢失敗，回傳 (0.0, 0.0, 0.0)
        """
        if not self._pynvml_available or self._gpu_device is None:
            return 0.0, 0.0, 0.0

        try:
            import pynvml

            # 取得使用率
            util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_device)
            gpu_percent = float(util.gpu)

            # 取得 VRAM 資訊
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._gpu_device)
            vram_used_mb = float(mem_info.used) / (1024 * 1024)
            vram_total_mb = float(mem_info.total) / (1024 * 1024)

            return gpu_percent, vram_used_mb, vram_total_mb
        except Exception as e:
            logger.warning(f"GPU 指標查詢失敗: {e}")
            return 0.0, 0.0, 0.0

    def _get_queue_depth(self) -> int:
        """取得當前請求佇列深度（私有方法）

        簡單實作：暫時回傳 0（佔位符）。
        後續可擴展至從 app.state 或 async task counter 取得實際值。

        Returns:
            佇列中待處理的請求數量，暫時為 0
        """
        # Placeholder：可後續整合至全域請求隊列管理
        return 0

    async def collect_metrics(self) -> None:
        """單次指標收集邏輯（私有方法）

        呼叫 GPU/VRAM/隊列收集器，建立 GPUMetrics 物件，並透過 lock 安全地
        更新 _latest_metrics，供 get_latest_metrics() 查詢。
        """
        try:
            gpu_percent, vram_mb, gpu_memory_total_mb = self._get_gpu_metrics()
            queue_length = self._get_queue_depth()

            metrics = GPUMetrics(
                timestamp=time.time(),
                gpu_percent=gpu_percent,
                vram_mb=vram_mb,
                queue_length=queue_length,
                gpu_memory_total_mb=gpu_memory_total_mb,
            )

            async with self._metrics_lock:
                self._latest_metrics = metrics
        except Exception as e:
            logger.error(f"指標收集過程中發生錯誤: {e}")

    async def start_background_task(self) -> None:
        """啟動背景指標收集任務

        建立一個非同步任務，每隔 update_interval 秒執行一次 collect_metrics()。
        任務執行中檢查 _stop_event，若已設則優雅結束。

        此方法應在 FastAPI lifespan 的 startup 階段呼叫。
        """
        if self._background_task is not None and not self._background_task.done():
            logger.warning("背景任務已在執行中")
            return

        self._stop_event.clear()

        async def collection_loop():
            """後臺循環：定期收集指標"""
            logger.info(f"啟動指標收集背景任務（更新週期 {self.update_interval}s）")

            while not self._stop_event.is_set():
                try:
                    await self.collect_metrics()
                    # 等待下一次收集週期，同時檢查停止信號
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.update_interval
                    )
                except asyncio.TimeoutError:
                    # 正常——計時器到期，繼續下一次收集
                    pass
                except asyncio.CancelledError:
                    logger.info("指標收集任務已取消")
                    break
                except Exception as e:
                    logger.error(f"指標收集任務中發生錯誤，將在 {self.update_interval}s 後重試: {e}")
                    try:
                        await asyncio.wait_for(
                            self._stop_event.wait(),
                            timeout=self.update_interval
                        )
                    except asyncio.TimeoutError:
                        pass

            logger.info("指標收集背景任務已停止")

        self._background_task = asyncio.create_task(collection_loop())
        logger.info("背景指標收集任務已建立")

    async def stop_background_task(self) -> None:
        """停止背景指標收集任務（優雅關閉）

        設定 _stop_event，等待任務完成。若任務懸掛超過 5 秒，強制取消。
        此方法應在 FastAPI lifespan 的 shutdown 階段呼叫。
        """
        if self._background_task is None or self._background_task.done():
            logger.debug("背景任務已結束或未啟動")
            return

        logger.info("正在停止指標收集背景任務...")
        self._stop_event.set()

        try:
            # 等待任務優雅完成（最長 5 秒）
            await asyncio.wait_for(self._background_task, timeout=5.0)
            logger.info("指標收集背景任務已優雅停止")
        except asyncio.TimeoutError:
            logger.warning("指標收集背景任務未在 5s 內停止，強制取消")
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                logger.info("指標收集背景任務已強制取消")
        except Exception as e:
            logger.error(f"停止背景任務時發生錯誤: {e}")

    def get_latest_metrics(self) -> Optional[GPUMetrics]:
        """取得最新指標快照（同步方法，無需 await）

        回傳最近一次成功收集的 GPUMetrics 物件，或 None（若尚未收集）。
        此方法為同步且非阻塞，適合在 SSE 路由中頻繁呼叫。

        Returns:
            GPUMetrics 物件或 None
        """
        return self._latest_metrics

    def metrics_to_dict(self) -> Optional[dict]:
        """將最新指標轉換為可序列化的字典

        便於 SSE 推送或 JSON 回應。

        Returns:
            GPUMetrics 的 dataclass asdict() 結果，或 None
        """
        if self._latest_metrics is None:
            return None
        return asdict(self._latest_metrics)
