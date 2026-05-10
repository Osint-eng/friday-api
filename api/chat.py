import json
import os
import datetime
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

FRIDAY_SYSTEM = (
    "You are Friday, the witty and loyal AI assistant from Iron Man. "
    "You address the user as 'Boss'. "
    "Be helpful, concise, slightly sarcastic, and always professional. "
    "Keep responses short — 1-3 sentences unless asked for detail. "
    "No markdown, no asterisks — plain text only."
)

def build_system():
    now = datetime.datetime.now().strftime("%B %d, %Y — %I:%M %p")
    return f"{FRIDAY_SYSTEM} Current date & time: {now}"

def call_claude(messages):
    if not ANTHROPIC_KEY:
        raise Exception("No ANTHROPIC_API_KEY set")

    claude_messages = [m for m in messages if m["role"] != "system"]

    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 300,
        "system": build_system(),
        "messages": claude_messages
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode())
        return data["content"][0]["text"].strip()


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "name": "F.R.I.D.A.Y API",
            "version": "1.0.0",
            "status": "online",
            "engine": "claude",
            "endpoints": {
                "chat":   "POST /api/chat",
                "health": "GET  /api/health"
            }
        }).encode())

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length).decode())

            message = body.get("message", "").strip()
            history = body.get("history", [])

            if not message:
                self._json(400, {"error": "No message provided"})
                return

            messages = [{"role": "system", "content": build_system()}]
            for m in history:
                messages.append({"role": m["role"], "content": m["content"]})
            messages.append({"role": "user", "content": message})

            reply = call_claude(messages)

            self._json(200, {
                "reply": reply,
                "model_used": "claude-haiku-4-5-20251001",
                "engine": "claude"
            })

        except Exception as e:
            self._json(503, {"detail": str(e)})

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, data):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass
