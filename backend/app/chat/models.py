from pydantic import BaseModel


class SendMessageRequest(BaseModel):
    chat_id: str | None = None
    message: str
    active_file_path: str | None = None


class MessageOut(BaseModel):
    role: str
    content: str
    agent: str | None = None
