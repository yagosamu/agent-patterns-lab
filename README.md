# Agent Patterns Lab

Minimal, focused implementations of AI agent patterns. Each project isolates **one design decision** and documents the trade-off behind it.

The goal is not to build products here. It is to understand a pattern deeply enough to know **when to use it and what it costs** — the part that reading documentation does not teach.

## Patterns

| Pattern | What it demonstrates | Stack |
|---|---|---|
| [self-healing-rag](self-healing-rag/) | RAG that grades its own answer, rewrites the query and retries, and gives an honest fallback instead of hallucinating | LangGraph · ChromaDB · Groq |
| [supervisor-content-team](supervisor-content-team/) | Multi-agent system where a supervisor routes four specialists, with a self-correction loop and a hard step cap | LangGraph · Gemini · Tavily |
| [persistent-memory-agent-mem0](persistent-memory-agent-mem0/) | Memory that persists across sessions, and the cost trade-off of carrying context | *in progress* |

## Recurring themes

A few decisions show up across every pattern here:

- **Knowing when to stop.** A retry limit, a step cap, an honest "I don't know". Unbounded loops are how agents burn money.
- **Right model for the job.** Routing is classification and can run on a cheap model; generation is where quality is worth paying for.
- **Prompts are not guarantees.** Termination, cost limits and safety belong in the code, not in a polite instruction to the model.

## Structure

Each folder is a standalone project with its own README, dependencies and run instructions.

```bash
cd <pattern>
uv sync
cp .env.example .env
uv run main.py
```
