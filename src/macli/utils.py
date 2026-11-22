"""Utilities for parsing generated file blocks and safely writing files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class FileArtifact:
    """Represents a single file parsed from LLM output."""

    path: str
    content: str


# Matches headings like:
#   ### FILE: src/app.py
#   ### FILE: `src/app.py`
#   ## FILE: README.md
# followed by a fenced code block (3+ backticks, optional language tag).
_FILE_BLOCK_PATTERN = re.compile(
    r"(?m)^#{2,4}\s*FILE\s*:\s*`?([^\r\n`]+?)`?\s*$\s*"
    r"(?P<fence>`{3,})[^\r\n]*\r?\n"
    r"(?:(?P<content>.*?)\r?\n)?"
    r"(?P=fence)[ \t]*(?=\r?$)",
    re.DOTALL,
)


def normalize_relative_path(raw_path: str) -> str:
    """Normalize and validate a relative file path to prevent directory traversal.

    Raises:
        ValueError: If the path is empty, absolute, or escapes the target directory.
    """
    cleaned = raw_path.strip().strip("`\"'").replace("\\", "/")
    cleaned = cleaned.lstrip("./") if cleaned.startswith("./") else cleaned

    if not cleaned:
        raise ValueError("Empty file path.")

    # Reject Windows drive letters (e.g., C:/foo) and absolute POSIX paths (/etc/passwd)
    if cleaned.startswith("/") or re.match(r"^[A-Za-z]:", cleaned):
        raise ValueError(f"Absolute file paths are not allowed: {raw_path!r}")

    posix_path = PurePosixPath(cleaned)
    parts = [part for part in posix_path.parts if part not in ("", ".")]

    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"Unsafe file path (path traversal detected): {raw_path!r}")

    return "/".join(parts)


def parse_file_blocks(text: str) -> list[FileArtifact]:
    """Extract `### FILE: <path>` fenced code blocks from LLM output.

    If the same normalized path appears more than once, the latest block wins.
    """
    artifacts_by_path: dict[str, FileArtifact] = {}

    for match in _FILE_BLOCK_PATTERN.finditer(text):
        raw_path = match.group(1)
        content = match.group("content") or ""
        try:
            normalized = normalize_relative_path(raw_path)
        except ValueError:
            continue

        # Ensure trailing newline for non-empty text files
        final_content = (
            content if (not content or content.endswith("\n")) else content + "\n"
        )
        artifacts_by_path[normalized] = FileArtifact(
            path=normalized,
            content=final_content,
        )

    return list(artifacts_by_path.values())


def safe_write_files(files: list[FileArtifact], output_dir: Path) -> list[Path]:
    """Safely write parsed FileArtifact objects into `output_dir`.

    Creates `output_dir` and any nested parent directories automatically.
    Guards against path traversal by verifying resolved paths stay inside `output_dir`.

    Returns:
        List of Paths to the written files.
    """
    base_dir = output_dir.resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for artifact in files:
        safe_rel = normalize_relative_path(artifact.path)
        target_path = (base_dir / safe_rel).resolve()

        # Defense-in-depth check that target_path stays inside base_dir
        try:
            target_path.relative_to(base_dir)
        except ValueError as exc:
            raise ValueError(
                f"Refusing to write outside output directory: {artifact.path!r}"
            ) from exc

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(artifact.content, encoding="utf-8")
        written.append(target_path)

    return written
