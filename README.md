# MiniMe

A modular multi-package repository and workspace for agentic AI tools, operational knowledge harnesses, and agent infrastructure.

---

## Workspace Packages

| Package | Location | Description |
| :--- | :--- | :--- |
| **`wikiskill`** | [`src/wikiskill/`](src/wikiskill/README.md) | Distributed, self-evolving knowledge & skill harness with PR-gated hub sync and background watcher daemon. |

*Additional packages will be integrated into the `src/` directory as new tools and capabilities are added.*

---

## Repository Structure

```text
MiniMe/
├── src/
│   └── wikiskill/               # WikiSkill package implementation
│       ├── README.md            # Comprehensive WikiSkill documentation
│       ├── cli.py               # CLI entrypoints (wikiskill, wikiskill-harness)
│       ├── daemon.py            # Background project watcher daemon
│       ├── harness.py           # Core post-session evolution harness
│       ├── models.py            # Session trajectory data models
│       ├── skill_proposer.py    # Operational skill generator & frontmatter parser
│       ├── sync.py              # GitHub CLI PR-gate and hub synchronization
│       └── wiki_manager.py      # Pattern wiki maintainer & index builder
├── tests/
│   ├── unit/                    # Fast, isolated unit test suites
│   └── integration/             # Full lifecycle end-to-end integration tests
├── plugins/
│   └── wikiskill/               # Native plugin companion (plugin.json)
├── docs/                        # Architectural documentation and specifications
├── pyproject.toml               # Python project configuration & dependencies
└── CLAUDE.md                    # Project development & loop guidelines
```

---

## Getting Started

### 1. Installation

This repository uses [`uv`](https://docs.astral.sh/uv/) for Python environment and package management:

```bash
# Install workspace dependencies
uv sync

# Or perform an editable install of the packages
uv pip install -e .
```

### 2. Running Commands

CLI tools defined in packages can be run directly via `uv run`:

```bash
# WikiSkill CLI help
uv run wikiskill --help

# Run background watcher daemon
uv run wikiskill daemon --once
```

---

## Testing & Quality Assurance

All tests, linting, and formatting checks run across workspace packages:

```bash
# Run entire test suite (unit + integration)
uv run pytest -v

# Run unit tests only
uv run pytest tests/unit/ -v

# Run integration tests only
uv run pytest tests/integration/ -v

# Lint and format checks
uv run ruff check .
uv run ruff format --check .
uvx pyrefly check --summarize-errors
```

---

## Adding New Packages

To add a new package to `MiniMe`:
1. Create a dedicated package folder under `src/<package_name>/`.
2. Include a `__init__.py` and a standalone `README.md` documenting its capabilities.
3. Expose any relevant CLI scripts or build targets in `pyproject.toml`.
4. Add corresponding unit tests in `tests/unit/` and integration tests in `tests/integration/`.
