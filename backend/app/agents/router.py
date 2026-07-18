"""
Multi-agent router.

MVP implementation uses a fast keyword/heuristic classifier so routing
works instantly with zero LLM calls (and zero API keys). This is the
seam where a LangGraph-based classifier drops in later without changing
the agent interface -- see roadmap in README.md.

Every agent implements `async def run(user_message, context) -> AgentResult`
and every routing decision is logged into `trail` so it's visible to the
frontend, not a black box (per constraints).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.agents import chat_agent, coding_agent, data_agent, research_agent, report_agent

AGENTS = {
    "chat": chat_agent,
    "coding": coding_agent,
    "data_analysis": data_agent,
    "research": research_agent,
    "report_writing": report_agent,
}

_ROUTING_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("coding", ("code", "bug", "function", "debug", "python", "javascript",
                "typescript", "error", "stack trace", "refactor", "compile")),
    ("data_analysis", ("csv", "excel", "spreadsheet", "dataframe", "chart",
                        "plot", "analyze this data", "pandas", "column")),
    ("research", ("search the web", "look up", "latest", "news", "find out",
                  "research", "current price", "who is the")),
    ("report_writing", ("write a report", "write a memo", "summarize this into",
                         "draft a document", "write-up", "generate a report")),
]


@dataclass
class AgentResult:
    agent: str
    reply: str
    trail: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)


def classify_intent(message: str) -> str:
    lowered = message.lower()
    for agent_name, keywords in _ROUTING_RULES:
        if any(k in lowered for k in keywords):
            return agent_name
    return "chat"


async def route_and_run(user_message: str, context: dict) -> AgentResult:
    """
    context carries whatever an agent might need: user_id, chat_history,
    retrieved memory, retrieved RAG chunks, uploaded file refs, etc.
    """
    trail: list[str] = []

    agent_name = classify_intent(user_message)
    trail.append(f"router: classified intent as '{agent_name}'")

    agent_module = AGENTS[agent_name]
    trail.append(f"router: dispatching to {agent_module.__name__}")

    reply, sources, agent_trail = await agent_module.run(user_message, context)
    trail.extend(agent_trail)

    return AgentResult(agent=agent_name, reply=reply, trail=trail, sources=sources)
