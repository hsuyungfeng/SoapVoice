---
phase: 11-lan-client
plan: "03"
subsystem: client/offline-resilience
tags: [client, local-storage, retry, exponential-backoff, queue, persistence, resilience]
requires: [11-01, 11-02]
provides:
  - LocalStorageManager
  - PendingUpload
  - RetryManager
  - 整合本機暫存與指數退避至 LANClient
affects:
  - client/lan_client.py
  - client/main.py
tech-stack:
  added: [json (stdlib), dataclasses, pathlib (atomic write)]
  patterns: [single queue.json + atomic replace, dataclass serialization, exponential backoff with jitter-free deterministic delays, async sleep gate]
key-files:
  created:
    - client/local_storage.py
    - client/retry_manager.py
  modified:
    - client/lan_client.py
    - client/main.py
    - tests/test_client.py
decisions:
  - 採單一 queue.json 集中管理（原子寫入：tmp + replace），避免散檔導致的同步漏寫
  - PendingUpload 採 dataclass + asdict / from_dict（容錯：缺欄位以預設值補齊）
  - 隊列上限預設 10 筆，先 drop_oldest 再 append（避免短暫超限）
  - 指數退避 2-4-8 秒（base=2.0, multiplier=2.0, max_retries=3）；參數可由 LANConfig 覆蓋
  - 連線恢復觸發點：unknown→healthy 與 offline→healthy 皆觸發補傳（涵蓋啟動情境）
  - 重試流程：成功→remove_pending；失敗→increment_retry_count + break；下次健康檢查再恢復
  - retry_in_progress 旗標：避免重複 retry coroutine 同時跑
  - FileNotFoundError 期間自動移出隊列（無法復原），記 error log
metrics:
  duration: 約 12 分鐘
  completed-date: 2026-04-27
  client-loc: 3 模組共 1020 行（local_storage 303 + retry_manager 193 + lan_client 524）
  test-loc: 1507 行（test_client.py）
  test-count: 60 通過 / 60 總計（11-03 新增 22）
---

# Phase 11 Plan 03: 本機暫存與重試機制 Summary

完成客戶端離線韌性層：未上傳成功的問診透過 LocalStorageManager 序列化至本機 `~/AppData/Local/SoapVoice/cache/pending/queue.json`，連線恢復後 RetryManager 以 2-4-8 秒指數退避自動補傳，最多 3 次，超限自動清出隊列。

## 一句話摘要

`LocalStorageManager` + `RetryManager` 整合至 `LANClient`，提供斷網恢復、重啟還原、佇列上限保護的離線韌性層；22 個新測試 / 60 個 client 測試全綠。

## 已交付檔案

| 檔案                       | 角色             | 行數    | 狀態             |
| -------------------------- | ---------------- | ------- | ---------------- |
| `client/local_storage.py`  | 暫存隊列 + 持久化 | 303     | 既存（2609705）   |
| `client/retry_manager.py`  | 指數退避 + 狀態  | 193     | 既存（34d8d71）   |
| `client/lan_client.py`     | 整合本機暫存 + 重試 | 524     | 修改             |
| `client/main.py`           | 顯式 key_link import | +2 行 | 修改             |
| `tests/test_client.py`     | 22 新測試 + 2 修正 | 1507    | 修改             |

## Tasks 完成情形

### Task 1 — 本機暫存管理模組（client/local_storage.py）

- `PendingUpload` dataclass（session_id / audio_path / screenshot_path / patient_name / doctor_name / queued_at / retry_count）含 `to_dict` / `from_dict`
- `LocalStorageManager`：建構子自動載入既有 queue.json；新增/移除/查詢/重試計數遞增；上限預設 10
- 隊列序列化採「寫入 tmp_file → tmp.replace(queue_file)」原子操作（POSIX/Windows 相容）
- 損毀 JSON 容錯：記 error，回退為空隊列，不丟例外
- 9 個單元測試全部通過

### Task 2 — 重試策略與指數退避（client/retry_manager.py）

- `get_retry_delay(retry_count)`：base × multiplier^retry_count
- `should_retry(session_id, count)`：count < max_retries
- `wait_before_retry(retry_count)`：async sleep 後回傳是否續退
- `mark_retry_scheduled` / `reset_state` / `get_state`：狀態追蹤（next_retry_at / last_attempt_at）
- 建構子驗證 base_delay >= 0 / max_retries >= 0 / multiplier >= 1.0
- 6 個單元測試全部通過（含預設值、邊界、async wait 計時）

### Task 3 — 整合至 LANClient + main.py

- LANClient 建構子自動建 `self.storage` / `self.retry_manager`
- `upload_consultation` 失敗 → `_enqueue_failed`（生成 YYYYMMDD_HHMMSS_xxxxxxxx 格式 session_id）
- `retry_pending_uploads`：迴圈處理隊列；成功 remove；失敗 increment + break（避免雪崩）
- `_set_status`：unknown→healthy 與 offline→healthy 兩種路徑均觸發 `asyncio.create_task(retry_pending_uploads())`
- `_retry_in_progress` 旗標：避免重入
- FileNotFoundError 期間自動清出（檔案被刪不可復原）
- main.py 顯式 import LocalStorageManager / RetryManager（滿足計畫 key_link 規範）
- 7 個整合測試全部通過

## 驗證結果

| 驗證項                               | 狀態 | 證據                                             |
| ------------------------------------ | ---- | ------------------------------------------------ |
| LocalStorageManager 完整 CRUD        | PASS | TestLocalStorageManager 9/9                       |
| 隊列序列化 queue.json 可往返          | PASS | test_local_storage_save_load                      |
| 上限 10 筆，溢出自動刪最舊            | PASS | test_local_storage_queue_overflow                 |
| 損毀 JSON 不崩潰                      | PASS | test_local_storage_corrupt_queue_json             |
| 指數退避 2-4-8 秒                     | PASS | test_retry_manager_backoff_calculation            |
| 最多 3 次重試                         | PASS | test_retry_manager_should_retry                   |
| async 等待                            | PASS | test_retry_manager_wait_before_retry              |
| 應用啟動自動載入隊列                  | PASS | test_lan_client_restore_pending_uploads           |
| 上傳失敗自動入隊                      | PASS | test_lan_client_upload_failure_queue              |
| 重試成功移除暫存                      | PASS | test_lan_client_retry_pending_uploads_success     |
| 重試失敗保留 + retry_count++          | PASS | test_lan_client_retry_pending_uploads_failure     |
| 超過 max_retries 自動移除             | PASS | test_lan_client_max_retries_exceeded              |
| 連線恢復自動觸發補傳                  | PASS | test_lan_client_health_recovery_triggers_retry    |
| session_id 格式 YYYYMMDD_HHMMSS_xxx   | PASS | test_lan_client_session_id_format                 |
| 整體 client 測試套件                  | PASS | 60/60 passed                                       |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 修正 11-02 兩個既有測試以匹配 11-03 新 schema**

- **發現於：** 跑全套 `tests/test_client.py` 時
- **問題：** `test_lan_client_upload_failure_queue` 與 `test_lan_client_load_pending_from_disk` 仍假設舊 schema（`pending_*.json` 散檔），但 11-03 已切換至單一 `pending/queue.json` 集中管理
- **修正：** 將斷言指向 `cache/pending/queue.json` 並驗證 `list[dict]` 格式；預塞測試資料亦以新 schema 寫入
- **檔案：** `tests/test_client.py`
- **提交：** 7a798a2

**2. [Rule 2 - Missing critical functionality] 補強 main.py key_link 顯式 import**

- **發現於：** Task 3 收尾時檢查計畫 `key_links` 規範
- **問題：** 計畫要求 `client/main.py → client/local_storage.py via "import LocalStorageManager"`；原本只透過 `LANClient` 間接引入
- **修正：** 在 main.py 加入顯式 `from client.local_storage import LocalStorageManager` 與 `from client.retry_manager import RetryManager`（含 noqa 標記說明用途）
- **檔案：** `client/main.py`
- **提交：** 7a798a2

### 既有提交追溯

`client/local_storage.py` 與 `client/retry_manager.py` 已在 Phase 11-02 收尾時先行提交（commits 2609705、34d8d71）；本計畫主要交付為「整合 + 測試」，於提交 7a798a2 中完成。

## Threat Model 對照

| Threat ID | Status | 證據                                                  |
| --------- | ------ | ----------------------------------------------------- |
| T-11-13   | mitigated | queue.json 寫入 `~/AppData/Local/SoapVoice/cache/pending/`（僅當前使用者讀取） |
| T-11-14   | accepted | LAN 內網使用，未加密 — 留待 Phase 12 啟用 HTTPS         |
| T-11-15   | mitigated | 指數退避 + max_retries=3 + retry_in_progress 旗標 + 超限自動清出 |
| T-11-16   | mitigated | 每次重試 logger.info 寫入 soapvoice_client.log；queue.json 含 queued_at |

## Known Stubs

無 — 所有實作均為功能性，無佔位資料或 TODO 標記。

## Threat Flags

無新增非預期攻擊面 — 本計畫僅在客戶端本機新增暫存目錄，未引入新網路端點或新 trust boundary。

## Self-Check: PASSED

驗證項：
- `client/local_storage.py` — FOUND（303 行）
- `client/retry_manager.py` — FOUND（193 行）
- `client/lan_client.py` 整合 — FOUND（524 行）
- `client/main.py` 顯式 import — FOUND
- `tests/test_client.py` — FOUND（1507 行 / 60 測試）
- Commit 7a798a2 — FOUND
- Commit 34d8d71 (RetryManager) — FOUND
- Commit 2609705 (LocalStorageManager) — FOUND
- 全套件 `uv run pytest tests/test_client.py` — 60 passed
