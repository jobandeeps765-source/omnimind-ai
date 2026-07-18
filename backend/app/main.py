from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.mongo import ensure_indexes
from app.auth.routes import router as auth_router
from app.chat.routes import router as chat_router
from app.chat.files_routes import router as files_router
from app.memory.routes import router as memory_router
from app.llm.provider import get_llm


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    # Touch the LLM provider once at startup so any misconfiguration
    # (bad key, unreachable Ollama) surfaces in logs immediately instead
    # of on the first user's chat request.
    llm = get_llm()
    print(f"[OmniMind] LLM provider active: {llm.name}")
    yield


app = FastAPI(title="OmniMind AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(files_router)
app.include_router(memory_router)


@app.get("/health")
async def health():
    return {"status": "ok", "llm_provider": get_llm().name}
