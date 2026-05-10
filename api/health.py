import json
import os
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "online",
            "claude": {"available": bool(os.environ.get("ANTHROPIC_API_KEY"))},
            "ollama": {"reachable": False},
            "fallback_enabled": True
        }).encode())

    def log_message(self, *args):
        pass
