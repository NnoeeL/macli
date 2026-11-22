"""Base agent abstraction."""

from __future__ import annotations

from macli.llm import LLMClient


class BaseAgent:
    """Base class for all specialized agents in macli."""

    name: str = "Agent"
    role: str = "General assistant"
    system_prompt: str = "You are a helpful AI assistant."
    temperature: float | None = None

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def run(self, user_prompt: str) -> str:
        """Execute the agent with the given user prompt."""
        return self.llm.chat(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            temperature=self.temperature,
        )
