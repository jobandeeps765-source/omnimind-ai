from app.llm.provider import get_llm

SYSTEM_PROMPT = (
    "You are OmniMind AI's data-analysis agent. You are given a summary "
    "of a CSV/Excel file (columns, dtypes, describe() stats) instead of "
    "the raw file. Answer the user's question using only that summary, "
    "and be explicit about what you can't determine from summary stats "
    "alone."
)


def _summarize_dataframe(path: str) -> str:
    import pandas as pd

    if path.endswith((".xlsx", ".xls")):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    lines = [
        f"Rows: {len(df)}, Columns: {len(df.columns)}",
        f"Columns: {list(df.columns)}",
        f"Dtypes:\n{df.dtypes.to_string()}",
        f"Describe:\n{df.describe(include='all').to_string()}",
    ]
    return "\n\n".join(lines)


async def run(user_message: str, context: dict):
    trail = []
    file_path = context.get("active_file_path")

    if not file_path:
        trail.append("data_agent: no active file in context, asking user to upload one")
        return (
            "I don't see a CSV or Excel file attached to this conversation yet. "
            "Upload one via the file manager and re-ask -- I'll summarize its "
            "columns and stats and answer questions grounded in that summary.",
            [],
            trail,
        )

    trail.append(f"data_agent: loading and summarizing {file_path}")
    try:
        summary = _summarize_dataframe(file_path)
    except Exception as e:
        trail.append(f"data_agent: failed to parse file ({e})")
        return (f"I couldn't parse that file: {e}", [], trail)

    llm = get_llm()
    messages = [{"role": "user", "content": f"File summary:\n{summary}\n\nQuestion: {user_message}"}]
    trail.append(f"data_agent: calling provider '{llm.name}' with dataframe summary")
    reply = await llm.generate(messages, system=SYSTEM_PROMPT)

    return reply, [{"type": "file", "path": file_path}], trail
