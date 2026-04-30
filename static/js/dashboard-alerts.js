/**
 * SoapVoice 監控儀表板 — 即時警報系統前端
 *
 * 負責：
 * 1. 輪詢 /api/v1/alerts/active（每 5 秒）
 * 2. 動態渲染警報 UI（slideInDown 動畫）
 * 3. Web Audio API 聲音通知（critical 警報三次嗶聲，warning 單次）
 * 4. 警報確認互動（POST acknowledge）
 * 5. localStorage 持久化聲音開關設定
 *
 * 依賴：
 *   - DOM 中存在 id="alert-container" 元素
 *   - /api/v1/alerts/active 端點
 *   - /api/v1/alerts/{id}/acknowledge 端點
 */

'use strict';

/* ═══════════════════════════════════════════════════════
   全域警報狀態
   ═══════════════════════════════════════════════════════ */

/**
 * alertState — 警報模組全域狀態
 * @property {Array}   activeAlerts        - 目前活躍警報陣列
 * @property {boolean} alertSoundEnabled   - 是否啟用聲音通知
 * @property {number}  autoRefreshInterval - 輪詢間隔（毫秒）
 * @property {number|null} pollingTimer    - setInterval 計時器 ID
 * @property {Set}     knownAlertIds       - 已知警報 ID 集合（用於偵測新警報）
 */
const alertState = {
    activeAlerts: [],
    alertSoundEnabled: true,
    autoRefreshInterval: 5000,
    pollingTimer: null,
    knownAlertIds: new Set(),
};

// ── 初始化：從 localStorage 讀取聲音設定 ─────────────────────────
(function initAlertSoundSetting() {
    try {
        const stored = localStorage.getItem('soapvoice_alert_sound');
        if (stored !== null) {
            alertState.alertSoundEnabled = stored === 'true';
        }
    } catch (e) {
        // localStorage 不可用（私密瀏覽模式），使用預設值
    }
})();


/* ═══════════════════════════════════════════════════════
   API 呼叫
   ═══════════════════════════════════════════════════════ */

/**
 * loadActiveAlerts — 從後端取得活躍警報並更新 UI
 *
 * 呼叫 GET /api/v1/alerts/active，更新 alertState.activeAlerts，
 * 偵測新警報（觸發聲音），並重新渲染警報容器。
 */
async function loadActiveAlerts() {
    try {
        const response = await fetch('/api/v1/alerts/active', {
            method: 'GET',
            headers: { 'Accept': 'application/json' },
        });

        if (!response.ok) {
            console.warn('[Alerts] API 回應異常:', response.status);
            return;
        }

        const data = await response.json();
        const alerts = data.alerts || [];

        // 偵測新警報（ID 不在已知集合中）
        const newAlerts = alerts.filter(a => !alertState.knownAlertIds.has(a.id));

        // 更新狀態
        alertState.activeAlerts = alerts;
        alerts.forEach(a => alertState.knownAlertIds.add(a.id));

        // 觸發聲音（僅對新 critical 警報）
        if (newAlerts.length > 0) {
            const hasCritical = newAlerts.some(a => a.severity === 'critical');
            const hasWarning = newAlerts.some(a => a.severity === 'warning');

            if (hasCritical) {
                playAlertSound('critical');
            } else if (hasWarning) {
                playAlertSound('warning');
            }
        }

        updateAlertUI(alerts);
    } catch (err) {
        console.warn('[Alerts] 載入警報失敗（網路錯誤）:', err.message);
    }
}


/**
 * acknowledgeAlert — 確認指定警報
 *
 * POST /api/v1/alerts/{alertId}/acknowledge?user=dashboard
 * 成功後從 UI 中移除該警報元素。
 *
 * @param {string} alertId - 警報 UUID
 */
async function acknowledgeAlert(alertId) {
    try {
        const response = await fetch(
            `/api/v1/alerts/${encodeURIComponent(alertId)}/acknowledge?user=dashboard`,
            {
                method: 'POST',
                headers: { 'Accept': 'application/json' },
            }
        );

        if (response.ok) {
            // 從 UI 移除該警報元素
            const elem = document.getElementById(`alert-item-${alertId}`);
            if (elem) {
                elem.style.animation = 'slideOutUp 0.3s ease forwards';
                setTimeout(() => elem.remove(), 300);
            }

            // 從狀態中移除
            alertState.activeAlerts = alertState.activeAlerts.filter(a => a.id !== alertId);
            alertState.knownAlertIds.delete(alertId);
        } else {
            console.warn('[Alerts] 確認警報失敗:', response.status);
        }
    } catch (err) {
        console.warn('[Alerts] 確認警報網路錯誤:', err.message);
    }
}


/* ═══════════════════════════════════════════════════════
   UI 渲染
   ═══════════════════════════════════════════════════════ */

/**
 * updateAlertUI — 更新警報容器 DOM
 *
 * 清空並重新渲染全部警報，或顯示無警報提示。
 *
 * @param {Array} alerts - 警報物件陣列
 */
function updateAlertUI(alerts) {
    const container = document.getElementById('alert-container');
    if (!container) return;

    if (!alerts || alerts.length === 0) {
        container.innerHTML = '<div class="alert-empty">目前無活躍警報</div>';
        return;
    }

    container.innerHTML = '';
    alerts.forEach(alert => {
        const elem = renderAlertBanner(alert);
        container.appendChild(elem);
    });
}


/**
 * renderAlertBanner — 建立單一警報 DOM 元素
 *
 * @param {Object} alert - 警報物件（含 id, type, severity, message, triggered_at, current_value, threshold）
 * @returns {HTMLElement} 警報 DOM 元素
 */
function renderAlertBanner(alert) {
    const div = document.createElement('div');
    div.id = `alert-item-${alert.id}`;
    div.className = `alert-item alert-${alert.severity}`;

    const iconMap = {
        gpu_high: '🔥',
        vram_high: '💾',
        queue_long: '📋',
    };
    const typeLabels = {
        gpu_high: 'GPU 使用率',
        vram_high: 'VRAM 使用率',
        queue_long: '請求佇列',
    };

    const icon = iconMap[alert.type] || '⚠️';
    const typeLabel = typeLabels[alert.type] || alert.type;
    const timeStr = formatAlertTime(alert.triggered_at);
    const valueStr = alert.type === 'queue_long'
        ? `${Math.round(alert.current_value)}`
        : `${alert.current_value.toFixed(1)}%`;
    const thresholdStr = alert.type === 'queue_long'
        ? `${Math.round(alert.threshold)}`
        : `${alert.threshold.toFixed(1)}%`;

    div.innerHTML = `
        <span class="alert-icon">${icon}</span>
        <div class="alert-content">
            <div class="alert-title">${typeLabel} — ${alert.severity === 'critical' ? '嚴重' : '警告'}</div>
            <div class="alert-detail">目前值：${valueStr} / 閾值：${thresholdStr}</div>
            <div class="alert-time">${timeStr}</div>
        </div>
        <button class="btn-acknowledge" onclick="acknowledgeAlert('${alert.id}')" title="確認此警報">✓ 確認</button>
    `;

    return div;
}


/* ═══════════════════════════════════════════════════════
   輪詢管理
   ═══════════════════════════════════════════════════════ */

/**
 * startAlertPolling — 啟動警報輪詢
 *
 * 立即執行一次，然後每隔 interval 毫秒重複。
 *
 * @param {number} interval - 輪詢間隔（毫秒，預設 5000）
 */
function startAlertPolling(interval) {
    const ms = interval || alertState.autoRefreshInterval;

    // 避免重複啟動
    if (alertState.pollingTimer !== null) {
        clearInterval(alertState.pollingTimer);
    }

    // 立即執行一次
    loadActiveAlerts();

    alertState.pollingTimer = setInterval(function () {
        loadActiveAlerts();
    }, ms);

    console.log('[Alerts] 警報輪詢已啟動（間隔', ms, 'ms）');
}


/**
 * stopAlertPolling — 停止警報輪詢
 */
function stopAlertPolling() {
    if (alertState.pollingTimer !== null) {
        clearInterval(alertState.pollingTimer);
        alertState.pollingTimer = null;
        console.log('[Alerts] 警報輪詢已停止');
    }
}


/* ═══════════════════════════════════════════════════════
   聲音通知（Web Audio API）
   ═══════════════════════════════════════════════════════ */

/**
 * playAlertSound — 播放警報聲音
 *
 * critical：三次嗶聲（200ms 開，100ms 間隔）
 * warning：單次 400ms 嗶聲
 *
 * @param {'critical'|'warning'} severity - 警報嚴重程度
 */
function playAlertSound(severity) {
    if (!alertState.alertSoundEnabled) return;

    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;

        const ctx = new AudioContext();

        if (severity === 'critical') {
            // 三次嗶聲
            _beep(ctx, 0, 200, 880);
            _beep(ctx, 300, 200, 880);
            _beep(ctx, 600, 200, 1046);
        } else {
            // 單次 400ms 嗶聲
            _beep(ctx, 0, 400, 660);
        }

        // 2 秒後關閉 AudioContext 釋放資源
        setTimeout(function () {
            ctx.close().catch(function () {});
        }, 2000);
    } catch (e) {
        console.warn('[Alerts] 無法播放警報音效:', e.message);
    }
}

/**
 * _beep — 產生單一嗶聲（私有輔助函式）
 *
 * @param {AudioContext} ctx      - AudioContext 實例
 * @param {number}       delayMs  - 延遲開始時間（毫秒）
 * @param {number}       durationMs - 持續時間（毫秒）
 * @param {number}       frequency  - 頻率（Hz）
 */
function _beep(ctx, delayMs, durationMs, frequency) {
    try {
        const oscillator = ctx.createOscillator();
        const gainNode = ctx.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);

        oscillator.type = 'sine';
        oscillator.frequency.value = frequency;

        const startTime = ctx.currentTime + delayMs / 1000;
        const endTime = startTime + durationMs / 1000;

        gainNode.gain.setValueAtTime(0.3, startTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, endTime);

        oscillator.start(startTime);
        oscillator.stop(endTime);
    } catch (e) {
        // 忽略單次嗶聲失敗
    }
}


/**
 * setAlertSoundEnabled — 切換聲音通知開關
 *
 * @param {boolean} enabled - true 開啟，false 關閉
 */
function setAlertSoundEnabled(enabled) {
    alertState.alertSoundEnabled = Boolean(enabled);
    try {
        localStorage.setItem('soapvoice_alert_sound', String(alertState.alertSoundEnabled));
    } catch (e) {
        // localStorage 不可用
    }

    const btn = document.getElementById('alert-sound-toggle');
    if (btn) {
        btn.textContent = alertState.alertSoundEnabled ? '🔔 聲音' : '🔕 靜音';
        btn.title = alertState.alertSoundEnabled ? '點擊關閉聲音通知' : '點擊開啟聲音通知';
    }
}


/* ═══════════════════════════════════════════════════════
   格式化輔助
   ═══════════════════════════════════════════════════════ */

/**
 * formatAlertTime — 相對時間格式化
 *
 * @param {number} timestamp - Unix 時間戳（秒）
 * @returns {string} 人類可讀的相對時間字串
 */
function formatAlertTime(timestamp) {
    const now = Date.now() / 1000;
    const diff = now - timestamp;

    if (diff < 60) {
        return '剛才';
    } else if (diff < 3600) {
        const minutes = Math.floor(diff / 60);
        return `${minutes} 分鐘前`;
    } else if (diff < 86400) {
        const hours = Math.floor(diff / 3600);
        return `${hours} 小時前`;
    } else {
        const days = Math.floor(diff / 86400);
        return `${days} 天前`;
    }
}


/* ═══════════════════════════════════════════════════════
   CSS 注入（動畫與警報樣式）
   ═══════════════════════════════════════════════════════ */

(function injectAlertStyles() {
    if (document.getElementById('alert-styles')) return;

    const style = document.createElement('style');
    style.id = 'alert-styles';
    style.textContent = `
        /* ── 警報容器 ─────────────────────────────────── */
        .alert-container {
            margin: 0 0 16px 0;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .alert-empty {
            color: #888;
            font-size: 13px;
            padding: 12px 0;
            text-align: center;
        }

        /* ── 警報條目 ─────────────────────────────────── */
        .alert-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            border-radius: 8px;
            border-left: 4px solid transparent;
            background: #fff;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
            animation: slideInDown 0.3s ease forwards;
        }

        .alert-critical {
            border-left-color: #e53e3e;
            background: #fff5f5;
        }

        .alert-warning {
            border-left-color: #d69e2e;
            background: #fffbeb;
        }

        .alert-icon {
            font-size: 20px;
            flex-shrink: 0;
        }

        .alert-content {
            flex: 1;
            min-width: 0;
        }

        .alert-title {
            font-weight: 600;
            font-size: 14px;
            color: #2d3748;
            margin-bottom: 2px;
        }

        .alert-detail {
            font-size: 12px;
            color: #718096;
        }

        .alert-time {
            font-size: 11px;
            color: #a0aec0;
            margin-top: 2px;
        }

        /* ── 確認按鈕 ─────────────────────────────────── */
        .btn-acknowledge {
            padding: 5px 12px;
            font-size: 12px;
            font-weight: 600;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            background: #ebf8ff;
            color: #2b6cb0;
            transition: background 0.2s;
            flex-shrink: 0;
        }

        .btn-acknowledge:hover {
            background: #bee3f8;
        }

        /* ── 動畫 ─────────────────────────────────────── */
        @keyframes slideInDown {
            from {
                opacity: 0;
                transform: translateY(-12px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes slideOutUp {
            from {
                opacity: 1;
                transform: translateY(0);
            }
            to {
                opacity: 0;
                transform: translateY(-12px);
            }
        }

        /* ── 聲音切換按鈕 ─────────────────────────────── */
        #alert-sound-toggle {
            padding: 5px 12px;
            font-size: 12px;
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            cursor: pointer;
            background: #f7fafc;
            color: #4a5568;
            transition: background 0.2s;
        }

        #alert-sound-toggle:hover {
            background: #edf2f7;
        }
    `;

    document.head.appendChild(style);
})();


/* ═══════════════════════════════════════════════════════
   匯出（供測試環境使用）
   ═══════════════════════════════════════════════════════ */

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        alertState,
        loadActiveAlerts,
        startAlertPolling,
        stopAlertPolling,
        updateAlertUI,
        renderAlertBanner,
        playAlertSound,
        setAlertSoundEnabled,
        acknowledgeAlert,
        formatAlertTime,
    };
}

// 掛載至 window（瀏覽器環境）
if (typeof window !== 'undefined') {
    window.alertState = alertState;
    window.loadActiveAlerts = loadActiveAlerts;
    window.startAlertPolling = startAlertPolling;
    window.stopAlertPolling = stopAlertPolling;
    window.updateAlertUI = updateAlertUI;
    window.renderAlertBanner = renderAlertBanner;
    window.playAlertSound = playAlertSound;
    window.setAlertSoundEnabled = setAlertSoundEnabled;
    window.acknowledgeAlert = acknowledgeAlert;
    window.formatAlertTime = formatAlertTime;
}
