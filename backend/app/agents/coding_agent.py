from app.llm.provider import get_llm

SYSTEM_PROMPT = (
    "You are OmniMind AI's coding agent. Write correct, minimal, well-"
    "commented code. When debugging, explain the root cause before the "
    "fix. Use fenced code blocks with a language tag."
)


async def run(user_message: str, context: dict):
    trail = ["coding_agent: calling provider with coding system prompt"]
    llm = get_llm()
    messages = context.get("chat_history", []) + [{"role": "user", "content": user_message}]
    reply = await llm.generate(messages, system=SYSTEM_PROMPT)
    trail.append(f"coding_agent: provider '{llm.name}' responded")
    return reply, [], trail
