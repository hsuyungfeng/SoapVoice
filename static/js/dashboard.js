/**
 * SoapVoice 監控儀表板前端邏輯
 *
 * 負責：
 * 1. SSE 連線管理（initSSE）— 接收 GPU/VRAM/佇列即時指標
 * 2. UI 即時更新（updateMetricsUI）
 * 3. 歷史趨勢圖（initChart / loadHistoryAndUpdate）— Chart.js 折線圖
 * 4. 看診統計（loadConsultationStats）— 本日 / 本月
 *
 * 所有外部依賴：
 *   - Chart.js 4.x（由 HTML 透過 CDN 載入）
 *   - /api/v1/metrics/stream  — SSE 端點
 *   - /api/v1/metrics/history — 歷史查詢端點
 *   - /api/v1/records/search  — 看診紀錄查詢端點
 */

'use strict';

/* ═══════════════════════════════════════════════════════
   全域狀態物件
   ═══════════════════════════════════════════════════════ */

/**
 * dashboardState — 儀表板全域狀態
 * @property {boolean}  connected         - SSE 是否已連線
 * @property {object|null} lastMetrics    - 最新一筆指標資料
 * @property {Array}    metricsHistory    - 已接收的歷史指標陣列（用於 SSE 即時追加）
 * @property {Chart|null} chart           - Chart.js 實例
 * @property {string}   currentGranularity - 目前圖表粒度（'hour' | 'day'）
 * @property {EventSource|null} eventSource - SSE EventSource 實例
 */
const dashboardState = {
    connected: false,
    lastMetrics: null,
    metricsHistory: [],
    chart: null,
    currentGranularity: 'hour',
    eventSource: null,
};

/* ═══════════════════════════════════════════════════════
   SSE 連線管理
   ═══════════════════════════════════════════════════════ */

/**
 * initSSE — 建立 SSE 連線至 /api/v1/metrics/stream
 *
 * 瀏覽器原生 EventSource 提供自動重連機制，
 * 此函式設定 onopen / onmessage / onerror 三個回呼。
 */
function initSSE() {
    // 若已有連線，先關閉舊的
    if (dashboardState.eventSource) {
        dashboardState.eventSource.close();
    }

    const es = new EventSource('/api/v1/metrics/stream');
    dashboardState.eventSource = es;

    /* 連線成功 */
    es.onopen = function () {
        dashboardState.connected = true;
        setConnectionStatus('connected', '已連線');
        hideAlert();
    };

    /* 接收指標事件 */
    es.onmessage = function (event) {
        let data;
        try {
            data = JSON.parse(event.data);
        } catch (e) {
            console.warn('[SSE] JSON 解析失敗:', e);
            return;
        }

        // 忽略初始化佔位符或錯誤訊息
        if (data.status === 'initializing' || data.error) {
            console.info('[SSE] 伺服器訊息:', data.status || data.error);
            return;
        }

        // 更新全域狀態
        dashboardState.lastMetrics = data;
        dashboardState.metricsHistory.push(data);

        // 限制本地歷史長度，避免記憶體膨脹
        if (dashboardState.metricsHistory.length > 500) {
            dashboardState.metricsHistory.shift();
        }

        // 更新 UI
        updateMetricsUI();

        // 更新最後接收時間
        const timeEl = document.getElementById('lastUpdateTime');
        if (timeEl) {
            timeEl.textContent = '最後更新：' + formatRelativeTime(data.timestamp);
        }
    };

    /* SSE 錯誤 / 斷線 */
    es.onerror = function () {
        dashboardState.connected = false;
        setConnectionStatus('disconnected', '連線失敗');
        showAlert('SSE 連線中斷，瀏覽器將自動重連...');
    };
}

/* ═══════════════════════════════════════════════════════
   UI 更新
   ═══════════════════════════════════════════════════════ */

/**
 * updateMetricsUI — 從 dashboardState.lastMetrics 更新 HTML 元素
 *
 * 依序更新：
 *  - GPU 使用率（#gpuPercent）
 *  - VRAM（#vramMb、#vramTotal、#vramBarFill）
 *  - 佇列長度（#queueLength）
 */
function updateMetricsUI() {
    const m = dashboardState.lastMetrics;
    if (!m) return;

    /* GPU 使用率 */
    const gpuEl = document.getElementById('gpuPercent');
    if (gpuEl) {
        gpuEl.innerHTML = safeNum(m.gpu_percent, 1) + '<span class="unit">%</span>';
    }
    const gpuSub = document.getElementById('gpuSub');
    if (gpuSub) {
        gpuSub.textContent = m.gpu_percent >= 90
            ? '⚠ GPU 使用率偏高'
            : '運作正常';
    }

    /* VRAM */
    const vramEl = document.getElementById('vramMb');
    if (vramEl) {
        vramEl.innerHTML = safeNum(m.vram_mb, 0) + '<span class="unit">MB</span>';
    }
    const vramTotalEl = document.getElementById('vramTotal');
    if (vramTotalEl && m.gpu_memory_total_mb) {
        vramTotalEl.textContent = '/ ' + safeNum(m.gpu_memory_total_mb, 0) + ' MB';
    }

    // VRAM 進度條
    const barEl = document.getElementById('vramBarFill');
    if (barEl && m.gpu_memory_total_mb && m.gpu_memory_total_mb > 0) {
        const pct = Math.min(100, (m.vram_mb / m.gpu_memory_total_mb) * 100);
        barEl.style.width = pct.toFixed(1) + '%';
        const progressbar = barEl.closest('[role="progressbar"]');
        if (progressbar) progressbar.setAttribute('aria-valuenow', pct.toFixed(0));
    }

    /* 佇列長度 */
    const queueEl = document.getElementById('queueLength');
    if (queueEl) {
        queueEl.innerHTML = safeNum(m.queue_length, 0) + '<span class="unit">筆</span>';
    }
    const queueSub = document.getElementById('queueSub');
    if (queueSub) {
        queueSub.textContent = m.queue_length > 10
            ? '⚠ 佇列積壓，請注意'
            : (m.queue_length === 0 ? '佇列空閒' : '處理中');
    }
}

/* ═══════════════════════════════════════════════════════
   歷史趨勢圖 (Chart.js)
   ═══════════════════════════════════════════════════════ */

/**
 * initChart — 向 /api/v1/metrics/history 取得初始資料並建立 Chart.js 折線圖
 *
 * @param {string} granularity - 粒度（'hour' | 'day'），預設使用 dashboardState.currentGranularity
 */
async function initChart(granularity) {
    granularity = granularity || dashboardState.currentGranularity;
    const url = '/api/v1/metrics/history?granularity=' + granularity + '&limit=100';

    let records = [];
    try {
        const resp = await fetch(url);
        if (!resp.ok) {
            throw new Error('HTTP ' + resp.status);
        }
        const json = await resp.json();
        records = Array.isArray(json.metrics) ? json.metrics : [];
    } catch (err) {
        console.error('[Chart] 取得歷史資料失敗:', err);
        showAlert('無法載入歷史圖表資料：' + err.message);
        records = [];
    }

    // 依時間正序排列
    records.sort(function (a, b) { return a.timestamp - b.timestamp; });

    const labels = records.map(function (r) { return formatTimeForChart(r.timestamp, granularity); });
    const gpuData = records.map(function (r) { return r.gpu_percent; });

    const canvas = document.getElementById('metricsChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // 銷毀舊圖表（若存在）
    if (dashboardState.chart) {
        dashboardState.chart.destroy();
        dashboardState.chart = null;
    }

    dashboardState.chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'GPU 使用率 (%)',
                    data: gpuData,
                    borderColor: '#0066cc',
                    backgroundColor: 'rgba(0,102,204,0.08)',
                    borderWidth: 2,
                    pointRadius: records.length > 60 ? 0 : 3,
                    pointHoverRadius: 5,
                    tension: 0.3,
                    fill: true,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index',
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { font: { size: 12 } },
                },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            return ' GPU: ' + (ctx.parsed.y != null ? ctx.parsed.y.toFixed(1) : '--') + '%';
                        },
                    },
                },
            },
            scales: {
                x: {
                    ticks: {
                        maxRotation: 45,
                        font: { size: 11 },
                        maxTicksLimit: 12,
                    },
                    grid: { display: false },
                },
                y: {
                    min: 0,
                    max: 100,
                    ticks: {
                        callback: function (v) { return v + '%'; },
                        font: { size: 11 },
                    },
                    grid: { color: 'rgba(0,0,0,0.06)' },
                },
            },
        },
    });
}

/**
 * loadHistoryAndUpdate — 切換粒度後重新載入圖表
 *
 * @param {string} granularity - 新粒度（'hour' | 'day'）
 */
async function loadHistoryAndUpdate(granularity) {
    dashboardState.currentGranularity = granularity;

    // 更新粒度按鈕樣式
    document.querySelectorAll('.granularity-btn').forEach(function (btn) {
        btn.classList.toggle('active', btn.dataset.granularity === granularity);
    });

    await initChart(granularity);
}

/* ═══════════════════════════════════════════════════════
   看診統計
   ═══════════════════════════════════════════════════════ */

/**
 * loadConsultationStats — 查詢本日 / 本月看診次數並更新 UI
 *
 * 使用 /api/v1/records/search 端點，以 date_from / date_to 篩選。
 * page_size=1 只需 total 欄位，不浪費頻寬。
 */
async function loadConsultationStats() {
    const today = getTodayString();               // 'YYYY-MM-DD'
    const monthStart = getMonthStartString();     // 'YYYY-MM-01'

    // 更新日期標籤
    const todayDateEl = document.getElementById('todayDate');
    if (todayDateEl) todayDateEl.textContent = today;

    const monthlyRangeEl = document.getElementById('monthlyRange');
    if (monthlyRangeEl) monthlyRangeEl.textContent = monthStart + ' ~ ' + today;

    // 並行查詢本日與本月
    const [todayTotal, monthTotal] = await Promise.all([
        fetchConsultationTotal(today, today),
        fetchConsultationTotal(monthStart, today),
    ]);

    const todayEl = document.getElementById('todayCount');
    if (todayEl) todayEl.textContent = todayTotal !== null ? String(todayTotal) : '--';

    const monthEl = document.getElementById('monthlyCount');
    if (monthEl) monthEl.textContent = monthTotal !== null ? String(monthTotal) : '--';
}

/**
 * fetchConsultationTotal — 查詢指定日期範圍內的看診總數
 *
 * @param {string} dateFrom - 起始日期（YYYY-MM-DD）
 * @param {string} dateTo   - 結束日期（YYYY-MM-DD）
 * @returns {Promise<number|null>} 看診總數，失敗時回傳 null
 */
async function fetchConsultationTotal(dateFrom, dateTo) {
    const url = '/api/v1/records/search?name=&date_from='
        + encodeURIComponent(dateFrom)
        + '&date_to='
        + encodeURIComponent(dateTo)
        + '&page=1&page_size=1';
    try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const json = await resp.json();
        // 回傳 total 欄位（整數），若不存在則回傳 0
        return typeof json.total === 'number' ? json.total : 0;
    } catch (err) {
        console.error('[Stats] 查詢看診統計失敗:', err);
        return null;
    }
}

/* ═══════════════════════════════════════════════════════
   工具函式
   ═══════════════════════════════════════════════════════ */

/**
 * formatRelativeTime — 將 Unix timestamp 格式化為本地時間字串
 *
 * @param {number} ts - Unix timestamp（秒）
 * @returns {string} 格式化後的本地時間，如 "12:34:56"
 */
function formatRelativeTime(ts) {
    if (ts == null) return '--';
    const d = new Date(ts * 1000);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    return hh + ':' + mm + ':' + ss;
}

/**
 * formatTimeForChart — 將 Unix timestamp 格式化為圖表 X 軸標籤
 *
 * @param {number} ts          - Unix timestamp（秒）
 * @param {string} granularity - 粒度（'hour' | 'day'）
 * @returns {string} 格式化後的標籤
 */
function formatTimeForChart(ts, granularity) {
    if (ts == null) return '';
    const d = new Date(ts * 1000);
    const mo = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');

    if (granularity === 'day') {
        return mo + '/' + dd;
    }
    // hour（預設）
    return mo + '/' + dd + ' ' + hh + ':' + mm;
}

/**
 * safeNum — 安全格式化數字，若為 null/undefined 回傳 '--'
 *
 * @param {number|null|undefined} val - 輸入值
 * @param {number} decimals           - 小數位數
 * @returns {string}
 */
function safeNum(val, decimals) {
    if (val == null || isNaN(val)) return '--';
    return Number(val).toFixed(decimals);
}

/**
 * getTodayString — 回傳今日日期字串（YYYY-MM-DD，本地時間）
 * @returns {string}
 */
function getTodayString() {
    const d = new Date();
    const y = d.getFullYear();
    const mo = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return y + '-' + mo + '-' + dd;
}

/**
 * getMonthStartString — 回傳本月第一天日期字串（YYYY-MM-01，本地時間）
 * @returns {string}
 */
function getMonthStartString() {
    const d = new Date();
    const y = d.getFullYear();
    const mo = String(d.getMonth() + 1).padStart(2, '0');
    return y + '-' + mo + '-01';
}

/**
 * setConnectionStatus — 更新連線狀態指示器的外觀與文字
 *
 * @param {'connected'|'disconnected'|'connecting'} status
 * @param {string} label - 顯示文字
 */
function setConnectionStatus(status, label) {
    const dot = document.getElementById('connectionDot');
    const indicator = document.getElementById('connectionIndicator');
    if (!dot || !indicator) return;

    dot.className = 'connection-dot ' + status;
    indicator.textContent = label;
}

/**
 * showAlert — 顯示頁面頂部通知列
 * @param {string} msg
 */
function showAlert(msg) {
    const el = document.getElementById('alertBar');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
}

/**
 * hideAlert — 隱藏通知列
 */
function hideAlert() {
    const el = document.getElementById('alertBar');
    if (el) el.classList.remove('show');
}

/* ═══════════════════════════════════════════════════════
   粒度切換事件綁定
   ═══════════════════════════════════════════════════════ */

/**
 * bindGranularityButtons — 綁定粒度選擇器按鈕的 click 事件
 */
function bindGranularityButtons() {
    document.querySelectorAll('.granularity-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const gran = btn.dataset.granularity;
            if (gran && gran !== dashboardState.currentGranularity) {
                loadHistoryAndUpdate(gran);
            }
        });
    });
}

/* ═══════════════════════════════════════════════════════
   主初始化函式
   ═══════════════════════════════════════════════════════ */

/**
 * initDashboard — 頁面載入後的主入口
 *
 * 依序：
 *  1. 設定連線中狀態
 *  2. 初始化 SSE 連線
 *  3. 初始化歷史圖表
 *  4. 載入看診統計
 *  5. 綁定粒度按鈕
 */
async function initDashboard() {
    setConnectionStatus('connecting', '連線中...');

    // 同步啟動 SSE（非阻塞）
    initSSE();

    // 並行初始化圖表與統計
    await Promise.all([
        initChart(dashboardState.currentGranularity),
        loadConsultationStats(),
    ]);

    bindGranularityButtons();

    // Phase 12-03：啟動即時警報輪詢（5 秒間隔）
    if (typeof startAlertPolling === 'function') {
        startAlertPolling(5000);
    }
}

/* ═══════════════════════════════════════════════════════
   DOM Ready
   ═══════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', function () {
    initDashboard().catch(function (err) {
        console.error('[Dashboard] 初始化失敗:', err);
        showAlert('儀表板初始化失敗，請重新整理頁面。');
    });
});

/* ═══════════════════════════════════════════════════════
   匯出（供測試環境使用）
   ═══════════════════════════════════════════════════════ */

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
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
        getTodayString,
        getMonthStartString,
        setConnectionStatus,
        showAlert,
        hideAlert,
        bindGranularityButtons,
        initDashboard,
    };
}
