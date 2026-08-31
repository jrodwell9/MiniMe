# AI Coding Specification: Autonomous LegalTech & AI Daily Briefing Engine

## 1. System Overview
An automated, deterministic CLI application that aggregates daily academic AI research (arXiv) and commercial legaltech news (RSS), synthesizes and extracts structured intelligence via an LLM, and formats the output into an Obsidian-compatible Markdown note deposited directly into a designated local vault.

---

## 2. Technical Stack & Constraints

- **Runtime**: Python >= 3.12
- **Package Manager**: `uv`
- **Networking**: `httpx` (async/sync HTTP client)
- **Data Validation & Parsing**: `pydantic` v2, `feedparser`, `defusedxml`
- **Templating**: `jinja2`
- **CLI Framework**: `typer` or `click`
- **LLM Interface**: Provider-agnostic client pattern (defaulting to Anthropic/Claude or Google Gemini served via GCP Vertex AI)
- **Testing**: `pytest`, `pytest-mock`, `respx` (for mocking HTTP), `freezegun`, `tmp_path`

### Hard Guardrails
1. **Network Isolation in Tests**: Zero external network calls are permitted inside `tests/unit/`. All HTTP calls to arXiv and RSS endpoints must be intercepted using `respx`. All LLM calls must use mocked response fixtures.
2. **File Safety**: Writing to the host disk must be confined to the configured `OBSIDIAN_VAULT_PATH`. File writes during testing must exclusively target `tmp_path`.
3. **Deterministic Timestamps**: Any time-based filtering (e.g., "last 24 hours") must accept an explicit reference `datetime` parameter to ensure tests are reproducible via `freezegun`.

---

## 3. Development Workflow: Strict TDD Protocol

Claude Code must strictly adhere to the Red-Green-Refactor cycle:

[Write Unit/Contract Test] ──► [Run pytest (FAIL)] ──► [Write Minimum Code] ──► [Run pytest (PASS)] ──► [Refactor]


1. **Step 1 (Red)**: Create the test file under `tests/` asserting the desired interface and edge cases. Run `pytest` to confirm failure.
2. **Step 2 (Green)**: Write the minimum implementation code under `src/` to satisfy the test assertions.
3. **Step 3 (Refactor)**: Clean up formatting, typing, and docstrings. Ensure 100% test pass rate before moving to the next feature.
4. **Step 4 (Document)**: Keep track of completed stages in a progress checklist.

---

## 4. Architecture & Component Specifications

### Directory Layout
```text
.
├── SPEC.md
├── pyproject.toml
├── .env.example
├── src/
│   ├── __init__.py
│   ├── config.py             # Pydantic Settings & environment parsing
│   ├── cli.py                # Command-line entrypoints
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── base.py           # Ingestion protocol/ABC
│   │   ├── arxiv.py          # arXiv API fetcher & Atom parser
│   │   └── rss.py            # LegalTech RSS parser & normalizer
│   ├── synthesis/
│   │   ├── __init__.py
│   │   ├── schemas.py        # Pydantic schemas for LLM data contracts
│   │   └── engine.py         # LLM prompting, extraction, and validation
│   └── output/
│       ├── __init__.py
│       ├── renderer.py       # Jinja2 markdown generator
│       └── vault_writer.py   # Atomic filesystem operations in Obsidian vault
├── templates/
│   └── briefing.md.j2        # Obsidian note template with frontmatter
└── tests/
    ├── conftest.py           # Shared fixtures, mock feeds, mock LLM outputs
    ├── test_config.py
    ├── test_arxiv.py
    ├── test_rss.py
    ├── test_synthesis.py
    ├── test_renderer.py
    └── test_vault_writer.py
```

--

## 5. Module Contracts & Acceptance Criteria
### 5.1 Configuration (src/config.py)
Spec: Pydantic BaseSettings object reading from .env.

Required Fields:

OBSIDIAN_VAULT_PATH: Path (must validate directory exists or can be created).

LLM_API_KEY: str

LOOKBACK_HOURS: int (default: 24)

ARXIV_CATEGORIES: list[str] (default: ["cs.CL", "cs.AI", "cs.LG"])

ARXIV_KEYWORDS: list[str] (default: ["legal", "contract", "statute", "compliance", "judicial"])

RSS_FEEDS: list[HttpUrl] (default: LawNext, Artificial Lawyer, Legal IT Insider)

### 5.2 Ingestion Engine (src/ingestion/)
arXiv Fetcher (arxiv.py):

Hits http://export.arxiv.org/api/query.

Constructs parameter query: cat:<cat> AND (ti:<kw> OR abs:<kw>).

Filters entries using entry publication/update date against reference_time - timedelta(hours=lookback).

RSS Fetcher (rss.py):

Consumes target RSS endpoints via httpx and parses via feedparser.

Sanitizes HTML in summaries to raw text.

Returns a unified internal dataclass:

Python
class RawFeedItem(BaseModel):
    title: str
    url: str
    published_at: datetime
    summary: str
    source_name: str

### 5.3 LLM Extraction & Synthesis (src/synthesis/)
Data Contract (schemas.py):

```python
from pydantic import BaseModel, Field
from typing import List

class NewsItem(BaseModel):
    title: str
    url: str
    category: str = Field(description="e.g., Commercial, Litigation Tech, Regulatory")
    gist: str = Field(description="1-2 sentence core factual summary.")
    legal_impact: str = Field(description="Actionable takeaway for legal practitioners.")
    entities: List[str] = Field(description="Key companies, models, or platforms for wikilinking.")

class PaperItem(BaseModel):
    title: str
    url: str
    authors: List[str]
    core_contribution: str = Field(description="Methodological advance or benchmark result.")
    practical_takeaway: str = Field(description="Relevance to NLP or applied legal AI.")
    tags: List[str] = Field(description="Lower-case tags without hash symbol.")

class DailyBriefingData(BaseModel):
    date: str
    meta_takeaway: str
    commercial_news: List[NewsItem]
    research_papers: List[PaperItem]
```

Engine Logic (engine.py):

Accepts raw feed and paper lists.

Sends single structured prompt to LLM requesting JSON conforming to DailyBriefingData.

Handles parsing failures by raising a descriptive custom exception SynthesisValidationError.

### 5.4 Vault Writer & Renderer (src/output/)
Renderer (renderer.py):

Renders DailyBriefingData via Jinja2 into templates/briefing.md.j2.

Must generate valid YAML frontmatter containing: date, type: daily-briefing, and tags.

Must format entity references into Obsidian double-bracket links: [[Entity Name]].

Vault Writer (vault_writer.py):

Target Path: {OBSIDIAN_VAULT_PATH}/{YYYY-MM-DD}-ai-briefing.md.

Collision Policy:

If file exists and --force is not set: abort with warning or append timestamp.

Write atomically (write to temporary .tmp file in vault, then rename).

--

## 6. Phased Implementation Roadmap
Execute each phase sequentially. Do not begin a phase until the previous phase's tests pass 100%.

[ ] Phase 1: Project Scaffolding & Config

Setup pyproject.toml with dependencies.

Implement and test src/config.py.

[ ] Phase 2: Ingestion & HTTP Normalization

Implement RawFeedItem schema.

Test and implement rss.py with mock RSS XML fixtures.

Test and implement arxiv.py with mock Atom XML fixtures.

[ ] Phase 3: Synthesis & LLM Client

Implement Pydantic output schemas.

Test LLM prompt composition and response validation using mock clients.

[ ] Phase 4: Templating & Obsidian Writer

Test Jinja2 template rendering with sample DailyBriefingData.

Test file system operations using tmp_path.

[ ] Phase 5: CLI & End-to-End Test

Wire all parts into src/cli.py.

Write full end-to-end integration test (tests/test_e2e.py) running against external services.