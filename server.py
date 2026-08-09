import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import ai_writer
import config
import merge as merge_mod
import sender

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(BASE_DIR, "test.html")
DRAFT_PATH = os.path.join(BASE_DIR, "draft.json")

HOST = os.getenv("HOST", "0.0.0.0" if os.getenv("PORT") else "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))


def _read_body(handler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    if not length:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def _json(handler, payload: dict, status: int = 200) -> None:
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _save_draft(payload: dict) -> None:
    try:
        with open(DRAFT_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
    except OSError:
        pass


class Handler(BaseHTTPRequestHandler):
    def _serve_file(self, path: str) -> None:
        try:
            with open(path, "rb") as handle:
                body = handle.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            self.send_error(404)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/test.html"):
            self._serve_file(HTML_PATH)
        elif path == "/api/status":
            _json(
                self,
                {
                    "ai_online": bool(config.GROQ_API_KEY),
                    "model": config.GROQ_MODEL,
                },
            )
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = _read_body(self)
        settings = body.get("settings") or {}
        api_key = (settings.get("groqApiKey") or config.GROQ_API_KEY).strip() or None
        model = (settings.get("model") or config.GROQ_MODEL).strip()
        base_url = (settings.get("baseUrl") or config.GROQ_BASE_URL).strip()
        gmail_user = (settings.get("gmailUser") or config.GMAIL_USER).strip()
        gmail_password = (settings.get("gmailPassword") or config.GMAIL_APP_PASSWORD).strip()
        sender_name = (settings.get("senderName") or config.SENDER_NAME).strip()
        try:
            if path == "/api/columns":
                headers = body["headers"]
                sample = [dict(zip(headers, row)) for row in body.get("sample", [])]
                mapping = ai_writer.map_columns(headers, sample, api_key=api_key, base_url=base_url, model=model)
                _json(self, {"mapping": mapping})

            elif path == "/api/draft":
                mapping = {key: (value or None) for key, value in body.get("mapping", {}).items()}
                draft = ai_writer.write_email(
                    body["description"],
                    body["campaign"],
                    mapping,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                )
                _save_draft(
                    {
                        "campaign": body.get("campaign"),
                        "description": body.get("description"),
                        "subject": draft["subject"],
                        "body": draft["body"],
                    }
                )
                _json(self, draft)

            elif path == "/api/preview":
                messages = merge_mod.build_messages_from_grid(
                    body["headers"],
                    body["rows"],
                    body["mapping"],
                    body["campaign"],
                    body["subject"],
                    body["body"],
                    cc_parents=bool(body.get("cc_parents") or body.get("ccParents")),
                )
                _json(self, {"messages": messages, "count": len(messages)})

            elif path == "/api/send":
                if body.get("dry_run"):
                    _json(self, {"dry_run": True, "count": len(body.get("messages", [])), "sent": [], "failed": []})
                else:
                    sent, failed = sender.send_emails(
                        body["messages"],
                        gmail_user=gmail_user,
                        gmail_password=gmail_password,
                        sender_name=sender_name,
                    )
                    _json(self, {"dry_run": False, "sent": sent, "failed": failed})

            else:
                self.send_error(404)
        except SystemExit as exc:
            _json(self, {"error": str(exc)}, status=400)
        except Exception as exc:
            _json(self, {"error": str(exc)}, status=500)

    def log_message(self, format, *args) -> None:
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Mail merge server on http://{HOST}:{PORT}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
