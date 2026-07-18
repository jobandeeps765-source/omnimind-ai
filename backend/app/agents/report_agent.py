from app.llm.provider import get_llm

SYSTEM_PROMPT = (
    "You are OmniMind AI's report-writing agent. Produce a well-"
    "structured Markdown document: a title, short executive summary, "
    "clearly headed sections, and a conclusion. Prefer bullet points "
    "over long paragraphs where it aids scanning. If RAG source context "
    "is provided, ground claims in it and list sources at the end."
)


async def run(user_message: str, context: dict):
    trail = ["report_agent: building structured-output prompt"]
    rag_chunks = context.get("rag_chunks", [])

    prompt = user_message
    sources = []
    if rag_chunks:
        joined = "\n\n".join(f"[{i+1}] {c['text']}" for i, c in enumerate(rag_chunks))
        prompt = f"Source material:\n{joined}\n\nTask: {user_message}"
        sources = [{"type": "document", "doc": c.get("source")} for c in rag_chunks]
        trail.append(f"report_agent: grounded in {len(rag_chunks)} RAG chunk(s)")

    llm = get_llm()
    reply = await llm.generate([{"role": "user", "content": prompt}], system=SYSTEM_PROMPT)
    trail.append(f"report_agent: provider '{llm.name}' generated report")

    return reply, sources, trail
