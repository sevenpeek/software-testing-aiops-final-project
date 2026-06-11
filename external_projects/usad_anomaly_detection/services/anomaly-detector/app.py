import argparse
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAST_SUMMARY: dict[str, str] = {}


def parse_summary(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" in line and not line.startswith("-"):
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def run_detection(payload: dict) -> dict:
    input_path = payload.get("input", "data/sample_kpi_metrics.csv")
    out_dir = payload.get("out", "outputs_service")
    window = str(payload.get("window", 12))
    epochs = str(payload.get("epochs", 180))
    command = [
        sys.executable,
        str(PROJECT_ROOT / "src" / "run_usad.py"),
        "--input",
        input_path,
        "--out",
        out_dir,
        "--window",
        window,
        "--epochs",
        epochs,
    ]
    proc = subprocess.run(command, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        return {"status": "error", "stdout": proc.stdout, "stderr": proc.stderr}
    summary = parse_summary(PROJECT_ROOT / out_dir / "metrics_summary.txt")
    LAST_SUMMARY.clear()
    LAST_SUMMARY.update(summary)
    return {"status": "ok", "summary": summary, "stdout": proc.stdout}


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"status": "ok", "service": "anomaly-detector"})
        elif self.path == "/summary":
            self._json(200, {"status": "ok", "summary": LAST_SUMMARY})
        else:
            self._json(404, {"status": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/detect":
            self._json(404, {"status": "not_found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._json(400, {"status": "bad_request", "error": str(exc)})
            return
        result = run_detection(payload)
        self._json(200 if result["status"] == "ok" else 500, result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8088)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"anomaly-detector listening on {args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
