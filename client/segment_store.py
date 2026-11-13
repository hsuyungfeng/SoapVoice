"""Phase 31: SoapVoice 分段音訊帳本 (SegmentStore & CycleManifest).

(D-31-20, D-31-30, D-31-31, D-31-32, D-31-33)
管理 cycles/{cycle_id}/ 下的分段 metadata 與 manifest.json：
- 記錄每段 seq、sha256、size、acked 與 server_sha256
- 嚴格比對 server 回傳 sha256 方標記 acked (D-31-30)
- 原子寫入 (tmp + fsync + os.replace)
- threading.Lock 保護執行緒安全
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CycleManifest:
    cycle_id: str
    created_at: str = field(default_factory=_utc_now_iso)
    chunks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    total_chunks: Optional[int] = None
    finalized: bool = False
    generation_done: bool = False
    draft_submitted: bool = False
    draft_id: Optional[str] = None
    archived: bool = False
    archived_at: Optional[str] = None
    last_error: Optional[str] = None
    extras_missing: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CycleManifest:
        return cls(
            cycle_id=data.get("cycle_id", ""),
            created_at=data.get("created_at", _utc_now_iso()),
            chunks=data.get("chunks", {}),
            total_chunks=data.get("total_chunks"),
            finalized=bool(data.get("finalized", False)),
            generation_done=bool(data.get("generation_done", False)),
            draft_submitted=bool(data.get("draft_submitted", False)),
            draft_id=data.get("draft_id"),
            archived=bool(data.get("archived", False)),
            archived_at=data.get("archived_at"),
            last_error=data.get("last_error"),
            extras_missing=list(data.get("extras_missing", [])),
            context=data.get("context", {}),
        )


class SegmentStore:
    """管理 cycles/ 目錄下所有循環之 manifest 與檔案帳本。"""

    def __init__(self, cycles_root: Union[str, Path]):
        self.cycles_root = Path(cycles_root)
        self.cycles_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _cycle_dir(self, cycle_id: str) -> Path:
        return self.cycles_root / cycle_id

    def _manifest_path(self, cycle_id: str) -> Path:
        return self._cycle_dir(cycle_id) / "manifest.json"

    def _save_manifest_unlocked(self, manifest: CycleManifest) -> None:
        c_dir = self._cycle_dir(manifest.cycle_id)
        c_dir.mkdir(parents=True, exist_ok=True)
        target = self._manifest_path(manifest.cycle_id)
        tmp = c_dir / "manifest.json.tmp"

        payload = json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp, target)

    def open_cycle(self, cycle_id: str) -> Path:
        """建立 cycle 目錄與初始 manifest.json（若尚不存在）。"""
        with self._lock:
            c_dir = self._cycle_dir(cycle_id)
            c_dir.mkdir(parents=True, exist_ok=True)
            m_path = self._manifest_path(cycle_id)
            if not m_path.exists():
                manifest = CycleManifest(cycle_id=cycle_id)
                self._save_manifest_unlocked(manifest)
            return c_dir

    def load(self, cycle_id: str) -> Optional[CycleManifest]:
        """載入特定 cycle 之 manifest。若不存在或損壞回傳 None。"""
        with self._lock:
            m_path = self._manifest_path(cycle_id)
            if not m_path.exists():
                return None
            try:
                data = json.loads(m_path.read_text(encoding="utf-8"))
                return CycleManifest.from_dict(data)
            except Exception as exc:
                logger.warning("Failed to load manifest for %s: %s", cycle_id, exc)
                return None

    def register_chunk(self, cycle_id: str, seq: int, path: Union[str, Path]) -> str:
        """計算 chunk 檔案之 sha256 與大小並記錄於 manifest。回傳本機 sha256。"""
        chunk_path = Path(path)
        content = chunk_path.read_bytes()
        sha256_val = hashlib.sha256(content).hexdigest()
        size_val = len(content)

        with self._lock:
            m = self.load(cycle_id) or CycleManifest(cycle_id=cycle_id)
            seq_key = str(seq)
            prev = m.chunks.get(seq_key, {})
            m.chunks[seq_key] = {
                "seq": seq,
                "sha256": sha256_val,
                "size": size_val,
                "path": str(chunk_path.name),
                "acked": prev.get("acked", False),
                "server_sha256": prev.get("server_sha256"),
                "acked_at": prev.get("acked_at"),
            }
            self._save_manifest_unlocked(m)

        return sha256_val

    def mark_acked(self, cycle_id: str, seq: int, server_sha256: str) -> bool:
        """驗證 server 回傳之 sha256 是否與本機一致。

        一致才標記 acked=True 並存檔；不一致回傳 False 且不改狀態 (D-31-30)。
        """
        with self._lock:
            m = self.load(cycle_id)
            if not m:
                return False
            seq_key = str(seq)
            chunk = m.chunks.get(seq_key)
            if not chunk:
                return False

            local_sha = chunk.get("sha256")
            if local_sha != server_sha256:
                logger.warning(
                    "SHA256 mismatch for %s chunk %d: local=%s, server=%s",
                    cycle_id,
                    seq,
                    local_sha,
                    server_sha256,
                )
                return False

            chunk["acked"] = True
            chunk["server_sha256"] = server_sha256
            chunk["acked_at"] = _utc_now_iso()
            self._save_manifest_unlocked(m)
            return True

    def pending_chunks(self, cycle_id: str) -> List[int]:
        """回傳尚未 acked 之分段 seq 清單（升冪排序）。"""
        with self._lock:
            m = self.load(cycle_id)
            if not m:
                return []
            res: List[int] = []
            for seq_str, chunk in m.chunks.items():
                if not chunk.get("acked", False):
                    try:
                        res.append(int(seq_str))
                    except ValueError:
                        pass
            return sorted(res)

    def reset_ack(self, cycle_id: str, seqs: List[int]) -> None:
        """重設指定分段之 acked 狀態為 False（供重傳補漏使用）。"""
        with self._lock:
            m = self.load(cycle_id)
            if not m:
                return
            for seq in seqs:
                seq_key = str(seq)
                if seq_key in m.chunks:
                    m.chunks[seq_key]["acked"] = False
                    m.chunks[seq_key]["server_sha256"] = None
                    m.chunks[seq_key]["acked_at"] = None
            self._save_manifest_unlocked(m)

    def set_context(self, cycle_id: str, context: Dict[str, Any]) -> None:
        """記錄病人/醫師等上下文於本機 manifest。"""
        with self._lock:
            m = self.load(cycle_id) or CycleManifest(cycle_id=cycle_id)
            m.context = dict(context)
            self._save_manifest_unlocked(m)

    def get_context(self, cycle_id: str) -> Dict[str, Any]:
        """讀取本機 manifest 之上下文資訊。"""
        m = self.load(cycle_id)
        return dict(m.context) if m else {}

    def set_total(self, cycle_id: str, total: int) -> None:
        with self._lock:
            m = self.load(cycle_id) or CycleManifest(cycle_id=cycle_id)
            m.total_chunks = total
            self._save_manifest_unlocked(m)

    def mark_finalized(self, cycle_id: str) -> None:
        with self._lock:
            m = self.load(cycle_id) or CycleManifest(cycle_id=cycle_id)
            m.finalized = True
            self._save_manifest_unlocked(m)

    def mark_generation_done(self, cycle_id: str) -> None:
        with self._lock:
            m = self.load(cycle_id) or CycleManifest(cycle_id=cycle_id)
            m.generation_done = True
            self._save_manifest_unlocked(m)

    def mark_draft_submitted(self, cycle_id: str, draft_id: str) -> None:
        with self._lock:
            m = self.load(cycle_id) or CycleManifest(cycle_id=cycle_id)
            m.draft_submitted = True
            m.draft_id = draft_id
            self._save_manifest_unlocked(m)

    def mark_archived(self, cycle_id: str) -> None:
        with self._lock:
            m = self.load(cycle_id) or CycleManifest(cycle_id=cycle_id)
            m.archived = True
            m.archived_at = _utc_now_iso()
            self._save_manifest_unlocked(m)

    def set_error(self, cycle_id: str, msg: str) -> None:
        with self._lock:
            m = self.load(cycle_id) or CycleManifest(cycle_id=cycle_id)
            m.last_error = msg
            self._save_manifest_unlocked(m)

    def list_cycles(self) -> List[CycleManifest]:
        """列出所有循環 manifest，依 created_at 排序。"""
        with self._lock:
            res: List[CycleManifest] = []
            if not self.cycles_root.exists():
                return res
            for child in self.cycles_root.iterdir():
                if child.is_dir():
                    m_file = child / "manifest.json"
                    if m_file.is_file():
                        try:
                            data = json.loads(m_file.read_text(encoding="utf-8"))
                            res.append(CycleManifest.from_dict(data))
                        except Exception:
                            continue
            res.sort(key=lambda x: x.created_at)
            return res

    def unfinished_cycles(self) -> List[CycleManifest]:
        """列出尚未封存 (archived == False) 之循環。"""
        return [c for c in self.list_cycles() if not c.archived]
