"""CLI entry point for macli."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from macli import __version__
from macli.config import ConfigError, load_settings
from macli.llm import LLMClient, LLMError
from macli.orchestrator import Orchestrator

app = typer.Typer(
    name="macli",
    help="Lightweight Multi-Agent CLI (Planner -> Coder -> Reviewer).",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

ENV_TEMPLATE = """\
# ==============================================================================
# macli LLM Configuration (OpenAI-compatible endpoint)
# ==============================================================================

# Required: API key for your provider (for local Ollama, use any string like "ollama")
LLM_API_KEY=your-api-key-here

# OpenAI-compatible API Base URL
LLM_BASE_URL=https://api.groq.com/openai/v1

# Model name supported by your provider
LLM_MODEL=llama-3.3-70b-versatile

# Optional settings
# LLM_TEMPERATURE=0.2
# LLM_TIMEOUT=120

# --- Provider Examples ---
# Groq:       LLM_BASE_URL=https://api.groq.com/openai/v1 | LLM_MODEL=llama-3.3-70b-versatile
# Gemini:     LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/ | LLM_MODEL=gemini-2.0-flash
# OpenRouter: LLM_BASE_URL=https://openrouter.ai/api/v1 | LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free
# Ollama:     LLM_BASE_URL=http://localhost:11434/v1 | LLM_MODEL=qwen2.5-coder:7b | LLM_API_KEY=ollama
# OpenAI:     LLM_BASE_URL=https://api.openai.com/v1 | LLM_MODEL=gpt-4o-mini
"""


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold cyan]macli[/bold cyan] v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=_version_callback,
        is_eager=True,
        help="Show the macli version and exit.",
    ),
) -> None:
    """macli — Lightweight Multi-Agent CLI."""


@app.command()
def init(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite an existing .env file if present.",
    ),
) -> None:
    """Create a `.env` configuration template in the current directory."""
    env_file = Path.cwd() / ".env"

    if env_file.exists() and not force:
        console.print(
            Panel(
                f"[yellow]`{env_file}` already exists.[/yellow]\n"
                "Use [bold]macli init --force[/bold] to overwrite it.",
                title="Configuration Exists",
                border_style="yellow",
            )
        )
        raise typer.Exit(code=0)

    env_file.write_text(ENV_TEMPLATE, encoding="utf-8")
    console.print(
        Panel(
            f"[green]Created `{env_file}` successfully![/green]\n\n"
            "Next steps:\n"
            "1. Open `.env` and set [bold]LLM_API_KEY[/bold], [bold]LLM_BASE_URL[/bold], "
            "and [bold]LLM_MODEL[/bold].\n"
            '2. Run: [bold cyan]macli run "Build a CLI password generator in Python"[/bold cyan]',
            title="macli Initialized",
            border_style="green",
        )
    )


@app.command()
def run(
    prompt: str = typer.Argument(
        ...,
        help="Prompt describing the project or script you want macli to build.",
    ),
    output: Path = typer.Option(
        Path("./output"),
        "--output",
        "-o",
        help="Directory where generated files will be written.",
    ),
    max_loops: int = typer.Option(
        2,
        "--max-loops",
        "-m",
        min=1,
        max=10,
        help="Maximum number of Coder -> Reviewer iterations.",
    ),
) -> None:
    """Run the Planner -> Coder -> Reviewer pipeline and save generated files."""
    try:
        settings = load_settings()
    except ConfigError as exc:
        console.print(
            Panel(
                f"[red]{exc}[/red]",
                title="[bold red]Configuration Error[/bold red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1) from None

    console.print(
        Panel(
            f"[bold]Prompt:[/bold] {prompt}\n"
            f"[bold]Model:[/bold] `{settings.model}`\n"
            f"[bold]Endpoint:[/bold] `{settings.base_url}`\n"
            f"[bold]Output Dir:[/bold] `{output}`  |  [bold]Max Loops:[/bold] {max_loops}",
            title=f"[bold cyan]macli v{__version__}[/bold cyan]",
            border_style="cyan",
        )
    )

    llm = LLMClient(settings)
    orchestrator = Orchestrator(llm, console=console)

    try:
        result = orchestrator.run(prompt, output_dir=output, max_loops=max_loops)
    except LLMError as exc:
        console.print(
            Panel(
                f"[red]{exc}[/red]",
                title="[bold red]LLM Error[/bold red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        console.print(
            Panel(
                f"[red]{exc}[/red]",
                title="[bold red]Output Error[/bold red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1) from None

    # Summary Table
    resolved_output = output.resolve()
    table = Table(
        title="Generation Summary",
        show_header=True,
        header_style="bold cyan",
        border_style="bright_black",
    )
    table.add_column("File", style="green")
    table.add_column("Size", justify="right", style="white")

    if result.written_files:
        for file_path in result.written_files:
            rel = file_path.relative_to(resolved_output).as_posix()
            size = file_path.stat().st_size
            table.add_row(rel, f"{size:,} bytes")
    else:
        table.add_row("[yellow](no files parsed from Coder output)[/yellow]", "-")

    console.print()
    console.print(table)

    status_badge = (
        "[bold green]APPROVED[/bold green]"
        if result.approved
        else "[bold yellow]MAX LOOPS REACHED[/bold yellow]"
    )
    console.print(
        Panel(
            f"[bold]Final Status:[/bold] {status_badge}\n"
            f"[bold]Iterations Used:[/bold] {result.iterations} / {max_loops}\n"
            f"[bold]Files Created:[/bold] {len(result.written_files)}\n"
            f"[bold]Output Path:[/bold] `{resolved_output}`",
            title="[bold]Run Complete[/bold]",
            border_style="green" if result.approved else "yellow",
        )
    )


if __name__ == "__main__":
    app()
