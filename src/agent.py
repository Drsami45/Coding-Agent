"""
Builds a LangGraph ReAct-style agent backed by either Groq or Google Gemini,
with the sandboxed coding tools attached.
"""
from __future__ import annotations

from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

from .config import GOOGLE_API_KEY, GROQ_API_KEY
from .prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS

# One shared in-memory checkpointer so each Streamlit chat "thread_id" keeps
# its own conversation history/state for the lifetime of the process.
_CHECKPOINTER = MemorySaver()


def get_llm(provider: str, model: str, temperature: float = 0.2):
    """Instantiate the chat model for the chosen provider."""
    if provider == "Groq":
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
        from langchain_groq import ChatGroq

        return ChatGroq(model=model, temperature=temperature, api_key=GROQ_API_KEY)

    if provider == "Google":
        if not GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY is not set. Add it to your .env file.")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model, temperature=temperature, google_api_key=GOOGLE_API_KEY
        )

    raise ValueError(f"Unknown provider: {provider}")


def build_agent(provider: str, model: str, temperature: float = 0.2):
    """Compile a LangGraph agent graph for the given provider/model."""
    llm = get_llm(provider, model, temperature)
    graph = create_agent(
        llm,
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=_CHECKPOINTER,
    )
    return graph