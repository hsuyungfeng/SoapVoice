"""Phase 31: 本機暫存清理規則 (temp_cleanup.enforce_cap).

(D-31-30, D-31-31, D-31-32, D-31-33)
清理規則保證：
1. 只在本機暫存總量超過上限時執行 (D-31-31)
2. 只刪除「已封存循環 (archived=True)」中「已 acked」的檔案 (D-31-30, D-31-33)
3. 由最舊的封存循環開始 (依 archived_at 由舊到新)
4. 未 acked 的檔案無論大小一律不刪 (D-31-32)
5. 未封存循環的檔案一律保留 (D-31-33)
6. manifest.json 永不刪除（紀錄永遠可追溯）
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from client.segment_store import SegmentStore

logger = logging.getLogger(__name__)


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


def enforce_cap(store: SegmentStore, max_bytes: int) -> Dict[str, Any]:
    """若 cycles 目錄總量超過 max_bytes，依規則清理已封存且已 acked 之暫存檔。

    回傳：
        {
            "before": 原始大小 (bytes),
            "after": 清理後大小 (bytes),
            "deleted_files": 被刪除之檔案路徑清單,
            "skipped_reason": 未執行或未達標之原因 (可為 None)
        }
    """
    total_size = _calc_dir_size(store.cycles_root)
    if total_size <= max_bytes:
        return {
            "before": total_size,
            "after": total_size,
            "deleted_files": [],
            "skipped_reason": None,
        }

    # 取得所有循環並過濾出已封存者
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

    # 依 archived_at 由舊到新排序
    archived_cycles.sort(key=lambda c: c.archived_at or c.created_at)

    current_total = total_size
    deleted_files: List[str] = []

    for c in archived_cycles:
        # 重讀 manifest 確認狀態避免競態
        curr_m = store.load(c.cycle_id)
        if not curr_m or not curr_m.archived:
            continue

        c_dir = store._cycle_dir(curr_m.cycle_id)
        if not c_dir.exists():
            continue

        # 1. 清理已 acked 的 chunk 檔案
        for seq_str in sorted(curr_m.chunks.keys(), key=lambda s: int(s) if s.isdigit() else 0):
            chunk = curr_m.chunks[seq_str]
            # D-31-30, D-31-32: 未 acked 嚴禁刪除
            if chunk.get("acked") is True:
                chunk_name = chunk.get("path") or f"chunk_{int(seq_str):06d}.wav"
                chunk_file = c_dir / chunk_name
                if chunk_file.is_file():
                    sz = chunk_file.stat().st_size
                    try:
                        chunk_file.unlink()
                        current_total -= sz
                        deleted_files.append(str(chunk_file))
                        logger.info(
                            "Deleted acked chunk %s in cycle %s (freed %d bytes)",
                            chunk_name,
                            curr_m.cycle_id,
                            sz,
                        )
                    except OSError as exc:
                        logger.warning("Failed to delete chunk %s: %s", chunk_file, exc)
                    if current_total <= max_bytes:
                        break

        if current_total <= max_bytes:
            break

        # 2. 清理衍生檔案（full.wav, lan_result.json, screenshot.*）
        # 僅在所有分段皆已 acked 時才可刪除衍生檔案
        all_chunks_acked = (
            len(curr_m.chunks) > 0
            and all(ck.get("acked") is True for ck in curr_m.chunks.values())
        )
        if all_chunks_acked:
            for deriv_name in ("full.wav", "lan_result.json"):
                deriv_file = c_dir / deriv_name
                if deriv_file.is_file():
                    sz = deriv_file.stat().st_size
                    try:
                        deriv_file.unlink()
                        current_total -= sz
                        deleted_files.append(str(deriv_file))
                        logger.info(
                            "Deleted derivative %s in cycle %s (freed %d bytes)",
                            deriv_name,
                            curr_m.cycle_id,
                            sz,
                        )
                    except OSError as exc:
                        logger.warning("Failed to delete %s: %s", deriv_file, exc)
                    if current_total <= max_bytes:
                        break

            if current_total <= max_bytes:
                break

            for shot_file in c_dir.glob("screenshot.*"):
                if shot_file.is_file():
                    sz = shot_file.stat().st_size
                    try:
                        shot_file.unlink()
                        current_total -= sz
                        deleted_files.append(str(shot_file))
                        logger.info(
                            "Deleted screenshot %s in cycle %s (freed %d bytes)",
                            shot_file.name,
                            curr_m.cycle_id,
                            sz,
                        )
                    except OSError as exc:
                        logger.warning("Failed to delete %s: %s", shot_file, exc)
                    if current_total <= max_bytes:
                        break

        if current_total <= max_bytes:
            break

    # manifest.json 永不刪除
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
