"""SoapVoice 本機控制伺服器 (Phase 31 契約 §1, D-31-03, T-31-57 ~ T-31-62).

職責：
1. 僅綁定 127.0.0.1 / localhost，非 loopback 拒絕啟動 (T-31-57)。
2. 驗證 Host 標頭防止 DNS rebinding 跨站攻擊 (T-31-58)。
3. 使用 X-Local-Token 進行 hmac.compare_digest 安全比對 (T-31-61)。
4. 限制請求 body 大小 ≤ 4 KB (413)。
5. 提供 /control/v1/status、start、stop、archived 端點。
6. 安全日誌：絕不記錄 Token、請求 body 或病人資訊。
"""

from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import re
import secrets
import threading
from typing import Any, Dict, Optional, Union

from client.cycle_session import CycleSession, CycleSessionError

logger = logging.getLogger("control_server")

_ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
_MAX_BODY_SIZE = 4096
_HEX32_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def default_control_token_path() -> Path:
    """預設本機控制 token 路徑（契約 §1）。"""
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        return Path(localappdata) / "ElcSoapVoice" / "control_token"
    return Path(os.path.expanduser("~")) / ".local" / "share" / "ElcSoapVoice" / "control_token"


def ensure_token(token_path: Path) -> str:
    """讀取或建立本機控制 token（長度 ≥ 43，POSIX 下權限 0o600）。"""
    token_path = Path(token_path)
    if token_path.is_file():
        try:
            existing = token_path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        except Exception as exc:
            logger.warning("讀取現有 token 檔失敗: %s", exc)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    new_token = secrets.token_urlsafe(32)
    token_path.write_text(new_token, encoding="utf-8")
    if os.name == "posix":
        try:
            token_path.chmod(0o600)
        except OSError:
            pass
    return new_token


class ControlRequestHandler(BaseHTTPRequestHandler):
    """處理 /control/v1/* 的 HTTP 請求。"""

    server: "ControlServer"

    def log_message(self, format: str, *args: Any) -> None:
        """安全存取日誌：僅記錄方法、路徑與狀態碼，絕不洩漏 Token、Body 或病歷。"""
        if args and len(args) >= 2:
            logger.info("IPC %s %s -> %s", self.command, self.path, args[1])
        else:
            logger.info("IPC %s %s", self.command, self.path)

    def _send_json(self, status: int, data: Dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, error_code: str, message: str) -> None:
        self._send_json(status, {"error": error_code, "message": message})

    def _verify_security(self) -> bool:
        """驗證 Content-Length、Host 標頭與 X-Local-Token。"""
        # 1. 內文大小限制
        content_length_str = self.headers.get("Content-Length")
        if content_length_str:
            try:
                cl = int(content_length_str)
                if cl > _MAX_BODY_SIZE:
                    self._send_error(413, "payload_too_large", "請求主體超過 4KB 上限")
                    return False
            except ValueError:
                self._send_error(400, "invalid_header", "Content-Length 格式不正確")
                return False

        # 2. Host 標頭檢查（防 DNS rebinding）
        host_hdr = self.headers.get("Host", "").strip().lower()
        if not host_hdr:
            self._send_error(400, "invalid_host", "缺少 Host 標頭")
            return False

        host_name = host_hdr.split(":")[0]
        if host_name not in _ALLOWED_HOSTS:
            self._send_error(400, "invalid_host", f"Host 標頭不允許：{host_hdr}")
            return False

        # 3. X-Local-Token 認證
        req_token = self.headers.get("X-Local-Token", "")
        if not req_token or not hmac.compare_digest(req_token, self.server.token):
            self._send_error(401, "unauthorized", "X-Local-Token 認證失敗或缺少標頭")
            return False

        return True

    def _read_json_body(self) -> Optional[Dict[str, Any]]:
        cl_str = self.headers.get("Content-Length", "0")
        try:
            cl = int(cl_str)
        except ValueError:
            cl = 0

        if cl <= 0:
            return {}

        raw = self.rfile.read(cl)
        try:
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                self._send_error(422, "invalid_json", "請求內容必須為 JSON 物件")
                return None
            return parsed
        except Exception:
            self._send_error(422, "invalid_json", "JSON 解析失敗")
            return None

    def do_GET(self) -> None:
        if not self._verify_security():
            return

        if self.path == "/control/v1/status":
            try:
                st = self.server.session.status()
                self._send_json(200, st)
            except Exception as exc:
                logger.exception("status endpoint error: %s", exc)
                self._send_error(500, "internal_error", str(exc))
        else:
            self._send_error(404, "not_found", "端點不存在")

    def do_POST(self) -> None:
        if not self._verify_security():
            return

        body = self._read_json_body()
        if body is None:
            return

        session = self.server.session

        if self.path == "/control/v1/start":
            cmd_id = str(body.get("command_id") or "")
            c_id = str(body.get("cycle_id") or "")
            if not _HEX32_RE.match(cmd_id) or not _HEX32_RE.match(c_id):
                self._send_error(422, "invalid_field", "command_id 與 cycle_id 必須為 32 位 hex")
                return
            try:
                res = session.start(cmd_id, c_id)
                self._send_json(200, res)
            except CycleSessionError as exc:
                self._send_json(exc.status, exc.to_dict())
            except Exception as exc:
                logger.exception("start error: %s", exc)
                self._send_error(500, "internal_error", str(exc))

        elif self.path == "/control/v1/stop":
            cmd_id = str(body.get("command_id") or "")
            c_id = str(body.get("cycle_id") or "")
            if not _HEX32_RE.match(cmd_id) or not _HEX32_RE.match(c_id):
                self._send_error(422, "invalid_field", "command_id 與 cycle_id 必須為 32 位 hex")
                return
            try:
                res = session.stop(cmd_id, c_id)
                self._send_json(200, res)
            except CycleSessionError as exc:
                self._send_json(exc.status, exc.to_dict())
            except Exception as exc:
                logger.exception("stop error: %s", exc)
                self._send_error(500, "internal_error", str(exc))

        elif self.path == "/control/v1/archived":
            c_id = str(body.get("cycle_id") or "")
            if not _HEX32_RE.match(c_id):
                self._send_error(422, "invalid_field", "cycle_id 必須為 32 位 hex")
                return
            try:
                res = session.archived(c_id)
                self._send_json(200, res)
            except CycleSessionError as exc:
                self._send_json(exc.status, exc.to_dict())
            except Exception as exc:
                logger.exception("archived error: %s", exc)
                self._send_error(500, "internal_error", str(exc))

        else:
            self._send_error(404, "not_found", "端點不存在")


class ControlServer(ThreadingHTTPServer):
    """SoapVoice 本機控制伺服器。"""

    def __init__(
        self,
        session: CycleSession,
        port: int = 18765,
        host: str = "127.0.0.1",
        token_path: Optional[Union[str, Path]] = None,
        token: Optional[str] = None,
    ):
        h = host.strip().lower()
        if h not in _ALLOWED_HOSTS:
            raise ValueError(f"control_host 必須為 loopback (127.0.0.1 或 localhost)，不允許：{host!r}")

        self.session = session
        self.control_host = h
        self.control_port = int(port)

        t_path = Path(token_path) if token_path else default_control_token_path()
        self.token = token.strip() if token is not None else ensure_token(t_path)
        self.token_path = t_path

        super().__init__((self.control_host, self.control_port), ControlRequestHandler)
        self._thread: Optional[threading.Thread] = None

    @property
    def bound_port(self) -> int:
        return self.server_port

    def start(self) -> None:
        """在背景 daemon 執行緒啟動 HTTP 服務。"""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self.serve_forever, daemon=True, name="control-server")
        self._thread.start()
        logger.info("ControlServer started on http://%s:%d", self.control_host, self.bound_port)

    def stop(self) -> None:
        """停止伺服器並關閉 socket。"""
        try:
            self.shutdown()
        except Exception:
            pass
        try:
            self.server_close()
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        logger.info("ControlServer stopped")
