import json
import threading
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Self

from src.utils.crypto import verify_signature


class _WebhookHandler(BaseHTTPRequestHandler):
    """HTTP request handler for receiving webhooks."""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        server_config = self.server.config  # type: ignore[attr-defined]

        # Simulate slow response
        if server_config["response_delay"] > 0:
            import time
            time.sleep(server_config["response_delay"])

        # Parse payload
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "invalid JSON"}).encode())
            return

        # Validate required fields
        required_fields = ["payment_id", "event_type", "amount", "currency", "timestamp", "status"]
        missing = [f for f in required_fields if f not in payload]
        if missing:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"missing fields: {missing}"}).encode())
            return

        # Validate amount is numeric
        try:
            float(payload["amount"])
        except (ValueError, TypeError):
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "invalid amount"}).encode())
            return

        # Signature verification
        if server_config["signature_secret"]:
            sig = self.headers.get("X-Webhook-Signature", "")
            if not sig:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "missing signature"}).encode())
                return
            if not verify_signature(payload, server_config["signature_secret"], sig):
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "invalid signature"}).encode())
                return

        # Idempotency check
        event_id = self.headers.get("X-Event-ID", "")
        if server_config["idempotency_enabled"] and event_id:
            with server_config["lock"]:
                if event_id in server_config["processed_event_ids"]:
                    # Return success but don't process again
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "already_processed"}).encode())
                    return

        # Record the event
        with server_config["lock"]:
            server_config["received_events"].append({
                "event_id": event_id,
                "payload": payload,
                "headers": dict(self.headers),
            })
            if event_id:
                server_config["processed_event_ids"].add(event_id)

        code = server_config["response_code"]
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if 200 <= code < 300:
            self.wfile.write(json.dumps({"status": "ok"}).encode())

    def log_message(self, format, *args):
        """Suppress default request logging."""
        pass


class MerchantWebhookServer:
    """Configurable HTTP server that simulates a merchant webhook receiver."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0, secret: str | None = None):
        self._host = host
        self._port = port
        self._config = {
            "response_code": 200,
            "response_delay": 0,
            "signature_secret": secret,
            "idempotency_enabled": False,
            "received_events": [],
            "processed_event_ids": set(),
            "lock": threading.Lock(),
        }
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def set_response_code(self, code: int) -> Self:
        self._config["response_code"] = code
        return self

    def set_response_delay(self, seconds: float) -> Self:
        self._config["response_delay"] = seconds
        return self

    def enable_signature_verification(self, secret: str) -> Self:
        self._config["signature_secret"] = secret
        return self

    def enable_idempotency(self) -> Self:
        self._config["idempotency_enabled"] = True
        return self

    def start(self) -> None:
        self._server = ThreadingHTTPServer((self._host, self._port), _WebhookHandler)
        self._server.config = self._config  # type: ignore[attr-defined]
        # Get the actual port (useful when port=0)
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}/webhook"

    @property
    def port(self) -> int:
        return self._port

    def get_received_events(self) -> list[dict]:
        with self._config["lock"]:
            return list(self._config["received_events"])

    def get_processed_count(self) -> int:
        with self._config["lock"]:
            return len(self._config["received_events"])

    def was_event_processed(self, event_id: str) -> bool:
        with self._config["lock"]:
            return event_id in self._config["processed_event_ids"]

    def clear_events(self) -> None:
        with self._config["lock"]:
            self._config["received_events"].clear()
            self._config["processed_event_ids"].clear()
