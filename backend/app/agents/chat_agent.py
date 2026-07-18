from app.llm.provider import get_llm

SYSTEM_PROMPT = (
    "You are OmniMind AI's general chat agent. Be helpful, direct, and "
    "concise. If relevant long-term memory about the user is provided "
    "below, use it naturally -- don't mention that you were given it."
)


async def run(user_message: str, context: dict):
    trail = ["chat_agent: building prompt with memory context"]

    memory_items = context.get("memory", [])
    system = SYSTEM_PROMPT
    if memory_items:
        facts = "\n".join(f"- {m}" for m in memory_items)
        system += f"\n\nKnown facts about this user:\n{facts}"
        trail.append(f"chat_agent: injected {len(memory_items)} memory item(s)")

    history = context.get("chat_history", [])
    messages = history + [{"role": "user", "content": user_message}]

    llm = get_llm()
    trail.append(f"chat_agent: calling provider '{llm.name}'")
    reply = await llm.generate(messages, system=system)

    return reply, [], trail
