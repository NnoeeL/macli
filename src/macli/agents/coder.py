"""Coder agent: writes complete code formatted in parseable file blocks."""

from __future__ import annotations

from macli.agents.base import BaseAgent

CODER_SYSTEM_PROMPT = """\
You are the Coder Agent in a lightweight multi-agent software engineering CLI (`macli`).

Your job is to write clean, complete, production-quality code following the Planner's plan (and any Reviewer feedback during revision loops).

CRITICAL OUTPUT FORMAT RULES:
1. Every file MUST be preceded by a heading in this exact format:
   ### FILE: relative/path/to/filename.ext
2. Immediately after the heading, provide the COMPLETE file contents inside a fenced code block (```language ... ```).
3. Never use placeholders like `# TODO`, `...`, or `// rest of code`. Always output the full content of every file.
4. When revising code based on Reviewer feedback, output ALL files in full again (not just diffs) so the final output is self-contained.
5. Use relative paths only (no leading `/` or `..`).

Example:
### FILE: app.py
```python
def main() -> None:
    print("Hello, world!")


if __name__ == "__main__":
    main()
```
"""


class CoderAgent(BaseAgent):
    """Generates or revises project source files based on plan and review feedback."""

    name = "Coder"
    role = "Code Generation & Revision"
    system_prompt = CODER_SYSTEM_PROMPT
    temperature = 0.2

    def code(
        self,
        *,
        user_prompt: str,
        plan: str,
        previous_code: str | None = None,
        review_feedback: str | None = None,
    ) -> str:
        """Generate initial code or revise existing code using reviewer feedback."""
        if previous_code and review_feedback:
            prompt = (
                f"Original User Request:\n{user_prompt}\n\n"
                f"Implementation Plan:\n{plan}\n\n"
                f"Previous Code:\n{previous_code}\n\n"
                f"Reviewer Feedback (MUST address all issues):\n{review_feedback}\n\n"
                "Please revise the implementation and output ALL files in full using "
                "the exact `### FILE: <path>` format."
            )
        else:
            prompt = (
                f"Original User Request:\n{user_prompt}\n\n"
                f"Implementation Plan:\n{plan}\n\n"
                "Implement all files listed in the plan in full using the exact "
                "`### FILE: <path>` format."
            )
        return self.run(prompt)
