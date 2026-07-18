import os

from app.llm.provider import get_llm

SYSTEM_PROMPT = (
    "You are OmniMind AI's research agent. You are given raw web search "
    "results below. Synthesize an answer grounded in them, and cite "
    "which result each claim came from by its [n] index. If the results "
    "don't answer the question, say so plainly instead of guessing."
)


async def _web_search(query: str) -> list[dict]:
    """
    Pluggable web search. Wired for SerpAPI/Tavily/Bing here as an
    example -- set SEARCH_API_KEY + SEARCH_PROVIDER to enable. With no
    key configured, returns an empty list and the agent degrades to a
    plain LLM answer with a caveat (keeps the app runnable offline).
    """
    api_key = os.getenv("SEARCH_API_KEY")
    if not api_key:
        return []

    provider = os.getenv("SEARCH_PROVIDER", "tavily")
    import httpx

    async with httpx.AsyncClient(timeout=15) as client:
        if provider == "tavily":
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": query, "max_results": 5},
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {"title": r.get("title"), "url": r.get("url"), "snippet": r.get("content")}
                for r in data.get("results", [])
            ]

    return []


async def run(user_message: str, context: dict):
    trail = [f"research_agent: searching web for query"]
    results = await _web_search(user_message)

    llm = get_llm()

    if not results:
        trail.append("research_agent: no SEARCH_API_KEY configured, no live results -- "
                      "answering from model knowledge with an explicit caveat")
        messages = [{"role": "user", "content": user_message}]
        reply = await llm.generate(
            messages,
            system=(
                "You are a research agent but no live web search is configured. "
                "Answer from your own knowledge and explicitly warn the user this "
                "may be outdated or incomplete, and that connecting SEARCH_API_KEY "
                "will enable grounded, cited answers."
            ),
        )
        return reply, [], trail

    trail.append(f"research_agent: got {len(results)} search result(s), synthesizing")
    formatted = "\n\n".join(
        f"[{i+1}] {r['title']} ({r['url']})\n{r['snippet']}" for i, r in enumerate(results)
    )
    messages = [{"role": "user", "content": f"Search results:\n{formatted}\n\nQuestion: {user_message}"}]
    reply = await llm.generate(messages, system=SYSTEM_PROMPT)
    sources = [{"type": "web", "title": r["title"], "url": r["url"]} for r in results]

    return reply, sources, trail
