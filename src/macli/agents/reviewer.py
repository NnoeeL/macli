"""Reviewer agent: inspects generated code and returns APPROVED or REVISE."""

from __future__ import annotations

import re
from dataclasses import dataclass

from macli.agents.base import BaseAgent

REVIEWER_SYSTEM_PROMPT = """\
You are the Reviewer Agent in a lightweight multi-agent software engineering CLI (`macli`).

Your job is to carefully review the Coder Agent's output against the original user prompt.
Check for:
- Correctness and bugs (syntax errors, broken imports, runtime crashes, logic flaws)
- Completeness (all requested features implemented, no placeholders or truncated files)
- Format compliance (every file uses `### FILE: <relative/path>` followed by a fenced code block)
- Cleanliness and basic error handling

CRITICAL OUTPUT FORMAT RULES:
- The VERY FIRST LINE of your response MUST be either:
  STATUS: APPROVED
  or
  STATUS: REVISE
- Follow the status line with concise, actionable bullet points.
- Only return `STATUS: REVISE` if there are concrete bugs, missing requirements, or format issues. Do not nitpick style if the code is correct and complete.
"""


@dataclass(frozen=True)
class ReviewResult:
    """Structured result parsed from the Reviewer Agent's response."""

    approved: bool
    status: str
    feedback: str
    raw: str


_STATUS_PATTERN = re.compile(
    r"^\s*(?:\*{0,2}|#{0,3}\s*)STATUS\s*:\s*(APPROVED|REVISE)\b",
    re.IGNORECASE | re.MULTILINE,
)


def parse_review(output: str) -> ReviewResult:
    """Parse the Reviewer Agent output into a structured ReviewResult."""
    cleaned = output.strip()
    match = _STATUS_PATTERN.search(cleaned)

    if match:
        status = match.group(1).upper()
        approved = status == "APPROVED"
        # Extract feedback after the matched status line
        line_end = cleaned.find("\n", match.end())
        feedback = cleaned[line_end + 1 :].strip() if line_end != -1 else ""
    else:
        # Fallback: default to REVISE if status header is missing so issues aren't silently ignored
        status = "REVISE"
        approved = False
        feedback = cleaned

    return ReviewResult(
        approved=approved,
        status=status,
        feedback=feedback or ("Looks good!" if approved else "Please review and fix issues."),
        raw=cleaned,
    )


class ReviewerAgent(BaseAgent):
    """Reviews generated code and emits STATUS: APPROVED or STATUS: REVISE."""

    name = "Reviewer"
    role = "Code Review & Quality Gate"
    system_prompt = REVIEWER_SYSTEM_PROMPT
    temperature = 0.1

    def review(self, *, user_prompt: str, coder_output: str) -> ReviewResult:
        """Review the Coder Agent's output against the original user prompt."""
        prompt = (
            f"Original User Request:\n{user_prompt}\n\n"
            f"Coder Output:\n{coder_output}\n\n"
            "Review the code thoroughly. Remember to start your very first line with "
            "`STATUS: APPROVED` or `STATUS: REVISE`."
        )
        raw = self.run(prompt)
        return parse_review(raw)
