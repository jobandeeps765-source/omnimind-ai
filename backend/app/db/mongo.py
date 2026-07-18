"""
Async Mongo connection + collection accessors.

Every collection that stores user data includes a `user_id` field, and
every query helper below requires a user_id up front. This is the
"per-user data isolation enforced at the API layer" constraint -- routes
should never query these collections without going through a dependency
that resolves the authenticated user first (see app.auth.utils.get_current_user).
"""
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URI)
    return _client


def get_db():
    return get_client()[settings.MONGO_DB_NAME]


# Collection shortcuts -- keeps route code from hardcoding string names.
def users_collection():
    return get_db()["users"]


def chats_collection():
    return get_db()["chats"]


def messages_collection():
    return get_db()["messages"]


def memory_collection():
    return get_db()["memory"]


def files_collection():
    return get_db()["files"]


def tasks_collection():
    return get_db()["tasks"]


async def ensure_indexes():
    """Call once at startup. Cheap/idempotent."""
    await users_collection().create_index("email", unique=True)
    await messages_collection().create_index([("user_id", 1), ("chat_id", 1)])
    await memory_collection().create_index([("user_id", 1)])
    await files_collection().create_index([("user_id", 1)])
    await tasks_collection().create_index([("user_id", 1)])
