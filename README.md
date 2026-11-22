<p align="center">
  <img src="assets/logo.jpg" alt="macli — Lightweight Multi-Agent CLI" width="640" />
</p>

<h1 align="center">macli — Lightweight Multi-Agent CLI</h1>

<p align="center">
  A minimal, open-source Python CLI that orchestrates three specialized AI agents (<strong>Planner → Coder → Reviewer</strong>) to generate small software projects or scripts from a single prompt.
</p>

- **Zero heavy AI frameworks** — no LangChain, no CrewAI, just clean modular Python.
- **Universal OpenAI-compatible client** — works with **Groq**, **Google Gemini**, **OpenRouter**, **Ollama** (local), or **OpenAI** via `.env`.
- **Bounded revision loop** — Reviewer checks Coder output and returns `STATUS: APPROVED` or `STATUS: REVISE` up to `--max-loops` iterations.
- **Aesthetic terminal UI** — powered by `typer` and `rich`.

---

## Architecture

```text
User Prompt
    │
    ▼
┌───────────┐
│  Planner  │  Breaks prompt into steps & exact file list
└─────┬─────┘
      ▼
┌───────────┐       STATUS: REVISE (if loop < max_loops)
│   Coder   │ ◄──────────────────────────────────────────┐
└─────┬─────┘                                            │
      ▼                                                  │
┌───────────┐                                            │
│ Reviewer  │ ───────────────────────────────────────────┘
└─────┬─────┘
      │ STATUS: APPROVED (or max_loops reached)
      ▼
  File Writer  ──►  ./output/
```

---

## Installation

Requires **Python 3.10+**.

```bash
# 1. Clone the repository
git clone https://github.com/NnoeeL/macli.git
cd macli

# 2. (Recommended) Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# 3. Install in editable mode
pip install -e .
```

Verify installation:

```bash
macli --version
```

---

## Configuration

Generate a `.env` template in your working directory:

```bash
macli init
```

Edit `.env` with your preferred OpenAI-compatible provider:

### Free / Fast Providers

**Groq (Free tier, very fast)**
```env
LLM_API_KEY=gsk_your_groq_key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
```

**Ollama (100% Local & Free)**
```env
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5-coder:7b
```

**Google Gemini (OpenAI-compatible endpoint)**
```env
LLM_API_KEY=your_gemini_api_key
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-2.0-flash
```

**OpenRouter (Free & Paid models)**
```env
LLM_API_KEY=sk-or-v1-your_key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free
```

**OpenAI**
```env
LLM_API_KEY=sk-your_openai_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

---

## Usage

### Run the multi-agent pipeline

```bash
macli run "Build a Python CLI password generator with length and symbol flags"
```

### Custom output directory & max revision loops

```bash
macli run "Create a simple FastAPI todo API with in-memory storage" --output ./todo-app --max-loops 3
```

### CLI Options

| Command / Option | Default | Description |
| :--- | :--- | :--- |
| `macli init [--force]` | — | Creates a `.env` template in the current directory |
| `macli run "<prompt>"` | — | Runs Planner → Coder → Reviewer pipeline |
| `--output, -o <dir>` | `./output` | Target directory for generated files |
| `--max-loops, -m <int>` | `2` | Maximum Coder → Reviewer iterations (1–10) |
| `--version, -v` | — | Print `macli` version |

---

## Project Structure

```text
macli/
├── src/
│   └── macli/
│       ├── __init__.py
│       ├── main.py          # CLI entry point (Typer + Rich)
│       ├── config.py        # Env & settings loader (Pydantic)
│       ├── llm.py           # Universal OpenAI-compatible client wrapper
│       ├── orchestrator.py  # Sequential workflow & revision loop
│       ├── utils.py         # File block parser & safe file writer
│       └── agents/
│           ├── __init__.py
│           ├── base.py      # BaseAgent class
│           ├── planner.py   # Planner system prompt & logic
│           ├── coder.py     # Coder system prompt & logic
│           └── reviewer.py  # Reviewer system prompt & logic
├── tests/
│   └── test_macli.py
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Development & Testing

```bash
pip install -e ".[dev]"
pytest
```
