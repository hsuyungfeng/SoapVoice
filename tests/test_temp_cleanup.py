"""Tests for temp_cleanup.enforce_cap and LocalStorageManager no-drop rule (Phase 31 Task 2)."""

from pathlib import Path
import pytest

from client.local_storage import LocalStorageManager
from client.segment_store import SegmentStore
from client.temp_cleanup import enforce_cap


def _setup_cycle(store: SegmentStore, cycle_id: str, chunk_sizes: list[int], acked_map: dict[int, bool], archived: bool, archived_at: str | None = None):
    c_dir = store.open_cycle(cycle_id)
    for seq, size in enumerate(chunk_sizes):
        f = c_dir / f"chunk_{seq:06d}.wav"
        f.write_bytes(b"x" * size)
        sha = store.register_chunk(cycle_id, seq, f)
        if acked_map.get(seq, False):
            store.mark_acked(cycle_id, seq, sha)
    if archived:
        store.mark_archived(cycle_id)
        if archived_at:
            m = store.load(cycle_id)
            m.archived_at = archived_at
            store._save_manifest_unlocked(m)
    return c_dir


def test_no_deletion_when_under_cap(tmp_path):
    """Test 1: 總量未超過上限 → 不刪任何檔案。"""
    store = SegmentStore(tmp_path)
    _setup_cycle(store, "c1", [100, 200], {0: True, 1: True}, archived=True)

    res = enforce_cap(store, max_bytes=5000)
    assert len(res["deleted_files"]) == 0
    assert res["skipped_reason"] is None
    assert (tmp_path / "c1" / "chunk_000000.wav").exists()
    assert (tmp_path / "c1" / "chunk_000001.wav").exists()


def test_no_deletion_when_only_unarchived(tmp_path):
    """Test 2: 超過上限、只有未封存循環 → 不刪任何檔案 (D-31-33)。"""
    store = SegmentStore(tmp_path)
    _setup_cycle(store, "c_unarchived", [1000, 2000], {0: True, 1: True}, archived=False)

    res = enforce_cap(store, max_bytes=500)
    assert len(res["deleted_files"]) == 0
    assert res["skipped_reason"] == "no_archived_cycles"
    assert (tmp_path / "c_unarchived" / "chunk_000000.wav").exists()
    assert (tmp_path / "c_unarchived" / "chunk_000001.wav").exists()


def test_partial_acked_cycle_deletion(tmp_path):
    """Test 3: 超過上限、已封存但含一段未 acked → 只刪已 acked 段，未 acked 段保留，衍生檔 full.wav 保留。"""
    store = SegmentStore(tmp_path)
    c_dir = _setup_cycle(store, "c_mixed", [500, 500], {0: True, 1: False}, archived=True)
    full_wav = c_dir / "full.wav"
    full_wav.write_bytes(b"f" * 300)

    # 總量約 1300+ bytes，設上限 600
    res = enforce_cap(store, max_bytes=600)

    # chunk 0 已 acked 應被刪除
    assert not (c_dir / "chunk_000000.wav").exists()
    # chunk 1 未 acked 嚴禁刪除 (D-31-30, D-31-32)
    assert (c_dir / "chunk_000001.wav").exists()
    # 因並非全部分段皆 acked，full.wav 必須保留
    assert full_wav.exists()


def test_oldest_archived_cycle_cleaned_first(tmp_path):
    """Test 4: 兩個已封存循環 → 先刪 archived_at 較早者，刪到低於上限即停，較新者保留。"""
    store = SegmentStore(tmp_path)
    # 較舊循環 (各 1000 bytes)
    c1_dir = _setup_cycle(store, "c_old", [1000, 1000], {0: True, 1: True}, archived=True, archived_at="2026-01-01T00:00:00Z")
    # 較新循環 (各 1000 bytes)
    c2_dir = _setup_cycle(store, "c_new", [1000, 1000], {0: True, 1: True}, archived=True, archived_at="2026-01-02T00:00:00Z")

    # 兩者合計約 5980+ bytes，設上限 4200 (刪除 c_old 兩分段後約 3980 <= 4200 停止)
    res = enforce_cap(store, max_bytes=4200)

    # c_old 的 chunk 0 與 1 被刪
    assert not (c1_dir / "chunk_000000.wav").exists()
    assert not (c1_dir / "chunk_000001.wav").exists()

    # c_new 完全未被觸及保留
    assert (c2_dir / "chunk_000000.wav").exists()
    assert (c2_dir / "chunk_000001.wav").exists()


def test_manifest_never_deleted(tmp_path):
    """Test 5: manifest.json 永不刪除。"""
    store = SegmentStore(tmp_path)
    c_dir = _setup_cycle(store, "c_manifest_test", [1000], {0: True}, archived=True)

    manifest_file = c_dir / "manifest.json"
    assert manifest_file.exists()

    # 設極低上限 1 byte 強制清理
    enforce_cap(store, max_bytes=1)

    assert not (c_dir / "chunk_000000.wav").exists()
    assert manifest_file.exists()
    assert manifest_file.stat().st_size > 0


def test_local_storage_no_drop_on_max_pending(tmp_path):
    """Test 6: LocalStorageManager 佇列達 max_pending 時仍加入新項目，不移除舊項目 (D-31-32)。"""
    cache_dir = tmp_path / "ls_cache"
    mgr = LocalStorageManager(str(cache_dir), max_pending=2)

    # 建立 3 個假音訊檔
    for i in range(3):
        a = tmp_path / f"audio_{i}.wav"
        a.write_bytes(b"wav")
        s = tmp_path / f"shot_{i}.jpg"
        s.write_bytes(b"jpg")
        ok = mgr.add_pending(f"sess_{i}", str(a), str(s), f"Pat_{i}", "Doc")
        assert ok is True

    # 佇列長度應為 3 (超過 max_pending=2 仍全部保留)
    assert mgr.get_queue_size() == 3
    all_sess = [p.session_id for p in mgr.get_all_pending()]
    assert all_sess == ["sess_0", "sess_1", "sess_2"]
