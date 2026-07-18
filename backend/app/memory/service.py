"""
Long-term memory layer.

MVP retrieval is keyword-overlap scoring (fast, zero-dependency, works
offline). Swap `retrieve_relevant` for an embedding-similarity lookup
against ChromaDB later without touching callers -- see README roadmap.

Every write/read is scoped by user_id, and every item is user-editable/
deletable via the /memory routes for transparency.
"""
from bson import ObjectId

from app.db.mongo import memory_collection


async def add_fact(user_id: str, text: str, source: str = "chat") -> str:
    doc = {"user_id": user_id, "text": text, "source": source}
    result = await memory_collection().insert_one(doc)
    return str(result.inserted_id)


async def list_facts(user_id: str) -> list[dict]:
    cursor = memory_collection().find({"user_id": user_id})
    items = await cursor.to_list(length=500)
    for i in items:
        i["id"] = str(i.pop("_id"))
    return items


async def delete_fact(user_id: str, fact_id: str) -> bool:
    result = await memory_collection().delete_one(
        {"_id": ObjectId(fact_id), "user_id": user_id}
    )
    return result.deleted_count > 0


async def update_fact(user_id: str, fact_id: str, text: str) -> bool:
    result = await memory_collection().update_one(
        {"_id": ObjectId(fact_id), "user_id": user_id}, {"$set": {"text": text}}
    )
    return result.modified_count > 0


async def retrieve_relevant(user_id: str, query: str, top_k: int = 5) -> list[str]:
    all_facts = await list_facts(user_id)
    if not all_facts:
        return []

    query_words = set(query.lower().split())
    scored = []
    for f in all_facts:
        fact_words = set(f["text"].lower().split())
        overlap = len(query_words & fact_words)
        scored.append((overlap, f["text"]))

    scored.sort(key=lambda x: x[0], reverse=True)
    # Include zero-overlap facts too, up to top_k, so small memory sets
    # (the common case early on) still get injected -- better UX than
    # showing nothing until overlap happens to occur.
    return [text for _, text in scored[:top_k]]
