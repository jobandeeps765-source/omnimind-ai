import json
import uuid
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.auth.utils import get_current_user
from app.chat.models import SendMessageRequest
from app.db.mongo import chats_collection, messages_collection
from app.memory.service import retrieve_relevant
from app.agents.router import route_and_run
from app.llm.provider import get_llm

router = APIRouter(prefix="/chat", tags=["chat"])


async def _get_or_create_chat(user_id: str, chat_id: str | None) -> str:
    if chat_id:
        existing = await chats_collection().find_one({"_id": ObjectId(chat_id), "user_id": user_id})
        if existing:
            return chat_id
    doc = {
        "user_id": user_id,
        "title": "New chat",
        "created_at": datetime.now(timezone.utc),
    }
    result = await chats_collection().insert_one(doc)
    return str(result.inserted_id)


async def _load_history(user_id: str, chat_id: str, limit: int = 20) -> list[dict]:
    cursor = (
        messages_collection()
        .find({"user_id": user_id, "chat_id": chat_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    items = await cursor.to_list(length=limit)
    items.reverse()
    return [{"role": m["role"], "content": m["content"]} for m in items]


async def _save_message(user_id: str, chat_id: str, role: str, content: str, agent: str | None = None):
    await messages_collection().insert_one(
        {
            "user_id": user_id,
            "chat_id": chat_id,
            "role": role,
            "content": content,
            "agent": agent,
            "created_at": datetime.now(timezone.utc),
        }
    )


@router.get("/list")
async def list_chats(user: dict = Depends(get_current_user)):
    cursor = chats_collection().find({"user_id": str(user["_id"])}).sort("created_at", -1)
    items = await cursor.to_list(length=200)
    return [{"id": str(c["_id"]), "title": c["title"], "created_at": c["created_at"]} for c in items]


@router.get("/history/{chat_id}")
async def get_history(chat_id: str, user: dict = Depends(get_current_user)):
    return await _load_history(str(user["_id"]), chat_id, limit=200)


@router.post("/send")
async def send_message(body: SendMessageRequest, user: dict = Depends(get_current_user)):
    """
    Non-streaming endpoint: runs the full agent-routing pipeline and
    returns the reply plus the routing trail and sources in one shot.
    Use /chat/stream for token-by-token streaming.
    """
    user_id = str(user["_id"])
    chat_id = await _get_or_create_chat(user_id, body.chat_id)

    await _save_message(user_id, chat_id, "user", body.message)

    history = await _load_history(user_id, chat_id, limit=20)
    memory = await retrieve_relevant(user_id, body.message)

    context = {
        "user_id": user_id,
        "chat_history": history[:-1] if history else [],
        "memory": memory,
        "active_file_path": body.active_file_path,
    }

    result = await route_and_run(body.message, context)
    await _save_message(user_id, chat_id, "assistant", result.reply, agent=result.agent)

    return {
        "chat_id": chat_id,
        "agent": result.agent,
        "reply": result.reply,
        "trail": result.trail,
        "sources": result.sources,
    }


@router.post("/stream")
async def stream_message(body: SendMessageRequest, user: dict = Depends(get_current_user)):
    """
    SSE endpoint. Emits routing/trail events first (so the frontend can
    show the agent indicator immediately), then token deltas, then a
    final 'done' event with sources.

    Note: only the general chat agent streams token-by-token today
    (it calls llm.stream directly). Other agents run to completion and
    are emitted as a single delta -- upgrading them to real streaming
    is a mechanical change once each agent's own tool-use loop is
    finalized (see README roadmap).
    """
    user_id = str(user["_id"])
    chat_id = await _get_or_create_chat(user_id, body.chat_id)
    await _save_message(user_id, chat_id, "user", body.message)

    history = await _load_history(user_id, chat_id, limit=20)
    memory = await retrieve_relevant(user_id, body.message)

    from app.agents.router import classify_intent

    agent_name = classify_intent(body.message)

    async def event_stream():
        def sse(event: str, data: dict):
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        yield sse("routing", {"agent": agent_name, "chat_id": chat_id})

        full_reply = ""
        sources = []

        if agent_name == "chat":
            from app.agents.chat_agent import SYSTEM_PROMPT

            system = SYSTEM_PROMPT
            if memory:
                facts = "\n".join(f"- {m}" for m in memory)
                system += f"\n\nKnown facts about this user:\n{facts}"

            llm = get_llm()
            messages = (history[:-1] if history else []) + [
                {"role": "user", "content": body.message}
            ]
            async for delta in llm.stream(messages, system=system):
                full_reply += delta
                yield sse("delta", {"text": delta})
        else:
            context = {
                "user_id": user_id,
                "chat_history": history[:-1] if history else [],
                "memory": memory,
                "active_file_path": body.active_file_path,
            }
            result = await route_and_run(body.message, context)
            full_reply = result.reply
            sources = result.sources
            yield sse("delta", {"text": full_reply})

        await _save_message(user_id, chat_id, "assistant", full_reply, agent=agent_name)
        yield sse("done", {"sources": sources})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
