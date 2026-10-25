# Technical Specification: Group-Scoped Plugin Marketplace, Commitizen SemVer & Sandboxed Curator Sub-Agent

## 1. System Overview & Architecture
This specification defines the **Zero-Copy Group-Scoped Plugin Marketplace** (`personal-wiki-skills`), **Commitizen-backed Semantic Versioning**, and the **WikiSkill Knowledge Curator Sub-Agent** (`WikiSkillCuratorAgent`).

All skills and failure patterns live centrally in the GitHub-backed marketplace repository, organized into **domain groups** (`global` plus specialized groups such as `python`, `ai-engineer`, `frontend`, etc.), with **one dual-compatible (Antigravity + Claude Code) plugin per skill**.

---

## 2. Marketplace Repository Layout

```text
<hub_dir>/ (~/.agents/wikiskill-hub or ~/.claude/wikiskill-hub)
├── .cz.toml                                    # Commitizen configuration for Conventional Commits
├── .claude-plugin/
│   └── marketplace.json                        # Top-level Claude Plugin Marketplace catalog
├── groups/
│   ├── global/                                 # Universal skills applicable to all repos
│   │   ├── skills.json                         # Group manifest pointing to each plugin's skills/ dir
│   │   └── plugins/
│   │       ├── file-editing/
│   │       │   ├── plugin.json                 # Canonical Antigravity & WikiSkill plugin manifest
│   │       │   ├── .claude-plugin/
│   │       │   │   └── plugin.json             # Claude Code Marketplace plugin manifest
│   │       │   └── skills/
│   │       │       └── file-editing/
│   │       │           ├── SKILL.md
│   │       │           └── PURPOSE.md
│   │       └── git-workflow/...
│   ├── python/                                 # Python/uv/pytest/refactoring skills
│   │   ├── skills.json
│   │   └── plugins/
│   │       └── <skill-name>/...
│   └── ai-engineer/                            # LLM/DSPy/agent harness skills
│       ├── skills.json
│       └── plugins/
│           └── <skill-name>/...
└── wiki/
    ├── index.md
    ├── logs.md
    └── patterns/
        └── <pattern-slug>.md
```

---

## 3. Commitizen & Conventional Commit SemVer Bumping

1. **Conventional Commit Parsing (`bump_plugin_version`)**:
   - Uses `commitizen` (`cz` conventional commits rules) to determine the semantic version increment for each individual plugin when updated:
     - `feat!:` or `BREAKING CHANGE:` $\to$ **MAJOR** (`1.0.0` $\to$ `2.0.0`)
     - `feat(...)` $\to$ **MINOR** (`1.0.0` $\to$ `1.1.0`)
     - `fix(...)`, `refactor(...)`, `docs(...)`, `chore(...)` $\to$ **PATCH** (`1.0.0` $\to$ `1.0.1`)
   - Newly created plugins start at `"1.0.0"`.
   - Both `groups/<group>/plugins/<skill>/plugin.json`, `groups/<group>/plugins/<skill>/.claude-plugin/plugin.json`, and `.claude-plugin/marketplace.json` are updated with the bumped version on the skill's canonical proposal branch (`proposal/skill-<name>`).
2. **Hub `.cz.toml`**:
   - Scaffolded in `<hub_dir>/.cz.toml` (`name = "cz_conventional_commits"`) to enforce Conventional Commit standards across the marketplace repository.

---

## 4. Public Interfaces & Component Contracts

### 4.1 SemVer Helper & `CuratorSandboxTools` (`src/wikiskill/curator.py`)
```python
def bump_plugin_version(current_version: str | None, commit_message: str) -> str:
    """Calculate the next SemVer version using Commitizen conventional commit rules."""


class CuratorSandboxTools:
    def list_hub_groups_and_plugins(
        self, branch: str = "main"
    ) -> dict[str, list[dict[str, Any]]]:
        """Return mapping of group_name -> list of plugin metadata ({name, description, version, group, patterns_addressed})."""

    def read_hub_skill(
        self, skill_name: str, group: str | None = None, branch: str = "main"
    ) -> str:
        """Read SKILL.md for a plugin from groups/<group>/plugins/<skill_name>/skills/<skill_name>/SKILL.md (with fallback to legacy global/skills/<skill_name>/SKILL.md)."""

    def upsert_skill_proposal_pr(
        self,
        skill_name: str,
        skill_md_content: str,
        purpose_md_content: str,
        patterns: dict[str, str],
        pr_title: str,
        pr_body: str,
        group: str = "global",
        commit_message: str | None = None,
    ) -> dict[str, Any]:
        """Write/update plugin under groups/<group>/plugins/<skill_name>/, bump version via Commitizen rules, update .claude-plugin/marketplace.json and groups/<group>/skills.json, push canonical branch proposal/skill-<skill_name>, and create/update PR."""

    def configure_workspace_groups(
        self,
        groups: Sequence[str] = ("global",),
    ) -> dict[str, Any]:
        """Generate <project_dir>/.agents/skills.json inheriting 'global' plus requested domain groups from the hub without copying SKILL.md files into the workspace."""
```

---

## 5. Acceptance Criteria (Given / When / Then)

1. **Commitizen SemVer Bumping & Dual-Manifest Marketplace Scaffolding**:
   - **Given** a skill `llm-configuration` assigned to `group="ai-engineer"`,
   - **When** `upsert_skill_proposal_pr(..., group="ai-engineer", commit_message="feat(skill): initial llm-configuration")` is called, followed by a second call with `commit_message="fix(skill): refine env var priority"` and a third call with `commit_message="feat(skill): add openrouter fallback"`,
   - **Then**:
     - Call 1 creates `groups/ai-engineer/plugins/llm-configuration/plugin.json` and `.claude-plugin/plugin.json` at version `"1.0.0"`.
     - Call 2 bumps version to `"1.0.1"` (`fix` $\to$ PATCH).
     - Call 3 bumps version to `"1.1.0"` (`feat` $\to$ MINOR).
     - `.claude-plugin/marketplace.json` lists `"source": "./groups/ai-engineer/plugins/llm-configuration"` with `"version": "1.1.0"` and `"group": "ai-engineer"`.
     - `groups/ai-engineer/skills.json` lists the plugin's `skills` directory in `entries`.
2. **Intelligent Group Classification & New Group Creation**:
   - **Given** existing groups `{"global": [...], "python": [...]}` and a new frontend skill `react-rendering` with `group="frontend"`,
   - **When** `upsert_skill_proposal_pr(..., group="frontend")` runs,
   - **Then** `groups/frontend/plugins/react-rendering/` and `groups/frontend/skills.json` are created and registered in `.claude-plugin/marketplace.json`.
3. **Zero-Copy Workspace Group Subscription (`configure_workspace_groups`)**:
   - **Given** a hub containing `global`, `python`, and `ai-engineer` groups,
   - **When** `configure_workspace_groups(groups=["frontend"])` is called on a workspace,
   - **Then** `<project_dir>/.agents/skills.json` is written with `"inherits"` pointing to the hub's `global/skills.json` and `frontend/skills.json` (excluding `ai-engineer` and `python`), with zero `SKILL.md` files copied into `<project_dir>`.
