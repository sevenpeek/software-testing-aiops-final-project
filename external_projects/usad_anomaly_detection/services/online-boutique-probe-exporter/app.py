from __future__ import annotations

import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


TARGET_URL = os.getenv("TARGET_URL", "http://frontend.online-boutique.svc.cluster.local/")
INTERVAL_SECONDS = float(os.getenv("INTERVAL_SECONDS", "5"))

lock = threading.Lock()
stats = {
    "requests_total": 0,
    "success_total": 0,
    "error_total": 0,
    "latency_ms": 0.0,
    "last_status_code": 0,
    "last_response_bytes": 0,
    "last_success": 0,
}


def probe_loop() -> None:
    while True:
        start = time.perf_counter()
        status_code = 0
        response_bytes = 0
        success = 0
        try:
            req = urllib.request.Request(TARGET_URL, headers={"User-Agent": "online-boutique-probe-exporter/1.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                body = resp.read()
                status_code = resp.getcode()
                response_bytes = len(body)
                success = 1 if 200 <= status_code < 400 else 0
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            try:
                response_bytes = len(exc.read())
            except Exception:
                response_bytes = 0
        except Exception:
            status_code = 0

        latency_ms = (time.perf_counter() - start) * 1000
        with lock:
            stats["requests_total"] += 1
            stats["success_total"] += success
            stats["error_total"] += 0 if success else 1
            stats["latency_ms"] = latency_ms
            stats["last_status_code"] = status_code
            stats["last_response_bytes"] = response_bytes
            stats["last_success"] = success

        time.sleep(INTERVAL_SECONDS)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_text("ok\n")
            return
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return

        with lock:
            snapshot = dict(stats)
        lines = [
            "# HELP online_boutique_probe_requests_total Total HTTP probes to Online Boutique frontend.",
            "# TYPE online_boutique_probe_requests_total counter",
            f"online_boutique_probe_requests_total {snapshot['requests_total']}",
            "# HELP online_boutique_probe_success_total Successful HTTP probes.",
            "# TYPE online_boutique_probe_success_total counter",
            f"online_boutique_probe_success_total {snapshot['success_total']}",
            "# HELP online_boutique_probe_error_total Failed HTTP probes.",
            "# TYPE online_boutique_probe_error_total counter",
            f"online_boutique_probe_error_total {snapshot['error_total']}",
            "# HELP online_boutique_probe_latency_ms Last frontend probe latency in milliseconds.",
            "# TYPE online_boutique_probe_latency_ms gauge",
            f"online_boutique_probe_latency_ms {snapshot['latency_ms']:.3f}",
            "# HELP online_boutique_probe_last_status_code Last frontend HTTP status code.",
            "# TYPE online_boutique_probe_last_status_code gauge",
            f"online_boutique_probe_last_status_code {snapshot['last_status_code']}",
            "# HELP online_boutique_probe_last_response_bytes Last frontend response size in bytes.",
            "# TYPE online_boutique_probe_last_response_bytes gauge",
            f"online_boutique_probe_last_response_bytes {snapshot['last_response_bytes']}",
            "# HELP online_boutique_probe_last_success Last frontend probe success flag.",
            "# TYPE online_boutique_probe_last_success gauge",
            f"online_boutique_probe_last_success {snapshot['last_success']}",
            "",
        ]
        self._send_text("\n".join(lines))

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_text(self, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    threading.Thread(target=probe_loop, daemon=True).start()
    port = int(os.getenv("PORT", "9105"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
