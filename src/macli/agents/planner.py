"""Planner agent: breaks down the user prompt into a clear plan and file list."""

from __future__ import annotations

from macli.agents.base import BaseAgent

PLANNER_SYSTEM_PROMPT = """\
You are the Planner Agent in a lightweight multi-agent software engineering CLI (`macli`).

Your job is to analyze the user's request and produce a concise, actionable implementation plan.

Follow this exact structure in Markdown:
## Goal
One-sentence summary of what will be built.

## File Structure
List every file to create using relative paths (e.g., `main.py`, `utils/helpers.py`, `README.md`) with a short description of each file's responsibility.

## Implementation Steps
Numbered step-by-step plan covering architecture, edge cases, dependencies, and how to run the result.

Rules:
- Keep the project minimal, clean, and self-contained.
- Prefer standard library modules when possible; only list external dependencies if truly needed.
- Do NOT write full implementation code — leave coding to the Coder Agent.
"""


class PlannerAgent(BaseAgent):
    """Breaks a user prompt into a structured plan and exact list of files."""

    name = "Planner"
    role = "Architecture & Task Breakdown"
    system_prompt = PLANNER_SYSTEM_PROMPT
    temperature = 0.2

    def plan(self, user_prompt: str) -> str:
        """Generate an implementation plan for the given user prompt."""
        prompt = (
            "Create a clear, step-by-step implementation plan and exact file list "
            f"for the following request:\n\n{user_prompt}"
        )
        return self.run(prompt)
