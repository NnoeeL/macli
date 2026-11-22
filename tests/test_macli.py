"""Unit tests for macli core modules."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rich.console import Console
from typer.testing import CliRunner

from macli.agents.reviewer import parse_review
from macli.config import ConfigError, Settings, load_settings
from macli.main import app
from macli.orchestrator import Orchestrator
from macli.utils import FileArtifact, normalize_relative_path, parse_file_blocks, safe_write_files


# ---------------------------------------------------------------------------
# utils.py tests
# ---------------------------------------------------------------------------


def test_parse_file_blocks_multiple_files() -> None:
    sample = """
Here is the generated project:

### FILE: app.py
```python
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

### FILE: `utils/math_ops.py`
```python
def add(a: int, b: int) -> int:
    return a + b
```

### FILE: pkg/__init__.py
```python
```
"""
    files = parse_file_blocks(sample)
    assert len(files) == 3
    assert files[0].path == "app.py"
    assert 'return f"Hello, {name}!"' in files[0].content
    assert files[1].path == "utils/math_ops.py"
    assert files[2].path == "pkg/__init__.py"
    assert files[2].content == ""


def test_parse_file_blocks_deduplicates_latest() -> None:
    sample = """
### FILE: main.py
```python
print("v1")
```

### FILE: main.py
```python
print("v2")
```
"""
    files = parse_file_blocks(sample)
    assert len(files) == 1
    assert 'print("v2")' in files[0].content


def test_normalize_relative_path_rejects_traversal() -> None:
    assert normalize_relative_path("./src/app.py") == "src/app.py"
    with pytest.raises(ValueError):
        normalize_relative_path("../secret.txt")
    with pytest.raises(ValueError):
        normalize_relative_path("/etc/passwd")
    with pytest.raises(ValueError):
        normalize_relative_path("C:/Windows/win.ini")


def test_safe_write_files(tmp_path: Path) -> None:
    artifacts = [
        FileArtifact(path="main.py", content="print('ok')\n"),
        FileArtifact(path="sub/helper.py", content="X = 1\n"),
    ]
    written = safe_write_files(artifacts, tmp_path / "out")
    assert len(written) == 2
    assert (tmp_path / "out" / "main.py").read_text(encoding="utf-8") == "print('ok')\n"
    assert (tmp_path / "out" / "sub" / "helper.py").read_text(encoding="utf-8") == "X = 1\n"


# ---------------------------------------------------------------------------
# reviewer.py tests
# ---------------------------------------------------------------------------


def test_parse_review_approved() -> None:
    res = parse_review("STATUS: APPROVED\n\n- Clean and complete.")
    assert res.approved is True
    assert res.status == "APPROVED"
    assert "Clean and complete." in res.feedback


def test_parse_review_revise() -> None:
    res = parse_review("**STATUS: REVISE**\n- Missing error handling in main.py")
    assert res.approved is False
    assert res.status == "REVISE"
    assert "Missing error handling" in res.feedback


# ---------------------------------------------------------------------------
# config.py tests
# ---------------------------------------------------------------------------


def test_load_settings_missing_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with pytest.raises(ConfigError, match="macli init"):
        load_settings(env_path=tmp_path / ".env")


def test_load_settings_placeholder_key_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_API_KEY=your-api-key-here\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="placeholder"):
        load_settings(env_path=env_file)


def test_load_settings_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_API_KEY=ollama\n"
        "LLM_BASE_URL=http://localhost:11434/v1\n"
        "LLM_MODEL=qwen2.5-coder:7b\n",
        encoding="utf-8",
    )
    settings = load_settings(env_path=env_file)
    assert isinstance(settings, Settings)
    assert settings.api_key == "ollama"
    assert settings.base_url == "http://localhost:11434/v1"
    assert settings.model == "qwen2.5-coder:7b"


# ---------------------------------------------------------------------------
# orchestrator.py tests
# ---------------------------------------------------------------------------


def test_orchestrator_revision_loop_and_approval(tmp_path: Path) -> None:
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [
        # 1. Planner
        "## Goal\nBuild hello script\n## File Structure\n- `hello.py`",
        # 2. Coder (attempt 1)
        "### FILE: hello.py\n```python\nprint('v1')\n```",
        # 3. Reviewer (attempt 1 -> REVISE)
        "STATUS: REVISE\n- Print Hello, World! instead of v1.",
        # 4. Coder (attempt 2)
        "### FILE: hello.py\n```python\nprint('Hello, World!')\n```",
        # 5. Reviewer (attempt 2 -> APPROVED)
        "STATUS: APPROVED\n- Looks great.",
    ]

    console = Console(record=True, quiet=True)
    orchestrator = Orchestrator(mock_llm, console=console)
    result = orchestrator.run(
        "Write a hello world script",
        output_dir=tmp_path / "out",
        max_loops=3,
    )

    assert result.approved is True
    assert result.iterations == 2
    assert len(result.written_files) == 1
    assert (tmp_path / "out" / "hello.py").read_text(encoding="utf-8") == "print('Hello, World!')\n"


def test_orchestrator_stops_at_max_loops(tmp_path: Path) -> None:
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [
        "## Goal\nPlan",
        "### FILE: a.py\n```python\nx = 1\n```",
        "STATUS: REVISE\n- Fix x",
        "### FILE: a.py\n```python\nx = 2\n```",
        "STATUS: REVISE\n- Still needs work",
    ]

    console = Console(record=True, quiet=True)
    orchestrator = Orchestrator(mock_llm, console=console)
    result = orchestrator.run("Test", output_dir=tmp_path / "out", max_loops=2)

    assert result.approved is False
    assert result.iterations == 2
    assert (tmp_path / "out" / "a.py").read_text(encoding="utf-8") == "x = 2\n"


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_cli_init_and_missing_env_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    # Running before init should fail gracefully with a helpful message
    res_fail = runner.invoke(app, ["run", "Hello world"])
    assert res_fail.exit_code == 1
    assert "macli init" in res_fail.output

    # Running init should create .env
    res_init = runner.invoke(app, ["init"])
    assert res_init.exit_code == 0
    assert (tmp_path / ".env").exists()
    content = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "LLM_API_KEY" in content
    assert "LLM_BASE_URL" in content
    assert "LLM_MODEL" in content
