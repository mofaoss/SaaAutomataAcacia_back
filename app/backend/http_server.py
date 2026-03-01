import json
import logging
import queue
import threading
import time
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

from app.backend.application import BackendApplication


class LogHub(logging.Handler):
    def __init__(self, history_size: int = 500):
        super().__init__()
        self.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"))
        self._history = deque(maxlen=history_size)
        self._subscribers: List[queue.Queue] = []
        self._lock = threading.Lock()

    def emit(self, record):
        line = self.format(record)
        with self._lock:
            self._history.append(line)
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(line)
            except Exception:
                pass

    def subscribe(self) -> queue.Queue:
        q = queue.Queue(maxsize=200)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def history(self, limit: int = 200) -> List[str]:
        with self._lock:
            return list(self._history)[-limit:]


class BackendHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass, app_service: BackendApplication):
        super().__init__(server_address, RequestHandlerClass)
        self.app = app_service


class BackendRequestHandler(BaseHTTPRequestHandler):
    server: BackendHTTPServer

    def _set_headers(self, status=HTTPStatus.OK, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _read_json(self) -> Dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, payload: Dict, status=HTTPStatus.OK):
        self._set_headers(status=status)
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        return

    def do_OPTIONS(self):
        self._set_headers(status=HTTPStatus.NO_CONTENT)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json(self.server.app.health())
            return

        if parsed.path == "/api/commands":
            self._send_json(self.server.app.list_commands())
            return

        if parsed.path == "/api/status":
            self._send_json(self.server.app.status())
            return

        if parsed.path == "/api/logs":
            params = parse_qs(parsed.query)
            limit = 200
            if "limit" in params:
                try:
                    limit = max(1, min(1000, int(params["limit"][0])))
                except Exception:
                    pass
            self._send_json(self.server.app.logs(limit=limit))
            return

        if parsed.path == "/api/logs/stream":
            self._stream_logs()
            return

        if parsed.path.startswith("/api/commands/"):
            command_name = unquote(parsed.path[len("/api/commands/"):])
            result = self.server.app.execute(command_name, payload={})
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            self._send_json(result, status=status)
            return

        self._send_json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/commands/"):
            command_name = unquote(parsed.path[len("/api/commands/"):])
            body = self._read_json()
            result = self.server.app.execute(command_name, payload=body)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            self._send_json(result, status=status)
            return

        if parsed.path == "/api/open-game":
            result = self.server.app.execute("game.open", payload={})
            if not result.get("ok"):
                self._send_json(result, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(result)
            return

        if parsed.path == "/api/start":
            body = self._read_json()
            result = self.server.app.execute("daily.start", payload=body)
            if not result.get("ok") and result.get("code") == "runner_busy":
                self._send_json(result, status=HTTPStatus.CONFLICT)
                return
            if not result.get("ok"):
                self._send_json(result, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(result)
            return

        if parsed.path == "/api/stop":
            body = self._read_json()
            result = self.server.app.execute("daily.stop", payload=body)
            if not result.get("ok") and result.get("code") == "runner_not_running":
                self._send_json(result, status=HTTPStatus.CONFLICT)
                return
            if not result.get("ok"):
                self._send_json(result, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(result)
            return

        self._send_json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def _stream_logs(self):
        self._set_headers(status=HTTPStatus.OK, content_type="text/event-stream; charset=utf-8")
        q = self.server.app.log_hub.subscribe()
        try:
            for line in self.server.app.log_hub.history(limit=300):
                payload = json.dumps({"log": line}, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
            self.wfile.flush()

            while True:
                try:
                    line = q.get(timeout=15)
                    payload = json.dumps({"log": line}, ensure_ascii=False)
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
                except Exception:
                    break
        finally:
            self.server.app.log_hub.unsubscribe(q)


def create_server(host: str, port: int, app_service: BackendApplication) -> BackendHTTPServer:
    return BackendHTTPServer((host, port), BackendRequestHandler, app_service)
