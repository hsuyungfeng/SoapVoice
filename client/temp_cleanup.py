"""Phase 31 & Phase 32: 本機暫存清理規則 (temp_cleanup.enforce_cap, enforce_retention).

(D-31-30, D-31-31, D-31-32, D-31-33, D-32-04, D-32-20)
清理規則保證：
1. 時間＋容量雙軌清理 (D-32-20)
   - 超過保存期限（預設 90 天，D-32-04）且已 acked 者由時間規則刪除 (reason="age")
   - 若仍超過容量上限 (max_bytes, Phase 31 預設 2GB)，依 FIFO 刪除最舊已 acked 者 (reason="cap")
2. 只刪除「已封存循環 (archived=True)」中「已 acked」的檔案 (D-31-30, D-31-33)
3. 由最舊的封存循環開始 (依 archived_at 由舊到新)
4. 未 acked 的檔案無論多舊、總量多大一律不刪 (D-31-32, D-32-20)
5. 未封存循環的檔案一律保留 (D-31-33)
6. manifest.json 永不刪除（紀錄永遠可追溯）
7. 統計並回報 unuploaded_bytes（未 acked 檔案總量，供快捷列警示）
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from client.segment_store import CycleManifest, SegmentStore

logger = logging.getLogger(__name__)


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    """解析 ISO 8601 時間字串為 UTC datetime。"""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _calc_dir_size(root: Path) -> int:
    """計算目錄下所有檔案總位元組數（排除不存在或無法讀取之項目）。"""
    total = 0
    if not root.exists():
        return 0
    for p in root.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _iter_deletable_files(c_dir: Path, curr_m: CycleManifest) -> Iterator[Tuple[Path, int]]:
    """產生指定封存循環中可安全刪除的檔案清單及其大小。

    只產生已 acked 的 chunks，以及在全部 chunks 都已 acked 時的衍生檔案。
    manifest.json 絕對不產生。
    """
    if not c_dir.exists() or not curr_m.archived:
        return

    # 1. 已 acked 的 chunk 檔案
    for seq_str in sorted(curr_m.chunks.keys(), key=lambda s: int(s) if s.isdigit() else 0):
        chunk = curr_m.chunks[seq_str]
        if chunk.get("acked") is True:
            chunk_name = chunk.get("path") or f"chunk_{int(seq_str):06d}.wav"
            chunk_file = c_dir / chunk_name
            if chunk_file.is_file():
                try:
                    sz = chunk_file.stat().st_size
                    yield chunk_file, sz
                except OSError:
                    pass

    # 2. 衍生檔案（full.wav, lan_result.json, screenshot.*）
    all_chunks_acked = (
        len(curr_m.chunks) > 0
        and all(ck.get("acked") is True for ck in curr_m.chunks.values())
    )
    if all_chunks_acked:
        for deriv_name in ("full.wav", "lan_result.json"):
            deriv_file = c_dir / deriv_name
            if deriv_file.is_file():
                try:
                    sz = deriv_file.stat().st_size
                    yield deriv_file, sz
                except OSError:
                    pass

        for shot_file in c_dir.glob("screenshot.*"):
            if shot_file.is_file():
                try:
                    sz = shot_file.stat().st_size
                    yield shot_file, sz
                except OSError:
                    pass


def _calc_unuploaded_bytes(store: SegmentStore) -> int:
    """計算所有未 acked 檔案之總位元組數。

    未 acked 包含：
    - 未封存或封存循環中未 acked 的 chunk 檔案
    - 含有未 acked chunk 的循環之衍生檔案（full.wav, screenshot.*）
    """
    unuploaded = 0
    cycles = store.list_cycles()
    for c in cycles:
        curr_m = store.load(c.cycle_id)
        if not curr_m:
            continue
        c_dir = store._cycle_dir(curr_m.cycle_id)
        if not c_dir.exists():
            continue

        all_chunks_acked = (
            len(curr_m.chunks) > 0
            and all(ck.get("acked") is True for ck in curr_m.chunks.values())
        )

        for seq_str, chunk in curr_m.chunks.items():
            if chunk.get("acked") is not True:
                chunk_name = chunk.get("path") or f"chunk_{int(seq_str):06d}.wav"
                f = c_dir / chunk_name
                if f.is_file():
                    try:
                        unuploaded += f.stat().st_size
                    except OSError:
                        pass

        # 若並非所有 chunk 皆 acked，衍生檔視為未完成上傳
        if not all_chunks_acked:
            for deriv_name in ("full.wav", "lan_result.json"):
                f = c_dir / deriv_name
                if f.is_file():
                    try:
                        unuploaded += f.stat().st_size
                    except OSError:
                        pass
            for f in c_dir.glob("screenshot.*"):
                if f.is_file():
                    try:
                        unuploaded += f.stat().st_size
                    except OSError:
                        pass

    return unuploaded


def enforce_retention(
    store: SegmentStore,
    max_bytes: int,
    retention_days: int = 90,
    now: Optional[Union[datetime, float]] = None,
) -> Dict[str, Any]:
    """雙軌清理：時間 (retention_days) + 容量 (max_bytes) 依 D-32-20。

    1. 時間規則：先刪除超過 retention_days 的已封存且已 acked 檔案 (reason="age")
    2. 容量規則：若總量仍大於 max_bytes，依最舊封存循環依序清理已 acked 檔案 (reason="cap")
    3. 未 acked 檔案無論多舊永不刪除
    4. 未封存循環永不刪除
    5. manifest.json 永不刪除
    """
    if now is None:
        now_dt = datetime.now(timezone.utc)
    elif isinstance(now, (int, float)):
        now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
    elif isinstance(now, datetime):
        now_dt = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    else:
        now_dt = datetime.now(timezone.utc)

    cutoff_dt = now_dt - timedelta(days=retention_days)
    total_size = _calc_dir_size(store.cycles_root)
    current_total = total_size
    deleted_files: List[str] = []
    reasons: Dict[str, str] = {}

    cycles = store.list_cycles()
    archived_cycles = [c for c in cycles if c.archived]
    archived_cycles.sort(key=lambda c: c.archived_at or c.created_at or "")

    # --- 步驟 1: 時間規則 (Age-based) ---
    for c in archived_cycles:
        curr_m = store.load(c.cycle_id)
        if not curr_m or not curr_m.archived:
            continue
        c_time = _parse_iso(curr_m.archived_at) or _parse_iso(curr_m.created_at)
        if not c_time or c_time > cutoff_dt:
            continue

        c_dir = store._cycle_dir(curr_m.cycle_id)
        for target_file, sz in _iter_deletable_files(c_dir, curr_m):
            try:
                target_file.unlink()
                current_total -= sz
                p_str = str(target_file)
                deleted_files.append(p_str)
                reasons[p_str] = "age"
                logger.info(
                    "Deleted expired acked file %s in cycle %s (age rule, freed %d bytes)",
                    target_file.name,
                    curr_m.cycle_id,
                    sz,
                )
            except OSError as exc:
                logger.warning("Failed to delete %s: %s", target_file, exc)

    # --- 步驟 2: 容量規則 (Cap-based FIFO) ---
    if current_total > max_bytes and archived_cycles:
        for c in archived_cycles:
            if current_total <= max_bytes:
                break
            curr_m = store.load(c.cycle_id)
            if not curr_m or not curr_m.archived:
                continue
            c_dir = store._cycle_dir(curr_m.cycle_id)

            for target_file, sz in _iter_deletable_files(c_dir, curr_m):
                p_str = str(target_file)
                if p_str in reasons:
                    continue  # 已在時間規則中刪除
                try:
                    target_file.unlink()
                    current_total -= sz
                    deleted_files.append(p_str)
                    reasons[p_str] = "cap"
                    logger.info(
                        "Deleted acked file %s in cycle %s (cap rule, freed %d bytes)",
                        target_file.name,
                        curr_m.cycle_id,
                        sz,
                    )
                except OSError as exc:
                    logger.warning("Failed to delete %s: %s", target_file, exc)

                if current_total <= max_bytes:
                    break

    skipped_reason: Optional[str] = None
    if current_total > max_bytes and len(deleted_files) == 0:
        skipped_reason = "no_eligible_files"
    elif current_total > max_bytes:
        skipped_reason = "cap_not_reached"

    unuploaded_bytes = _calc_unuploaded_bytes(store)

    return {
        "before": total_size,
        "after": current_total,
        "deleted_files": deleted_files,
        "reasons": reasons,
        "unuploaded_bytes": unuploaded_bytes,
        "skipped_reason": skipped_reason,
    }


def enforce_cap(store: SegmentStore, max_bytes: int) -> Dict[str, Any]:
    """若 cycles 目錄總量超過 max_bytes，依規則清理已封存且已 acked 之暫存檔。

    Phase 31 既有介面相容包裝函式。
    """
    total_size = _calc_dir_size(store.cycles_root)
    if total_size <= max_bytes:
        return {
            "before": total_size,
            "after": total_size,
            "deleted_files": [],
            "skipped_reason": None,
        }

    cycles = store.list_cycles()
    archived_cycles = [c for c in cycles if c.archived]

    if not archived_cycles:
        logger.info(
            "Cycles cache exceeds cap (%d > %d), but no archived cycles eligible for deletion",
            total_size,
            max_bytes,
        )
        return {
            "before": total_size,
            "after": total_size,
            "deleted_files": [],
            "skipped_reason": "no_archived_cycles",
        }

    archived_cycles.sort(key=lambda c: c.archived_at or c.created_at)

    current_total = total_size
    deleted_files: List[str] = []

    for c in archived_cycles:
        curr_m = store.load(c.cycle_id)
        if not curr_m or not curr_m.archived:
            continue

        c_dir = store._cycle_dir(curr_m.cycle_id)
        if not c_dir.exists():
            continue

        for target_file, sz in _iter_deletable_files(c_dir, curr_m):
            try:
                target_file.unlink()
                current_total -= sz
                deleted_files.append(str(target_file))
                logger.info(
                    "Deleted acked file %s in cycle %s (cap rule, freed %d bytes)",
                    target_file.name,
                    curr_m.cycle_id,
                    sz,
                )
            except OSError as exc:
                logger.warning("Failed to delete %s: %s", target_file, exc)
            if current_total <= max_bytes:
                break

        if current_total <= max_bytes:
            break

    skipped_reason: Optional[str] = None
    if current_total > max_bytes and len(deleted_files) == 0:
        skipped_reason = "no_eligible_files"
    elif current_total > max_bytes:
        skipped_reason = "cap_not_reached"

    return {
        "before": total_size,
        "after": current_total,
        "deleted_files": deleted_files,
        "skipped_reason": skipped_reason,
    }

