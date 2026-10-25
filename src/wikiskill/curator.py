import json
import os
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import dspy

from .llm import WikiSkillLLMAdapter
from .marketplace import MarketplaceManager, bump_plugin_version
from .sync import GitHubSyncManager, _parse_frontmatter, ensure_agent_links

__all__ = [
    "CuratorLocalSessionSignature",
    "CuratorSandboxError",
    "CuratorSandboxTools",
    "WikiSkillCuratorAgent",
    "bump_plugin_version",
]


class CuratorSandboxError(PermissionError):
    """Raised when the Curator Sub-Agent attempts a file or git operation outside its allowed sandbox."""


class CuratorLocalSessionSignature(dspy.Signature):
    """Curate and consolidate newly extracted session failure patterns into `<project_dir>/.agents/{wiki,skills}` using the provided sandboxed tools.
    1. Inspect existing local skills/patterns and hub groups/plugins/open PRs first (`list_hub_groups_and_plugins`, `list_hub_skills_and_open_prs`).
    2. Consolidate overlapping patterns into existing domain skills (`skills/<name>/SKILL.md` and `PURPOSE.md`) rather than creating fragmented micro-skills.
    3. Distinguish which domain group each skill belongs to (`global` for universal workflows like git/file-editing, an existing domain group like `python` or `ai-engineer`, or a new kebab-case group if needed) and include `group: <group-name>` in the skill's YAML frontmatter and proposal object.
    4. If an unmerged local micro-skill is superseded by a broader domain skill, merge its rules/patterns and call `delete_unmerged_local_skill`.
    5. Return a JSON summary with keys `proposals` (list of updated/created skill objects including `group`) and `deleted_skills` (list of deleted skill names)."""

    session_id: str = dspy.InputField(desc="Session identifier")
    extracted_patterns_json: str = dspy.InputField(
        desc="JSON list of newly extracted/updated wiki patterns ({name, content})"
    )
    curation_summary_json: str = dspy.OutputField(
        desc="JSON object with keys 'proposals' and 'deleted_skills'"
    )


class CuratorSandboxTools:
    """Strictly sandboxed filesystem and hub Git/PR toolset for the Knowledge Curator Sub-Agent."""

    def __init__(
        self,
        project_dir: Path | str,
        hub_dir: Path | str | None = None,
        skills_dir: Path | str | None = None,
        wiki_dir: Path | str | None = None,
        allow_hub_mutations: bool = False,
        ensure_links: bool = True,
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        if ensure_links and not skills_dir and not wiki_dir:
            ensure_agent_links(self.project_dir)
        self.agents_dir = (self.project_dir / ".agents").resolve()
        self.skills_dir = Path(skills_dir or (self.agents_dir / "skills")).resolve()
        self.wiki_dir = Path(wiki_dir or (self.agents_dir / "wiki")).resolve()
        self.hub_dir = Path(
            os.path.expanduser(str(hub_dir or "~/.claude/wikiskill-hub"))
        ).resolve()
        self.allow_hub_mutations = allow_hub_mutations
        self.sync_manager = GitHubSyncManager(hub_dir=self.hub_dir)
        self.marketplace = MarketplaceManager(
            hub_dir=self.hub_dir, git_runner=self.sync_manager._run_git
        )

    @staticmethod
    def _validate_safe_name(name: str) -> str:
        cleaned = name.strip()
        if (
            not cleaned
            or "/" in cleaned
            or "\\" in cleaned
            or ".." in cleaned
            or cleaned.startswith(".")
        ):
            raise CuratorSandboxError(
                f"Sandbox violation: Invalid skill, group, or pattern identifier '{name}'."
            )
        return cleaned

    def _resolve_local_agents_path(self, relative_path: str) -> Path:
        """Resolve a path relative to `.agents/{skills,wiki}` and enforce strict containment."""
        rel_clean = relative_path.strip().replace("\\", "/").lstrip("/")
        if rel_clean.startswith(".agents/"):
            rel_clean = rel_clean.removeprefix(".agents/")

        if rel_clean.startswith("skills/"):
            candidate = (self.skills_dir / rel_clean.removeprefix("skills/")).resolve()
        elif rel_clean == "skills":
            candidate = self.skills_dir
        elif rel_clean.startswith("wiki/"):
            candidate = (self.wiki_dir / rel_clean.removeprefix("wiki/")).resolve()
        elif rel_clean == "wiki":
            candidate = self.wiki_dir
        else:
            candidate = (self.agents_dir / rel_clean).resolve()

        if not (
            candidate.is_relative_to(self.skills_dir)
            or candidate.is_relative_to(self.wiki_dir)
        ):
            raise CuratorSandboxError(
                f"Sandbox violation: Path '{relative_path}' resolves outside '.agents/skills' and '.agents/wiki'."
            )
        return candidate

    def _resolve_hub_global_path(self, relative_path: str) -> Path:
        """Resolve a path inside `<hub_dir>/{global,groups,wiki}` and enforce strict containment."""
        rel_clean = relative_path.strip().replace("\\", "/").lstrip("/")
        if not rel_clean.startswith(("global/", "groups/", "wiki/")):
            rel_clean = f"global/{rel_clean}"
        allowed_roots = (
            (self.hub_dir / "global" / "skills").resolve(),
            (self.hub_dir / "global" / "wiki").resolve(),
            (self.hub_dir / "groups").resolve(),
            (self.hub_dir / "wiki").resolve(),
        )
        candidate = (self.hub_dir / rel_clean).resolve()
        if not any(candidate.is_relative_to(root) for root in allowed_roots):
            raise CuratorSandboxError(
                f"Sandbox violation: Hub path '{relative_path}' resolves outside allowed marketplace directories."
            )
        return candidate

    def read_project_context(self) -> str:
        """Read root `CLAUDE.md` and `AGENTS.md` from the working repository (read-only project context)."""
        sections: list[str] = []
        for doc_name in ("CLAUDE.md", "AGENTS.md"):
            doc_path = (self.project_dir / doc_name).resolve()
            if doc_path.parent == self.project_dir and doc_path.is_file():
                try:
                    sections.append(
                        f"=== {doc_name} ===\n{doc_path.read_text(encoding='utf-8')}"
                    )
                except OSError:
                    continue
        return "\n\n".join(sections) if sections else "No CLAUDE.md or AGENTS.md found."

    def list_local_skills_and_patterns(self) -> dict[str, Any]:
        """List all skills and wiki patterns currently inside `<project_dir>/.agents/`."""
        skills: list[str] = []
        if self.skills_dir.exists():
            skills = sorted(
                d.name
                for d in self.skills_dir.iterdir()
                if d.is_dir() and (d / "SKILL.md").exists()
            )
        patterns: list[str] = []
        pat_dir = self.wiki_dir / "patterns"
        if pat_dir.exists():
            patterns = sorted(p.stem for p in pat_dir.glob("*.md"))
        return {"skills": skills, "patterns": patterns}

    def read_local_file(self, relative_path: str) -> str:
        """Read a file strictly inside `<project_dir>/.agents/{skills,wiki}`."""
        target = self._resolve_local_agents_path(relative_path)
        if not target.is_file():
            raise FileNotFoundError(f"Local file not found: {relative_path}")
        return target.read_text(encoding="utf-8")

    def write_local_file(self, relative_path: str, content: str) -> str:
        """Write or update a file strictly inside `<project_dir>/.agents/{skills,wiki}`."""
        target = self._resolve_local_agents_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {target.name} ({relative_path})"

    def _find_hub_skill_on_branch(
        self, skill_name: str, branch: str = "main"
    ) -> tuple[str, str | None, str | None] | None:
        """Locate `(group, version, skill_md_content)` for `skill_name` on `branch` in the hub."""
        if not (self.hub_dir / ".git").exists():
            return None

        # 1. Check group-scoped marketplace plugins first
        code, groups_out = self.sync_manager._run_git(
            ["ls-tree", "--name-only", f"{branch}:groups"]
        )
        if code == 0 and groups_out:
            for grp in groups_out.splitlines():
                grp = grp.strip()
                if not grp:
                    continue
                md_rel = (
                    f"groups/{grp}/plugins/{skill_name}/skills/{skill_name}/SKILL.md"
                )
                c_md, md_text = self.sync_manager._run_git(
                    ["show", f"{branch}:{md_rel}"]
                )
                if c_md == 0:
                    p_rel = f"groups/{grp}/plugins/{skill_name}/plugin.json"
                    c_p, p_text = self.sync_manager._run_git(
                        ["show", f"{branch}:{p_rel}"]
                    )
                    ver: str | None = None
                    if c_p == 0 and p_text:
                        try:
                            ver = json.loads(p_text).get("version")
                        except json.JSONDecodeError:
                            ver = None
                    return grp, ver, md_text

        # 2. Fallback to legacy global/skills/<skill_name>/SKILL.md
        c_leg, leg_text = self.sync_manager._run_git(
            ["show", f"{branch}:global/skills/{skill_name}/SKILL.md"]
        )
        if c_leg == 0:
            return "global", "1.0.0", leg_text

        return None

    def _is_skill_merged_on_hub_main(self, skill_name: str) -> bool:
        """Return True if `skill_name` is committed on `main` in the hub."""
        return self._find_hub_skill_on_branch(skill_name, branch="main") is not None

    def delete_unmerged_local_skill(self, skill_name: str) -> str:
        """Delete an unmerged local skill directory in `.agents/skills/<skill_name>`. Raises CuratorSandboxError if the skill is already merged on hub `main`."""
        safe_name = self._validate_safe_name(skill_name)
        if safe_name == "wikiskill":
            raise CuratorSandboxError(
                "Sandbox violation: Cannot delete core 'wikiskill' system skill."
            )
        if self._is_skill_merged_on_hub_main(safe_name):
            raise CuratorSandboxError(
                f"Sandbox violation: Skill '{safe_name}' is already merged on hub 'main' and cannot be deleted locally without a PR."
            )
        target_dir = self._resolve_local_agents_path(f"skills/{safe_name}")
        if target_dir.exists() and target_dir.is_dir():
            shutil.rmtree(target_dir)
            return f"Deleted unmerged local skill '{safe_name}'."
        return f"Local skill '{safe_name}' did not exist."

    def list_hub_groups_and_plugins(
        self, branch: str = "main"
    ) -> dict[str, list[dict[str, Any]]]:
        """Return mapping of `group_name -> list of plugin metadata` currently on `branch` in the hub."""
        groups_map: dict[str, list[dict[str, Any]]] = {}
        if not (self.hub_dir / ".git").exists():
            return groups_map

        seen_skills: set[str] = set()
        code, groups_out = self.sync_manager._run_git(
            ["ls-tree", "--name-only", f"{branch}:groups"]
        )
        if code == 0 and groups_out:
            for grp in sorted(
                line.strip() for line in groups_out.splitlines() if line.strip()
            ):
                groups_map.setdefault(grp, [])
                c_pl, plugins_out = self.sync_manager._run_git(
                    ["ls-tree", "--name-only", f"{branch}:groups/{grp}/plugins"]
                )
                if c_pl != 0 or not plugins_out:
                    continue
                for s_name in sorted(
                    line.strip() for line in plugins_out.splitlines() if line.strip()
                ):
                    p_rel = f"groups/{grp}/plugins/{s_name}/plugin.json"
                    c_p, p_text = self.sync_manager._run_git(
                        ["show", f"{branch}:{p_rel}"]
                    )
                    p_meta: dict[str, Any] = {
                        "name": s_name,
                        "group": grp,
                        "version": "1.0.0",
                        "description": "",
                    }
                    if c_p == 0 and p_text:
                        try:
                            loaded = json.loads(p_text)
                            if isinstance(loaded, dict):
                                p_meta.update(loaded)
                        except json.JSONDecodeError:
                            pass
                    groups_map[grp].append(p_meta)
                    seen_skills.add(s_name)

        # Include any legacy global/skills not yet in groups/
        c_leg, leg_out = self.sync_manager._run_git(
            ["ls-tree", "--name-only", f"{branch}:global/skills"]
        )
        if c_leg == 0 and leg_out:
            for s_name in sorted(
                line.strip() for line in leg_out.splitlines() if line.strip()
            ):
                if s_name in seen_skills:
                    continue
                groups_map.setdefault("global", []).append(
                    {
                        "name": s_name,
                        "group": "global",
                        "version": "1.0.0",
                        "description": "",
                    }
                )

        return groups_map

    def list_hub_skills_and_open_prs(self) -> dict[str, Any]:
        """List skills on hub `main`, group mappings, and any open Pull Requests on the remote hub repository."""
        groups_map = self.list_hub_groups_and_plugins(branch="main")
        hub_skills = sorted(
            {
                plugin["name"]
                for plugins in groups_map.values()
                for plugin in plugins
                if plugin.get("name")
            }
        )
        open_prs = self._fetch_open_prs()
        return {
            "hub_main_skills": hub_skills,
            "groups": groups_map,
            "open_prs": open_prs,
        }

    def read_hub_file(self, relative_path: str, branch: str = "main") -> str:
        """Read a file from `<hub_dir>/{global,groups,wiki}` on the specified git branch."""
        target = self._resolve_hub_global_path(relative_path)
        rel_to_hub = target.relative_to(self.hub_dir).as_posix()
        if (self.hub_dir / ".git").exists():
            code, content = self.sync_manager._run_git(
                ["show", f"{branch}:{rel_to_hub}"]
            )
            if code == 0:
                return content
            # If reading skills/<name>/SKILL.md, also search group plugins on branch
            if rel_to_hub.startswith("global/skills/") and rel_to_hub.endswith(
                "/SKILL.md"
            ):
                s_name = rel_to_hub.split("global/skills/")[1].split("/")[0]
                found = self._find_hub_skill_on_branch(s_name, branch=branch)
                if found and found[2] is not None:
                    return found[2]
        if target.is_file():
            return target.read_text(encoding="utf-8")
        raise FileNotFoundError(
            f"Hub file '{relative_path}' not found on branch '{branch}'."
        )

    def _fetch_open_prs(self) -> list[dict[str, Any]]:
        """Query `gh pr list` in `hub_dir` for open PRs."""
        if not (self.hub_dir / ".git").exists() or not shutil.which("gh"):
            return []
        try:
            res = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--state",
                    "open",
                    "--json",
                    "number,headRefName,title,url",
                ],
                cwd=str(self.hub_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, list):
                    return data
        except OSError, json.JSONDecodeError:
            pass
        return []

    def _ensure_cz_and_marketplace_manifests(self) -> None:
        """Ensure `.cz.toml`, `groups/<group>/{skills,plugins}.json`, and `.claude-plugin/marketplace.json` are up-to-date in `hub_dir`."""
        self.marketplace.ensure_cz_and_marketplace_manifests()

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
        """Create or update canonical branch `proposal/skill-<skill_name>` with Commitizen SemVer bump and group marketplace manifests."""
        if not self.allow_hub_mutations:
            raise CuratorSandboxError(
                "Sandbox violation: Hub mutations (branch push / PR upsert) are disabled in local curation mode."
            )

        safe_skill = self._validate_safe_name(skill_name)
        safe_group = self._validate_safe_name(group or "global")
        canonical_branch = f"proposal/skill-{safe_skill}"

        self.sync_manager.init_hub()
        self.sync_manager._run_git(["checkout", "main"])
        self.sync_manager.pull(prune=False)

        # Inspect existing skill on main to determine current version
        existing_on_main = self._find_hub_skill_on_branch(safe_skill, branch="main")
        current_ver = existing_on_main[1] if existing_on_main else None

        effective_commit_msg = commit_message or (
            f"fix(skill): update {safe_skill} skill"
            if existing_on_main
            else f"feat(skill): add {safe_skill} skill"
        )
        next_version = bump_plugin_version(current_ver, effective_commit_msg)

        open_prs = self._fetch_open_prs()
        matching_pr = next(
            (
                pr
                for pr in open_prs
                if pr.get("headRefName") == canonical_branch
                or str(pr.get("headRefName", "")).startswith(f"{canonical_branch}-")
            ),
            None,
        )
        target_branch = (
            str(matching_pr["headRefName"]) if matching_pr else canonical_branch
        )

        # Check out or create/reset the canonical proposal branch based on main
        self.sync_manager._run_git(["checkout", "-B", target_branch, "main"])

        fm = _parse_frontmatter(skill_md_content)
        desc = str(fm.get("description", f"Operational skill for {safe_skill}."))

        # 1. Write group-scoped plugin structure: groups/<safe_group>/plugins/<safe_skill>/
        self.marketplace.write_plugin_files(
            safe_skill=safe_skill,
            safe_group=safe_group,
            description=desc,
            version=next_version,
            skill_md_content=skill_md_content,
            purpose_md_content=purpose_md_content,
        )

        # 2. Write bundled pattern files
        for pat_slug, pat_content in patterns.items():
            clean_pat = self._validate_safe_name(pat_slug.removesuffix(".md"))
            for pat_prefix in ("global/wiki/patterns", "wiki/patterns"):
                pat_path = self._resolve_hub_global_path(f"{pat_prefix}/{clean_pat}.md")
                pat_path.parent.mkdir(parents=True, exist_ok=True)
                pat_path.write_text(pat_content, encoding="utf-8")
                self.sync_manager._run_git(["add", f"{pat_prefix}/{clean_pat}.md"])

        # 3. Update .cz.toml, groups/<group>/skills.json, and .claude-plugin/marketplace.json
        self._ensure_cz_and_marketplace_manifests()

        _, staged_diff = self.sync_manager._run_git(["diff", "--cached", "--name-only"])
        if not staged_diff or not staged_diff.strip():
            self.sync_manager._run_git(["checkout", "main"])
            return {
                "name": safe_skill,
                "group": safe_group,
                "version": next_version,
                "branch": target_branch,
                "action": "no_changes",
                "pr_url": matching_pr.get("url") if matching_pr else None,
                "success": True,
            }

        self.sync_manager._run_git(["commit", "-m", effective_commit_msg])

        push_code, _ = self.sync_manager._run_git(
            ["push", "-f", "-u", "origin", target_branch]
        )
        if push_code != 0:
            push_code, _ = self.sync_manager._run_git(
                ["push", "-f", "origin", target_branch]
            )

        pr_url: str | None = None
        action = "updated" if matching_pr else "created"

        if matching_pr and shutil.which("gh"):
            pr_number = str(matching_pr.get("number") or target_branch)
            edit_res = subprocess.run(
                [
                    "gh",
                    "pr",
                    "edit",
                    pr_number,
                    "--title",
                    pr_title,
                    "--body",
                    pr_body,
                ],
                cwd=str(self.hub_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            pr_url = (
                edit_res.stdout.strip()
                if edit_res.returncode == 0 and edit_res.stdout.strip()
                else matching_pr.get("url")
            )
        else:
            pr_url = self.sync_manager._create_pull_request(
                target_branch=target_branch,
                title=pr_title,
                body=pr_body,
                interactive=False,
            )

        self.sync_manager._run_git(["checkout", "main"])
        return {
            "name": safe_skill,
            "group": safe_group,
            "version": next_version,
            "type": "skill",
            "branch": target_branch,
            "action": action,
            "pr_url": pr_url,
            "description": pr_body,
            "success": True,
        }

    def configure_workspace_groups(
        self,
        groups: Sequence[str] = ("global",),
    ) -> dict[str, Any]:
        """Write `<project_dir>/.agents/{skills,plugins}.json` inheriting `global` plus requested domain groups from the hub without copying SKILL.md files."""
        validated_groups = [self._validate_safe_name(grp) for grp in groups]
        return self.marketplace.configure_workspace_groups(
            agents_dir=self.agents_dir, groups=validated_groups
        )

    def close_superseded_pr(self, branch_or_pr: str, reason: str) -> dict[str, Any]:
        """Close a superseded open Pull Request on the hub repository and delete its proposal branch."""
        if not self.allow_hub_mutations:
            raise CuratorSandboxError(
                "Sandbox violation: Hub mutations are disabled in local curation mode."
            )
        if shutil.which("gh"):
            res = subprocess.run(
                [
                    "gh",
                    "pr",
                    "close",
                    str(branch_or_pr),
                    "--comment",
                    reason,
                    "--delete-branch",
                ],
                cwd=str(self.hub_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            return {
                "closed": str(branch_or_pr),
                "success": res.returncode == 0,
            }
        return {"closed": str(branch_or_pr), "success": False}


class WikiSkillCuratorAgent:
    """Embedded DSPy ReAct sub-agent for sandboxing skill consolidation and hub PR curation."""

    def __init__(
        self,
        project_dir: Path | str,
        hub_dir: Path | str | None = None,
        skills_dir: Path | str | None = None,
        wiki_dir: Path | str | None = None,
        llm_adapter: WikiSkillLLMAdapter | None = None,
        max_iters: int = 10,
        react_runner: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.hub_dir = Path(
            os.path.expanduser(str(hub_dir or "~/.claude/wikiskill-hub"))
        ).resolve()
        self.skills_dir = Path(skills_dir).resolve() if skills_dir else None
        self.wiki_dir = Path(wiki_dir).resolve() if wiki_dir else None
        self.llm_adapter = llm_adapter
        self.max_iters = max_iters
        self.react_runner = react_runner

    def curate_local_session(
        self,
        session_id: str,
        extracted_patterns: list[dict[str, Any]],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Consolidate extracted patterns and skills inside `<project_dir>/.agents/` using hub `main` and open PRs as read context."""
        if not extracted_patterns:
            return {
                "status": "clean_session",
                "proposals": [],
                "deleted_skills": [],
            }

        tools = CuratorSandboxTools(
            project_dir=self.project_dir,
            hub_dir=self.hub_dir,
            skills_dir=self.skills_dir,
            wiki_dir=self.wiki_dir,
            allow_hub_mutations=False,
        )

        if self.react_runner is not None:
            out = self.react_runner(
                tools=tools,
                session_id=session_id,
                extracted_patterns=extracted_patterns,
                dry_run=dry_run,
            )
            return {
                "status": "dry_run" if dry_run else "success",
                "proposals": out.get("proposals", []),
                "deleted_skills": out.get("deleted_skills", []),
            }

        if self.llm_adapter is not None and not self.llm_adapter.mock:
            lm = self.llm_adapter.get_lm()
            react_tools: list[Callable[..., Any]] = [
                tools.read_project_context,
                tools.list_local_skills_and_patterns,
                tools.read_local_file,
                tools.list_hub_groups_and_plugins,
                tools.list_hub_skills_and_open_prs,
                tools.read_hub_file,
            ]
            if not dry_run:
                react_tools.extend(
                    [
                        tools.write_local_file,
                        tools.delete_unmerged_local_skill,
                    ]
                )
            react_module = dspy.ReAct(
                CuratorLocalSessionSignature,
                tools=react_tools,
                max_iters=self.max_iters,
            )
            with dspy.context(lm=lm):
                pred = react_module(
                    session_id=session_id,
                    extracted_patterns_json=json.dumps(extracted_patterns),
                )
            raw_json = getattr(pred, "curation_summary_json", "{}")
            try:
                parsed = (
                    raw_json
                    if isinstance(raw_json, dict)
                    else json.loads(str(raw_json))
                )
            except json.JSONDecodeError:
                parsed = {"proposals": [], "deleted_skills": []}
            return {
                "status": "dry_run" if dry_run else "success",
                "proposals": parsed.get("proposals", []),
                "deleted_skills": parsed.get("deleted_skills", []),
            }

        proposals = self._mock_curate_skills(
            tools=tools,
            session_id=session_id,
            extracted_patterns=extracted_patterns,
            dry_run=dry_run,
        )
        return {
            "status": "dry_run" if dry_run else "success",
            "proposals": proposals,
            "deleted_skills": [],
        }

    @staticmethod
    def _mock_curate_skills(
        tools: CuratorSandboxTools,
        session_id: str,
        extracted_patterns: list[dict[str, Any]],
        dry_run: bool,
    ) -> list[dict[str, Any]]:
        """Deterministic skill curation for `--mock` mode executed strictly via CuratorSandboxTools."""
        pattern_names = {p.get("name", "") for p in extracted_patterns}
        heuristic_specs = [
            (
                "edit-string-mismatch-loop",
                "file-editing",
                "global",
                "Best practices and guardrails for safe, exact file modifications.",
                [
                    "Always inspect the exact line range with View immediately before Edit.",
                    "Never guess whitespace, indentation, or newlines in old_string.",
                    "If an edit spans more than 30 lines or 50% of a file, use whole-file write instead of Edit.",
                ],
            ),
            (
                "unprefixed-python-runner-loop",
                "cli-tool-execution",
                "python",
                "Rules for executing python tools, test runners, and linters in the project environment.",
                [
                    "Always prefix python commands and test runners with 'uv run' (e.g. 'uv run pytest', 'uv run ruff check .').",
                    "Never invoke bare 'pytest' or 'python' directly in shell subshells.",
                ],
            ),
            (
                "missing-dependency-import-loop",
                "dependency-management",
                "python",
                "Standards for adding dependencies and organizing package imports.",
                [
                    "Add new project dependencies using 'uv add <package>'.",
                    "Ensure package imports are aligned with workspace root hierarchy.",
                ],
            ),
        ]

        proposals: list[dict[str, Any]] = []
        for pat_slug, skill_name, grp, desc, rules in heuristic_specs:
            if pat_slug not in pattern_names:
                continue
            proposal = {
                "action": "create",
                "name": skill_name,
                "group": grp,
                "description": desc,
                "status": "active",
                "rules": rules,
                "patterns_addressed": [pat_slug],
            }
            proposals.append(proposal)
            if not dry_run:
                rules_md = "\n".join(f"- {r}" for r in rules)
                skill_md = (
                    f"---\nname: {skill_name}\ngroup: {grp}\ndescription: {desc}\nstatus: active\n"
                    f"origin_session: {session_id}\npatterns_addressed:\n  - {pat_slug}\n---\n\n"
                    f"# Operational Rules\n\n## Trigger\nApply when working with {skill_name} operations in this codebase.\n\n"
                    f"## Rules\n{rules_md}\n"
                )
                purpose_md = (
                    f"# Purpose & Origin\n\n## Origin\nOrigin Session: {session_id}\nStatus: active\nGroup: {grp}\n\n"
                    f"## Patterns Addressed\n- `{pat_slug}`\n"
                )
                tools.write_local_file(f"skills/{skill_name}/SKILL.md", skill_md)
                tools.write_local_file(f"skills/{skill_name}/PURPOSE.md", purpose_md)

        return proposals

    @staticmethod
    def infer_skill_group(skill_name: str, fm: dict[str, Any]) -> str:
        """Infer the appropriate domain group for a skill from frontmatter or domain keywords."""
        explicit_grp = str(fm.get("group", "")).strip()
        if explicit_grp:
            return explicit_grp
        text = f"{skill_name} {fm.get('description', '')}".lower()
        if any(
            k in text
            for k in (
                "llm",
                "dspy",
                "agent",
                "claude",
                "antigravity",
                "wikiskill",
                "openrouter",
            )
        ):
            return "ai-engineer"
        if any(
            k in text
            for k in (
                "python",
                "pytest",
                "uv ",
                "dependency",
                "import",
                "refactor",
                "typeerror",
            )
        ):
            return "python"
        return "global"

    def sync_and_propose_hub_prs(
        self,
        direct: bool = False,
        interactive: bool = False,
    ) -> dict[str, Any]:
        """Reconcile `<project_dir>/.agents/` with `<hub_dir>`, push canonical `proposal/skill-<name>` branches, and create/update PRs without clobbering local skills."""
        tools = CuratorSandboxTools(
            project_dir=self.project_dir,
            hub_dir=self.hub_dir,
            skills_dir=self.skills_dir,
            wiki_dir=self.wiki_dir,
            allow_hub_mutations=True,
        )
        tools.sync_manager.init_hub()

        if direct:
            tools.sync_manager.sync_project_to_hub(self.project_dir, prune=False)
            return tools.sync_manager.push_patterns(
                direct=True, interactive=interactive
            )

        local_state = tools.list_local_skills_and_patterns()
        proposals: list[dict[str, Any]] = []

        for skill_name in local_state["skills"]:
            if skill_name == "wikiskill":
                continue
            skill_md = tools.read_local_file(f"skills/{skill_name}/SKILL.md")
            try:
                purpose_md = tools.read_local_file(f"skills/{skill_name}/PURPOSE.md")
            except FileNotFoundError:
                purpose_md = f"# Purpose: {skill_name}\n"

            try:
                hub_skill_md = tools.read_hub_file(
                    f"skills/{skill_name}/SKILL.md", branch="main"
                )
            except FileNotFoundError:
                hub_skill_md = None

            fm = _parse_frontmatter(skill_md)
            target_group = self.infer_skill_group(skill_name, fm)
            raw_pats = fm.get("patterns_addressed") or fm.get("patterns") or []
            if isinstance(raw_pats, str):
                pats = [raw_pats]
            else:
                pats = list(raw_pats)

            bundled_patterns: dict[str, str] = {}
            patterns_changed = False
            for pat in pats:
                clean_pat = pat.removesuffix(".md")
                try:
                    pat_text = tools.read_local_file(f"wiki/patterns/{clean_pat}.md")
                    bundled_patterns[clean_pat] = pat_text
                    try:
                        hub_pat = tools.read_hub_file(
                            f"wiki/patterns/{clean_pat}.md", branch="main"
                        )
                        if hub_pat.strip() != pat_text.strip():
                            patterns_changed = True
                    except FileNotFoundError:
                        patterns_changed = True
                except FileNotFoundError:
                    continue

            if (
                hub_skill_md is not None
                and hub_skill_md.strip() == skill_md.strip()
                and not patterns_changed
            ):
                continue

            change_label = "Updated" if hub_skill_md is not None else "New"
            commit_prefix = "fix(skill)" if hub_skill_md is not None else "feat(skill)"
            desc = fm.get("description", "Consolidated operational skill.")
            pr_body = (
                f"## WikiSkill Knowledge Evolution Proposal\n\n"
                f"### Proposed & Updated Skills\n"
                f"- **`{skill_name}`** (`{change_label}`, `group: {target_group}`, `status: {fm.get('status', 'active')}`):\n"
                f"  - **Purpose**: {desc}\n"
                f"  - **Patterns Addressed**: `{', '.join(pats)}`\n"
            )
            res = tools.upsert_skill_proposal_pr(
                skill_name=skill_name,
                skill_md_content=skill_md,
                purpose_md_content=purpose_md,
                patterns=bundled_patterns,
                pr_title=f"WikiSkill Proposal: {skill_name}",
                pr_body=pr_body,
                group=target_group,
                commit_message=f"{commit_prefix}: curate {skill_name} in {target_group} group",
            )
            if res.get("action") != "no_changes":
                proposals.append(res)

        if not proposals:
            return {
                "status": "no_changes",
                "message": "No new patterns or skills to push.",
                "success": True,
            }

        first = proposals[0]
        return {
            "status": "success",
            "mode": "pr",
            "branch": first.get("branch"),
            "pr_url": first.get("pr_url"),
            "description": first.get("description"),
            "proposals": proposals,
            "success": True,
        }
