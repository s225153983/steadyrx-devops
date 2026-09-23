"""Team alert receiver.

Stands in for a chat or paging tool. Alertmanager and Jenkins POST alerts to
/alert. The receiver logs each one and keeps the latest 200 so the team (and
the Jenkins Monitoring stage) can read them at /alerts or view them at /.
"""

import html
import json
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EVENTS = deque(maxlen=200)


def _flatten(payload):
    """Turn an Alertmanager webhook payload into one event per alert."""
    now = datetime.now(timezone.utc).isoformat()
    alerts = payload.get("alerts") or [payload]
    for alert in alerts:
        labels = alert.get("labels", {})
        notes = alert.get("annotations", {})
        yield {
            "received_at": now,
            "status": alert.get("status", payload.get("status", "firing")),
            "alertname": labels.get("alertname", payload.get("alertname", "unknown")),
            "severity": labels.get("severity", payload.get("severity", "info")),
            "team": labels.get("team", payload.get("team", "steadyrx")),
            "summary": notes.get("summary", payload.get("summary", "")),
            "description": notes.get("description", payload.get("description", "")),
        }


class Handler(BaseHTTPRequestHandler):
    """Minimal JSON and HTML endpoints."""

    def _send(self, code, body, ctype="application/json"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):  # noqa: N802
        if self.path != "/alert":
            self._send(404, '{"error": "not found"}')
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, '{"error": "invalid json"}')
            return
        for event in _flatten(payload):
            EVENTS.appendleft(event)
            print(f"[{event['status'].upper()}] {event['severity']} "
                  f"{event['alertname']}: {event['summary']}", flush=True)
        self._send(200, '{"ok": true}')

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/alerts"):
            self._send(200, json.dumps(list(EVENTS)))
        elif self.path == "/health":
            self._send(200, '{"status": "ok"}')
        elif self.path == "/":
            rows = "".join(
                f"<tr class='{html.escape(e['status'])}'><td>{html.escape(e['received_at'][:19])}</td>"
                f"<td>{html.escape(e['status'])}</td><td>{html.escape(e['severity'])}</td>"
                f"<td>{html.escape(e['alertname'])}</td><td>{html.escape(e['summary'])}</td></tr>"
                for e in EVENTS)
            page = ("<html><head><title>SteadyRx team alerts</title><meta http-equiv='refresh' content='5'>"
                    "<style>body{font-family:sans-serif;margin:2em}td,th{padding:6px 10px;border-bottom:1px solid #ddd}"
                    ".firing{background:#fde2e1}.resolved{background:#e3f6e5}</style></head><body>"
                    "<h1>SteadyRx team alert channel</h1><table><tr><th>Received (UTC)</th><th>Status</th>"
                    f"<th>Severity</th><th>Alert</th><th>Summary</th></tr>{rows}</table></body></html>")
            self._send(200, page, "text/html")
        else:
            self._send(404, '{"error": "not found"}')

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9095), Handler).serve_forever()  # nosec B104
