from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx
import datetime
import os

OLLAMA_URL    = os.getenv("OLLAMA_URL",    "http://localhost:11434")
OLLAMA_MODEL  = os.getenv("OLLAMA_MODEL",  "llama3.2")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
USE_FALLBACK  = os.getenv("USE_FALLBACK",  "true").lower() == "true"

FRIDAY_SYSTEM = (
    "You are Friday, the witty and loyal AI assistant from Iron Man. "
    "You address the user as 'Boss'. "
    "Be helpful, concise, slightly sarcastic, and always professional. "
    "Keep responses short — 1-3 sentences unless asked for detail. "
    "No markdown, no asterisks — plain text only."
)

app = FastAPI(title="F.R.I.D.A.Y API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[list[Message]] = []

class ChatResponse(BaseModel):
    reply: str
    model_used: str
    engine: str

def build_system_prompt():
    now = datetime.datetime.now().strftime("%B %d, %Y — %I:%M %p")
    return f"{FRIDAY_SYSTEM} Current date & time: {now}"

async def try_ollama(messages):
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            tags = await client.get(f"{OLLAMA_URL}/api/tags")
            models = tags.json().get("models", [])
            model_name = next(
                (m["name"] for m in models
                 if m["name"] == OLLAMA_MODEL or m["name"].startswith(OLLAMA_MODEL + ":")),
                OLLAMA_MODEL
            )
        except Exception:
            model_name = OLLAMA_MODEL

        res = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": model_name, "stream": False, "messages": messages}
        )
        res.raise_for_status()
        return res.json()["message"]["content"].strip(), model_name

async def try_claude(messages):
    if not ANTHROPIC_KEY:
        raise Exception("No Anthropic API key configured")
    claude_messages = [m for m in messages if m["role"] != "system"]
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "system": build_system_prompt(),
                "messages": claude_messages
            }
        )
        res.raise_for_status()
        return res.json()["content"][0]["text"].strip()

@app.get("/")
async def root():
    return {"name": "F.R.I.D.A.Y API", "status": "online", "version": "1.0.0"}

@app.get("/health")
async def health():
    ollama_ok = False
    ollama_models = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"{OLLAMA_URL}/api/tags")
            ollama_models = [m["name"] for m in res.json().get("models", [])]
            ollama_ok = True
    except Exception:
        pass
    return {
        "status": "online",
        "ollama": {"reachable": ollama_ok, "models": ollama_models},
        "claude": {"available": bool(ANTHROPIC_KEY)},
        "fallback_enabled": USE_FALLBACK
    }

@app.get("/models")
async def list_models():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"{OLLAMA_URL}/api/tags")
            return {"models": [m["name"] for m in res.json().get("models", [])]}
    except Exception:
        return {"models": [], "error": "Ollama not reachable"}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    messages = [{"role": "system", "content": build_system_prompt()}]
    for m in (req.history or []):
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": req.message})

    try:
        reply, model_name = await try_ollama(messages)
        return ChatResponse(reply=reply, model_used=model_name, engine="ollama")
    except Exception as ollama_err:
        if not USE_FALLBACK:
            raise HTTPException(status_code=503, detail=str(ollama_err))
        try:
            reply = await try_claude(messages)
            return ChatResponse(reply=reply, model_used="claude-haiku-4-5-20251001", engine="claude")
        except Exception as claude_err:
            raise HTTPException(status_code=503,
                detail=f"Both failed. Ollama: {ollama_err} | Claude: {claude_err}")
