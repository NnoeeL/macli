"""Sequential multi-agent orchestrator with bounded revision loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from macli.agents import CoderAgent, PlannerAgent, ReviewerAgent, ReviewResult
from macli.llm import LLMClient
from macli.utils import parse_file_blocks, safe_write_files


@dataclass
class OrchestrationResult:
    """Result returned after completing the Planner -> Coder -> Reviewer workflow."""

    plan: str
    final_code: str
    reviews: list[ReviewResult] = field(default_factory=list)
    written_files: list[Path] = field(default_factory=list)
    iterations: int = 0
    approved: bool = False


class Orchestrator:
    """Coordinates Planner, Coder, and Reviewer agents sequentially."""

    def __init__(
        self,
        llm: LLMClient,
        *,
        console: Console | None = None,
        planner: PlannerAgent | None = None,
        coder: CoderAgent | None = None,
        reviewer: ReviewerAgent | None = None,
    ) -> None:
        self.llm = llm
        self.console = console or Console()
        self.planner = planner or PlannerAgent(llm)
        self.coder = coder or CoderAgent(llm)
        self.reviewer = reviewer or ReviewerAgent(llm)

    def run(
        self,
        prompt: str,
        output_dir: Path,
        *,
        max_loops: int = 2,
    ) -> OrchestrationResult:
        """Execute the multi-agent pipeline and write final files to `output_dir`.

        Args:
            prompt: The user's software/script request.
            output_dir: Directory where generated files will be saved.
            max_loops: Maximum number of Coder -> Reviewer iterations (minimum 1).

        Returns:
            OrchestrationResult with plan, reviews, iteration count, and written files.
        """
        max_loops = max(1, max_loops)

        # 1. Planner stage
        with self.console.status(
            "[bold cyan]Planner Agent[/bold cyan] is breaking down your prompt...",
            spinner="dots",
        ):
            plan = self.planner.plan(prompt)

        self.console.print(
            Panel(
                Markdown(plan),
                title="[bold cyan]Step 1 · Planner Agent[/bold cyan]",
                border_style="cyan",
                expand=True,
            )
        )

        # 2. Coder -> Reviewer loop
        coder_output = ""
        feedback: str | None = None
        reviews: list[ReviewResult] = []
        approved = False
        iterations = 0

        for iteration in range(1, max_loops + 1):
            iterations = iteration
            action_label = (
                "writing initial code"
                if iteration == 1
                else f"revising code (attempt {iteration}/{max_loops})"
            )

            with self.console.status(
                f"[bold green]Coder Agent[/bold green] is {action_label}...",
                spinner="dots",
            ):
                coder_output = self.coder.code(
                    user_prompt=prompt,
                    plan=plan,
                    previous_code=coder_output if iteration > 1 else None,
                    review_feedback=feedback,
                )

            parsed_preview = parse_file_blocks(coder_output)
            file_list_text = (
                "\n".join(f"- `{f.path}` ({len(f.content.splitlines())} lines)" for f in parsed_preview)
                if parsed_preview
                else "_No `### FILE:` blocks detected in output._"
            )
            self.console.print(
                Panel(
                    Markdown(f"**Generated files:**\n{file_list_text}"),
                    title=(
                        f"[bold green]Step 2 · Coder Agent "
                        f"(Iteration {iteration}/{max_loops})[/bold green]"
                    ),
                    border_style="green",
                    expand=True,
                )
            )

            with self.console.status(
                f"[bold magenta]Reviewer Agent[/bold magenta] is inspecting code "
                f"(iteration {iteration}/{max_loops})...",
                spinner="dots",
            ):
                review = self.reviewer.review(
                    user_prompt=prompt,
                    coder_output=coder_output,
                )

            reviews.append(review)
            status_style = "bold green" if review.approved else "bold yellow"
            border_style = "green" if review.approved else "yellow"
            self.console.print(
                Panel(
                    Markdown(f"**Status:** `{review.status}`\n\n{review.feedback}"),
                    title=(
                        f"[{status_style}]Step 3 · Reviewer Agent "
                        f"(Iteration {iteration}/{max_loops})[/{status_style}]"
                    ),
                    border_style=border_style,
                    expand=True,
                )
            )

            if review.approved:
                approved = True
                break

            feedback = review.feedback
            if iteration < max_loops:
                self.console.print(
                    f"[yellow]↻ Revision requested. Passing feedback back to Coder "
                    f"({iteration}/{max_loops})...[/yellow]\n"
                )
            else:
                self.console.print(
                    f"[yellow]⚠ Reached maximum iterations ({max_loops}). "
                    "Writing latest generated output.[/yellow]\n"
                )

        # 3. Parse and write final files
        artifacts = parse_file_blocks(coder_output)
        written_files = safe_write_files(artifacts, output_dir) if artifacts else []

        return OrchestrationResult(
            plan=plan,
            final_code=coder_output,
            reviews=reviews,
            written_files=written_files,
            iterations=iterations,
            approved=approved,
        )
