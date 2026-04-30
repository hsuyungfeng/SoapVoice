/**
 * tests/test_dashboard_frontend.js
 *
 * SoapVoice 監控儀表板前端單元測試
 * 測試環境：Jest + jsdom
 *
 * 測試套件：
 *  1. TestDashboardInitialization  — 模組載入與初始狀態
 *  2. TestSSEConnection            — EventSource 連線事件模擬
 *  3. TestMetricsUI                — 指標 UI 格式化與更新
 *  4. TestChartInitialization      — 歷史圖表 fetch / 建立 / 資料填充
 *  5. TestGranularitySwitch        — 粒度切換事件
 *  6. TestConsultationStats        — 看診統計 fetch / UI 更新 / 缺值處理
 */

'use strict';

/* ═══════════════════════════════════════════════════════
   測試用 HTML Fixture（模擬 dashboard.html 的 DOM 結構）
   ═══════════════════════════════════════════════════════ */
const DASHBOARD_HTML = `
<div id="connectionDot" class="connection-dot connecting"></div>
<span id="connectionIndicator">連線中...</span>
<span id="lastUpdateTime">尚未接收資料</span>
<div id="alertBar" class="alert-bar"></div>

<div id="gpuPercent">--<span class="unit">%</span></div>
<div id="gpuSub">等待資料中...</div>

<div id="vramMb">--<span class="unit">MB</span></div>
<div id="vramTotal">/ -- MB</div>
<div role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
  <div id="vramBarFill" style="width:0%"></div>
</div>

<div id="queueLength">--<span class="unit">筆</span></div>
<div id="queueSub">等待資料中...</div>

<canvas id="metricsChart"></canvas>

<button class="granularity-btn active" data-granularity="hour" id="btnHour">小時</button>
<button class="granularity-btn" data-granularity="day" id="btnDay">日</button>

<div id="todayCount">--</div>
<div id="todayDate">載入中...</div>
<div id="monthlyCount">--</div>
<div id="monthlyRange">載入中...</div>
`;

/* ═══════════════════════════════════════════════════════
   Mock 設定
   ═══════════════════════════════════════════════════════ */

// Mock Chart.js — 必須在 require dashboard.js 之前宣告
class MockChart {
    constructor(ctx, config) {
        this.ctx = ctx;
        this.config = config;
        this.data = config.data;
        this.destroyed = false;
        MockChart.lastInstance = this;
        MockChart.instances.push(this);
    }
    destroy() { this.destroyed = true; }
    update() {}
}
MockChart.lastInstance = null;
MockChart.instances = [];

// Mock EventSource
class MockEventSource {
    constructor(url) {
        this.url = url;
        this.readyState = 0; // CONNECTING
        this.onopen = null;
        this.onmessage = null;
        this.onerror = null;
        MockEventSource.lastInstance = this;
        MockEventSource.instances.push(this);
    }
    close() { this.readyState = 2; }

    // 測試輔助：模擬連線成功
    simulateOpen() {
        this.readyState = 1;
        if (this.onopen) this.onopen();
    }

    // 測試輔助：模擬接收訊息
    simulateMessage(data) {
        if (this.onmessage) {
            this.onmessage({ data: JSON.stringify(data) });
        }
    }

    // 測試輔助：模擬錯誤
    simulateError() {
        this.readyState = 2;
        if (this.onerror) this.onerror();
    }
}
MockEventSource.lastInstance = null;
MockEventSource.instances = [];

// 掛載到 global（jsdom 環境）
global.EventSource = MockEventSource;
global.Chart = MockChart;

// Mock fetch
global.fetch = jest.fn();

// 載入受測模組
const dashboard = require('../static/js/dashboard.js');
const {
    dashboardState,
    initSSE,
    updateMetricsUI,
    initChart,
    loadHistoryAndUpdate,
    loadConsultationStats,
    fetchConsultationTotal,
    formatRelativeTime,
    formatTimeForChart,
    safeNum,
    setConnectionStatus,
    showAlert,
    hideAlert,
    bindGranularityButtons,
    initDashboard,
} = dashboard;

/* ═══════════════════════════════════════════════════════
   測試前置作業
   ═══════════════════════════════════════════════════════ */

beforeEach(() => {
    // 重置 DOM
    document.body.innerHTML = DASHBOARD_HTML;

    // 重置狀態
    dashboardState.connected = false;
    dashboardState.lastMetrics = null;
    dashboardState.metricsHistory = [];
    dashboardState.chart = null;
    dashboardState.currentGranularity = 'hour';
    dashboardState.eventSource = null;

    // 重置 Mock
    MockChart.lastInstance = null;
    MockChart.instances = [];
    MockEventSource.lastInstance = null;
    MockEventSource.instances = [];
    global.fetch.mockReset();
});

/* ═══════════════════════════════════════════════════════
   1. TestDashboardInitialization
   ═══════════════════════════════════════════════════════ */

describe('TestDashboardInitialization', () => {
    test('模組應正確匯出所有必要函式', () => {
        // 驗證所有公開函式均已匯出
        expect(typeof initSSE).toBe('function');
        expect(typeof updateMetricsUI).toBe('function');
        expect(typeof initChart).toBe('function');
        expect(typeof loadHistoryAndUpdate).toBe('function');
        expect(typeof loadConsultationStats).toBe('function');
        expect(typeof formatRelativeTime).toBe('function');
        expect(typeof formatTimeForChart).toBe('function');
    });

    test('dashboardState 初始值應符合規格', () => {
        expect(dashboardState.connected).toBe(false);
        expect(dashboardState.lastMetrics).toBeNull();
        expect(Array.isArray(dashboardState.metricsHistory)).toBe(true);
        expect(dashboardState.chart).toBeNull();
        expect(dashboardState.currentGranularity).toBe('hour');
    });
});

/* ═══════════════════════════════════════════════════════
   2. TestSSEConnection
   ═══════════════════════════════════════════════════════ */

describe('TestSSEConnection', () => {
    test('initSSE 應建立指向正確端點的 EventSource', () => {
        initSSE();
        const es = MockEventSource.lastInstance;
        expect(es).not.toBeNull();
        expect(es.url).toBe('/api/v1/metrics/stream');
        expect(dashboardState.eventSource).toBe(es);
    });

    test('onopen 事件應將 connected 設為 true 並更新指示器', () => {
        initSSE();
        const es = MockEventSource.lastInstance;
        es.simulateOpen();

        expect(dashboardState.connected).toBe(true);
        const indicator = document.getElementById('connectionIndicator');
        expect(indicator.textContent).toBe('已連線');
        const dot = document.getElementById('connectionDot');
        expect(dot.className).toContain('connected');
    });

    test('onmessage 事件應更新 lastMetrics 並更新 UI', () => {
        initSSE();
        const es = MockEventSource.lastInstance;

        const testData = {
            timestamp: 1745000000,
            gpu_percent: 45.2,
            vram_mb: 2048,
            queue_length: 3,
            gpu_memory_total_mb: 8192,
        };
        es.simulateMessage(testData);

        expect(dashboardState.lastMetrics).toEqual(testData);
        expect(dashboardState.metricsHistory).toHaveLength(1);

        // UI 應已更新
        const gpuEl = document.getElementById('gpuPercent');
        expect(gpuEl.textContent).toContain('45.2');
    });

    test('onerror 事件應將 connected 設為 false 並顯示警告', () => {
        initSSE();
        const es = MockEventSource.lastInstance;
        es.simulateOpen(); // 先連線成功

        es.simulateError();

        expect(dashboardState.connected).toBe(false);
        const indicator = document.getElementById('connectionIndicator');
        expect(indicator.textContent).toContain('連線失敗');
        const alertBar = document.getElementById('alertBar');
        expect(alertBar.classList.contains('show')).toBe(true);
    });
});

/* ═══════════════════════════════════════════════════════
   3. TestMetricsUI
   ═══════════════════════════════════════════════════════ */

describe('TestMetricsUI', () => {
    test('updateMetricsUI 應正確格式化並顯示 GPU/VRAM/佇列數值', () => {
        dashboardState.lastMetrics = {
            timestamp: 1745000000,
            gpu_percent: 72.5,
            vram_mb: 3072,
            queue_length: 5,
            gpu_memory_total_mb: 8192,
        };

        updateMetricsUI();

        // GPU
        expect(document.getElementById('gpuPercent').textContent).toContain('72.5');
        // VRAM
        expect(document.getElementById('vramMb').textContent).toContain('3072');
        expect(document.getElementById('vramTotal').textContent).toContain('8192');
        // 進度條寬度 ≈ 37.5%
        const barFill = document.getElementById('vramBarFill');
        const width = parseFloat(barFill.style.width);
        expect(width).toBeCloseTo(37.5, 0);
        // 佇列
        expect(document.getElementById('queueLength').textContent).toContain('5');
    });

    test('formatRelativeTime 應將 Unix timestamp 格式化為 HH:MM:SS', () => {
        // 使用固定 timestamp 驗證格式
        const ts = 1745000000; // 2025-04-18 某時刻
        const result = formatRelativeTime(ts);
        // 應符合 HH:MM:SS 格式
        expect(result).toMatch(/^\d{2}:\d{2}:\d{2}$/);

        // null 值應回傳 '--'
        expect(formatRelativeTime(null)).toBe('--');
        expect(formatRelativeTime(undefined)).toBe('--');
    });
});

/* ═══════════════════════════════════════════════════════
   4. TestChartInitialization
   ═══════════════════════════════════════════════════════ */

describe('TestChartInitialization', () => {
    const mockHistoryResponse = {
        metrics: [
            { timestamp: 1745000000, gpu_percent: 30, vram_mb: 1024, queue_length: 1 },
            { timestamp: 1745003600, gpu_percent: 55, vram_mb: 2048, queue_length: 2 },
            { timestamp: 1745007200, gpu_percent: 80, vram_mb: 3072, queue_length: 4 },
        ],
        granularity: 'hour',
        total: 3,
        limit: 100,
    };

    test('initChart 應向正確端點發送 fetch 請求', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => mockHistoryResponse,
        });

        await initChart('hour');

        expect(global.fetch).toHaveBeenCalledWith(
            '/api/v1/metrics/history?granularity=hour&limit=100'
        );
    });

    test('initChart 應建立 Chart.js 實例並存入 dashboardState.chart', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => mockHistoryResponse,
        });

        await initChart('hour');

        expect(dashboardState.chart).not.toBeNull();
        expect(dashboardState.chart).toBeInstanceOf(MockChart);
    });

    test('Chart 資料集應包含正確數量的資料點', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => mockHistoryResponse,
        });

        await initChart('hour');

        const chartData = dashboardState.chart.data;
        expect(chartData.labels).toHaveLength(3);
        expect(chartData.datasets[0].data).toHaveLength(3);
        expect(chartData.datasets[0].data[0]).toBe(30);
        expect(chartData.datasets[0].data[2]).toBe(80);
    });
});

/* ═══════════════════════════════════════════════════════
   5. TestGranularitySwitch
   ═══════════════════════════════════════════════════════ */

describe('TestGranularitySwitch', () => {
    const mockDayResponse = {
        metrics: [
            { timestamp: 1744934400, gpu_percent: 42, vram_mb: 1500, queue_length: 2 },
            { timestamp: 1745020800, gpu_percent: 61, vram_mb: 2200, queue_length: 3 },
        ],
        granularity: 'day',
        total: 2,
        limit: 100,
    };

    test('loadHistoryAndUpdate 應更新 currentGranularity 並切換按鈕樣式', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => mockDayResponse,
        });

        await loadHistoryAndUpdate('day');

        expect(dashboardState.currentGranularity).toBe('day');

        const dayBtn = document.getElementById('btnDay');
        const hourBtn = document.getElementById('btnHour');
        expect(dayBtn.classList.contains('active')).toBe(true);
        expect(hourBtn.classList.contains('active')).toBe(false);
    });

    test('點擊粒度按鈕應觸發 loadHistoryAndUpdate', async () => {
        global.fetch.mockResolvedValue({
            ok: true,
            json: async () => mockDayResponse,
        });

        bindGranularityButtons();

        const dayBtn = document.getElementById('btnDay');
        dayBtn.click();

        // 等待非同步更新
        await new Promise(resolve => setTimeout(resolve, 50));

        expect(dashboardState.currentGranularity).toBe('day');
        expect(global.fetch).toHaveBeenCalled();
    });
});

/* ═══════════════════════════════════════════════════════
   6. TestConsultationStats
   ═══════════════════════════════════════════════════════ */

describe('TestConsultationStats', () => {
    test('loadConsultationStats 應查詢本日與本月資料並更新 UI', async () => {
        // 本日查詢回傳 5，本月查詢回傳 42
        global.fetch
            .mockResolvedValueOnce({ ok: true, json: async () => ({ total: 5, records: [], page: 1, total_pages: 1 }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ total: 42, records: [], page: 1, total_pages: 5 }) });

        await loadConsultationStats();

        expect(document.getElementById('todayCount').textContent).toBe('5');
        expect(document.getElementById('monthlyCount').textContent).toBe('42');
    });

    test('fetchConsultationTotal 應回傳 total 欄位的數值', async () => {
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ total: 17, records: [], page: 1, total_pages: 2 }),
        });

        const result = await fetchConsultationTotal('2026-04-01', '2026-04-29');
        expect(result).toBe(17);

        // 驗證 URL 包含正確的查詢參數
        const calledUrl = global.fetch.mock.calls[0][0];
        expect(calledUrl).toContain('date_from=2026-04-01');
        expect(calledUrl).toContain('date_to=2026-04-29');
    });

    test('fetch 失敗時 loadConsultationStats 應顯示 "--"', async () => {
        // 兩個查詢都失敗
        global.fetch
            .mockRejectedValueOnce(new Error('Network error'))
            .mockRejectedValueOnce(new Error('Network error'));

        await loadConsultationStats();

        expect(document.getElementById('todayCount').textContent).toBe('--');
        expect(document.getElementById('monthlyCount').textContent).toBe('--');
    });
});

/* ═══════════════════════════════════════════════════════
   7. TestUtilityFunctions
   ═══════════════════════════════════════════════════════ */

describe('TestUtilityFunctions', () => {
    test('formatTimeForChart 在 day 粒度應回傳 MM/DD 格式', () => {
        // timestamp: 2026-04-29 12:00:00 UTC
        const ts = 1745928000;
        const result = formatTimeForChart(ts, 'day');
        // 應符合 MM/DD 格式（不含時間）
        expect(result).toMatch(/^\d{2}\/\d{2}$/);
    });

    test('formatTimeForChart 在 hour 粒度應回傳含時間的格式', () => {
        const ts = 1745928000;
        const result = formatTimeForChart(ts, 'hour');
        // 應符合 MM/DD HH:MM 格式
        expect(result).toMatch(/^\d{2}\/\d{2} \d{2}:\d{2}$/);
    });

    test('safeNum 應正確格式化數字並處理 null/NaN', () => {
        expect(safeNum(45.678, 1)).toBe('45.7');
        expect(safeNum(0, 0)).toBe('0');
        expect(safeNum(null, 1)).toBe('--');
        expect(safeNum(undefined, 1)).toBe('--');
        expect(safeNum(NaN, 1)).toBe('--');
    });

    test('showAlert 與 hideAlert 應切換 alertBar 的顯示狀態', () => {
        const alertBar = document.getElementById('alertBar');

        showAlert('測試訊息');
        expect(alertBar.classList.contains('show')).toBe(true);
        expect(alertBar.textContent).toBe('測試訊息');

        hideAlert();
        expect(alertBar.classList.contains('show')).toBe(false);
    });
});
