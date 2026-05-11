import json
import os
import datetime
import urllib.request
from http.server import BaseHTTPRequestHandler

GROQ_KEY   = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

FRIDAY_SYSTEM = (
    "You are F.R.I.D.A.Y — Female Replacement Intelligent Digital Assistant Youth — "
    "Tony Stark's AI from Iron Man. You are witty, sharp, slightly sassy, fiercely loyal. "
    "You call the user 'Boss' always. Keep responses punchy — 2-4 sentences max unless detail is needed. "
    "No markdown, no asterisks, plain text only."
)

def build_system():
    now = datetime.datetime.now().strftime("%B %d, %Y — %I:%M %p")
    return f"{FRIDAY_SYSTEM} Current date & time: {now}"

def call_groq(messages):
    if not GROQ_KEY:
        raise Exception("No GROQ_API_KEY set in environment")
    body = json.dumps({
        "model": GROQ_MODEL,
        "messages": messages,
        "max_tokens": 350,
        "temperature": 0.85
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode())
        return data["choices"][0]["message"]["content"].strip()

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
            "name": "F.R.I.D.A.Y API", "status": "online",
            "engine": "groq", "model": GROQ_MODEL
        }).encode())

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length).decode())
            message = body.get("message", "").strip()
            history = body.get("history", [])
            if not message:
                self._json(400, {"error": "No message"}); return
            messages = [{"role": "system", "content": build_system()}]
            for m in history:
                messages.append({"role": m["role"], "content": m["content"]})
            messages.append({"role": "user", "content": message})
            reply = call_groq(messages)
            self._json(200, {"reply": reply, "model_used": GROQ_MODEL, "engine": "groq"})
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
