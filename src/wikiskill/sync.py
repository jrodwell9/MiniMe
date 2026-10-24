import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML-style frontmatter from markdown content into a dictionary."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    fm_text = parts[1]
    result: dict[str, Any] = {}
    current_key: str | None = None

    for raw_line in fm_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Multiline list item (e.g., "  - item" or "- item")
        if line.startswith("- ") and current_key:
            item_val = line[2:].strip().strip('"').strip("'")
            if not isinstance(result.get(current_key), list):
                result[current_key] = []
            result[current_key].append(item_val)
            continue

        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")

            # Inline list (e.g., [item1, item2])
            if v.startswith("[") and v.endswith("]"):
                items = [
                    x.strip().strip('"').strip("'")
                    for x in v[1:-1].split(",")
                    if x.strip()
                ]
                result[k] = items
                current_key = k
            elif v == "" or v == "[]":
                result[k] = []
                current_key = k
            else:
                result[k] = v
                current_key = k
        else:
            current_key = None

    return result


class GitHubSyncManager:
    def __init__(
        self,
        hub_dir: Path | str | None = None,
        remote_url: str | None = None,
    ):
        self.hub_dir = Path(
            os.path.expanduser(hub_dir or "~/.claude/wikiskill-hub")
        ).resolve()
        self.remote_url = remote_url
        self._gh_fallback_preference: bool | None = None
        self._gh_notice_printed: bool = False

    def _run_git(self, args: list[str]) -> tuple[int, str]:
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(self.hub_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            return res.returncode, res.stdout.strip() or res.stderr.strip()
        except OSError as e:
            return 1, str(e)

    def init_hub(self, remote_url: str | None = None) -> bool:
        """Initialize the central hub repository structure and create initial commit if empty."""
        self.hub_dir.mkdir(parents=True, exist_ok=True)

        global_wiki = self.hub_dir / "global" / "wiki" / "patterns"
        global_skills = self.hub_dir / "global" / "skills"

        global_wiki.mkdir(parents=True, exist_ok=True)
        global_skills.mkdir(parents=True, exist_ok=True)

        # Initialize git if not present
        if not (self.hub_dir / ".git").exists():
            self._run_git(["init", "-b", "main"])

        # Create initial commit if no commits exist yet
        code, _ = self._run_git(["rev-parse", "--verify", "HEAD"])
        if code != 0:
            readme = self.hub_dir / "README.md"
            if not readme.exists():
                readme.write_text(
                    "# Central WikiSkill Knowledge Hub\n\nCompounding knowledge repository across workstations.\n",
                    encoding="utf-8",
                )
            gitignore = self.hub_dir / ".gitignore"
            if not gitignore.exists():
                gitignore.write_text(
                    ".processed_sessions.json\ndaemon_state.json\n*.tmp\n",
                    encoding="utf-8",
                )
            self._run_git(["add", "."])
            self._run_git(["commit", "-m", "Initial commit: WikiSkill knowledge hub"])
        else:
            gitignore = self.hub_dir / ".gitignore"
            if not gitignore.exists():
                gitignore.write_text(
                    ".processed_sessions.json\ndaemon_state.json\n*.tmp\n",
                    encoding="utf-8",
                )

        effective_remote = remote_url or self.remote_url
        if effective_remote:
            self._run_git(["remote", "remove", "origin"])
            self._run_git(["remote", "add", "origin", effective_remote])

        return True

    def sync_project_to_hub(
        self, project_dir: Path | str, prune: bool = False
    ) -> dict[str, Any]:
        """Promote universal engineering patterns and skills from a local project into the central global hub."""
        # Ensure hub is on clean main and synchronized with remote before copying
        self._run_git(["checkout", "main"])
        self.pull(prune=prune)

        p_dir = Path(project_dir).resolve()
        global_wiki = self.hub_dir / "global" / "wiki" / "patterns"
        global_skills = self.hub_dir / "global" / "skills"

        global_wiki.mkdir(parents=True, exist_ok=True)
        global_skills.mkdir(parents=True, exist_ok=True)

        local_wiki_patterns = p_dir / ".claude" / "wiki" / "patterns"
        local_skills = p_dir / ".claude" / "skills"

        synced_patterns = []
        if local_wiki_patterns.exists():
            for f in local_wiki_patterns.glob("*.md"):
                dest = global_wiki / f.name
                shutil.copy2(f, dest)
                synced_patterns.append(f.stem)

        synced_skills = []
        if local_skills.exists():
            for s_dir in local_skills.iterdir():
                if s_dir.is_dir() and (s_dir / "SKILL.md").exists():
                    dest_dir = global_skills / s_dir.name
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    for item in s_dir.iterdir():
                        if item.is_file():
                            if (
                                item.name == "SKILL.md"
                                and (dest_dir / "SKILL.md").exists()
                            ):
                                local_text = item.read_text(encoding="utf-8")
                                dest_text = (dest_dir / "SKILL.md").read_text(
                                    encoding="utf-8"
                                )
                                local_fm = _parse_frontmatter(local_text)
                                dest_fm = _parse_frontmatter(dest_text)

                                merged_origin = local_fm.get(
                                    "origin_session"
                                ) or dest_fm.get("origin_session")
                                merged_status = local_fm.get("status") or dest_fm.get(
                                    "status"
                                )
                                local_pats = (
                                    local_fm.get("patterns_addressed")
                                    or local_fm.get("patterns")
                                    or []
                                )
                                if isinstance(local_pats, str):
                                    local_pats = [local_pats]
                                dest_pats = (
                                    dest_fm.get("patterns_addressed")
                                    or dest_fm.get("patterns")
                                    or []
                                )
                                if isinstance(dest_pats, str):
                                    dest_pats = [dest_pats]
                                merged_pats = list(
                                    dict.fromkeys(list(local_pats) + list(dest_pats))
                                )

                                if dest_fm and (
                                    (
                                        merged_origin
                                        and not local_fm.get("origin_session")
                                    )
                                    or (merged_status and not local_fm.get("status"))
                                    or (
                                        merged_pats
                                        and not local_fm.get("patterns_addressed")
                                    )
                                ):
                                    pats_yaml = "\n".join(
                                        f"  - {p}" for p in merged_pats
                                    )
                                    pats_block = (
                                        f"\npatterns_addressed:\n{pats_yaml}"
                                        if merged_pats
                                        else ""
                                    )
                                    origin_line = (
                                        f"\norigin_session: {merged_origin}"
                                        if merged_origin
                                        else ""
                                    )
                                    status_line = (
                                        f"\nstatus: {merged_status}"
                                        if merged_status
                                        else ""
                                    )

                                    body = (
                                        local_text.split("---", 2)[2]
                                        if local_text.startswith("---")
                                        and len(local_text.split("---", 2)) >= 3
                                        else local_text
                                    )
                                    merged_content = f"""---
name: {local_fm.get("name", s_dir.name)}
description: {local_fm.get("description", dest_fm.get("description", ""))}
{status_line.strip()}
{origin_line.strip()}
{pats_block.strip()}
---
{body.lstrip()}"""
                                    (dest_dir / "SKILL.md").write_text(
                                        merged_content.strip() + "\n", encoding="utf-8"
                                    )
                                    continue

                            if (
                                item.name == "PURPOSE.md"
                                and (dest_dir / "PURPOSE.md").exists()
                            ):
                                local_text = item.read_text(encoding="utf-8")
                                dest_text = (dest_dir / "PURPOSE.md").read_text(
                                    encoding="utf-8"
                                )
                                if (
                                    "Origin Session:" not in local_text
                                    and "Origin Session:" in dest_text
                                ):
                                    # Keep existing rich PURPOSE.md from hub
                                    continue

                            shutil.copy2(item, dest_dir / item.name)
                    synced_skills.append(s_dir.name)

        return {
            "status": "success",
            "synced_patterns": synced_patterns,
            "synced_skills": synced_skills,
        }

    def sync_hub_to_project(
        self, project_dir: Path | str, prune: bool = False
    ) -> dict[str, Any]:
        """Sync global skills and patterns from central hub into a local repository."""
        p_dir = Path(project_dir).resolve()
        local_skills = p_dir / ".claude" / "skills"
        local_wiki_patterns = p_dir / ".claude" / "wiki" / "patterns"

        local_skills.mkdir(parents=True, exist_ok=True)
        local_wiki_patterns.mkdir(parents=True, exist_ok=True)

        applied_skills = []
        valid_skills = {"wikiskill"}
        valid_patterns = set()

        # Copy global skills to project
        global_skills = self.hub_dir / "global" / "skills"
        if global_skills.exists():
            for s_dir in global_skills.iterdir():
                if s_dir.is_dir() and (s_dir / "SKILL.md").exists():
                    valid_skills.add(s_dir.name)
                    dest_dir = local_skills / s_dir.name
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    for item in s_dir.iterdir():
                        if item.is_file():
                            shutil.copy2(item, dest_dir / item.name)
                    applied_skills.append(s_dir.name)

        # Collect valid patterns from hub
        global_patterns = self.hub_dir / "global" / "wiki" / "patterns"
        if global_patterns.exists():
            for f in global_patterns.glob("*.md"):
                valid_patterns.add(f.name)

        pruned_skills = []
        pruned_patterns = []
        if prune:
            for s_dir in list(local_skills.iterdir()):
                if s_dir.is_dir() and s_dir.name not in valid_skills:
                    shutil.rmtree(s_dir)
                    pruned_skills.append(s_dir.name)

            for f in list(local_wiki_patterns.glob("*.md")):
                if f.name not in valid_patterns:
                    f.unlink()
                    pruned_patterns.append(f.stem)

        return {
            "status": "success",
            "applied_skills": applied_skills,
            "pruned_skills": pruned_skills,
            "pruned_patterns": pruned_patterns,
        }

    def pull(self, prune: bool = False) -> bool:
        """Pull latest changes from remote Git hub."""
        if prune:
            self._run_git(["fetch", "--prune", "origin"])
            code, branches_out = self._run_git(["branch"])
            if code == 0:
                for line in branches_out.splitlines():
                    b_name = line.strip().lstrip("*").strip()
                    if b_name.startswith("proposal/"):
                        self._run_git(["branch", "-D", b_name])
        code, _ = self._run_git(["pull", "origin", "main"])
        return code == 0

    def _get_remote_owner_repo(self) -> tuple[str, str] | None:
        """Parse owner and repo name from remote origin URL."""
        url = self.remote_url or ""
        if not url:
            code, git_url = self._run_git(["remote", "get-url", "origin"])
            if code == 0 and git_url:
                url = git_url
        url = url.strip()
        if not url:
            return None

        cleaned = url.removesuffix(".git")
        if "github.com/" in cleaned:
            parts = cleaned.split("github.com/", 1)[1].split("/")
            if len(parts) >= 2:
                return (parts[0], parts[1])
        elif "github.com:" in cleaned:
            parts = cleaned.split("github.com:", 1)[1].split("/")
            if len(parts) >= 2:
                return (parts[0], parts[1])
        return None

    def _get_file_content(self, filepath: str, branch: str | None = None) -> str | None:
        """Read file content from a specific branch or local hub filesystem."""
        if branch:
            code, content = self._run_git(["show", f"{branch}:{filepath}"])
            if code == 0:
                return content
        local_path = self.hub_dir / filepath
        if local_path.exists():
            try:
                return local_path.read_text(encoding="utf-8")
            except OSError:
                pass
        return None

    def _generate_proposal_description(
        self,
        target_branch: str,
        base_branch: str = "main",
    ) -> str:
        """Inspect branch diff and generate detailed markdown changelog for PR."""
        code, diff_names = self._run_git(
            ["diff", "--name-status", f"{base_branch}..{target_branch}"]
        )
        if (code != 0 or not diff_names) and target_branch:
            code, diff_names = self._run_git(["diff", "--cached", "--name-status"])
        if code != 0 or not diff_names:
            code, diff_names = self._run_git(
                ["diff", "--name-status", f"{base_branch}...{target_branch}"]
            )

        skills_seen: set[str] = set()
        patterns_seen: set[str] = set()
        skills_details: list[dict[str, Any]] = []
        patterns_details: list[dict[str, Any]] = []

        if diff_names:
            for line in diff_names.strip().splitlines():
                parts = line.split(maxsplit=1)
                if len(parts) < 2:
                    continue
                status_code, filepath = parts[0], parts[1].replace("\\", "/")
                if "global/skills/" in filepath:
                    skill_name = filepath.split("global/skills/")[1].split("/")[0]
                    if skill_name not in skills_seen:
                        skills_seen.add(skill_name)
                        skill_rel_md = f"global/skills/{skill_name}/SKILL.md"
                        content = self._get_file_content(
                            skill_rel_md, branch=target_branch
                        )
                        desc = "Operational skill synthesized from session patterns."
                        origin = None
                        patterns: list[str] = []
                        status = "active"
                        if content:
                            fm = _parse_frontmatter(content)
                            if fm.get("description"):
                                desc = fm["description"]
                            if fm.get("origin_session"):
                                origin = fm["origin_session"]
                            if fm.get("status"):
                                status = fm["status"]
                            raw_pats = (
                                fm.get("patterns_addressed") or fm.get("patterns") or []
                            )
                            if isinstance(raw_pats, str):
                                patterns = [raw_pats]
                            else:
                                patterns = list(raw_pats)
                        skills_details.append(
                            {
                                "name": skill_name,
                                "description": desc,
                                "origin_session": origin,
                                "patterns_addressed": patterns,
                                "status": status,
                                "change_type": "New"
                                if status_code == "A"
                                else "Updated",
                            }
                        )

                elif "global/wiki/patterns/" in filepath:
                    pat_name = filepath.split("global/wiki/patterns/")[1]
                    if pat_name not in patterns_seen:
                        patterns_seen.add(pat_name)
                        pat_rel = f"global/wiki/patterns/{pat_name}"
                        pat_text = self._get_file_content(pat_rel, branch=target_branch)
                        summary = "Diagnosed recurring failure pattern."
                        fix = None
                        if pat_text:
                            lines = pat_text.splitlines()
                            for i, l in enumerate(lines):
                                if any(
                                    h in l
                                    for h in [
                                        "## Description",
                                        "## Summary",
                                        "## Diagnosis",
                                    ]
                                ):
                                    for j in range(i + 1, min(i + 5, len(lines))):
                                        if lines[j].strip() and not lines[j].startswith(
                                            "#"
                                        ):
                                            summary = lines[j].strip()
                                            break
                                if any(
                                    h in l
                                    for h in [
                                        "## Recommended Fix",
                                        "## Prevention",
                                        "## Fix",
                                    ]
                                ):
                                    for j in range(i + 1, min(i + 5, len(lines))):
                                        if lines[j].strip() and not lines[j].startswith(
                                            "#"
                                        ):
                                            fix = lines[j].strip()
                                            break
                        patterns_details.append(
                            {
                                "filename": pat_name,
                                "summary": summary,
                                "fix": fix,
                                "change_type": "New"
                                if status_code == "A"
                                else "Updated",
                            }
                        )

        md_lines = [
            "## WikiSkill Knowledge Evolution Proposal",
            "",
            "This proposal introduces operational skills and failure pattern diagnoses synthesized from agent execution sessions.",
            "",
        ]

        if skills_details:
            md_lines.append("### Proposed & Updated Skills")
            for s in skills_details:
                md_lines.append(
                    f"- **`{s['name']}`** (`{s['change_type']}`, `status: {s['status']}`):"
                )
                md_lines.append(f"  - **Purpose**: {s['description']}")
                if s["patterns_addressed"]:
                    md_lines.append(
                        f"  - **Patterns Addressed**: `{', '.join(s['patterns_addressed'])}`"
                    )
                if s["origin_session"]:
                    md_lines.append(f"  - **Origin Session**: `{s['origin_session']}`")
            md_lines.append("")

        if patterns_details:
            md_lines.append("### Diagnosed Failure Patterns")
            for p in patterns_details:
                md_lines.append(f"- **`{p['filename']}`** (`{p['change_type']}`):")
                md_lines.append(f"  - **Summary**: {p['summary']}")
                if p["fix"]:
                    md_lines.append(f"  - **Recommended Fix**: {p['fix']}")
            md_lines.append("")

        md_lines.extend(
            [
                "---",
                "### Review Instructions",
                "1. Review the proposed rules in `global/skills/` and patterns in `global/wiki/patterns/`.",
                "2. Merge this Pull Request to incorporate these practices into the global standard library.",
                "3. If closed or rejected without merging, `wikiskill sync --pull --prune` on workstations will discard the candidate skills.",
            ]
        )

        return "\n".join(md_lines)

    def _ensure_gh_ready(self, interactive: bool = True) -> tuple[bool, str]:
        """Ensure gh CLI is installed and authenticated, prompting for login or web fallback."""
        gh_path = shutil.which("gh")
        is_interactive = (
            interactive
            and sys.stdin is not None
            and hasattr(sys.stdin, "isatty")
            and sys.stdin.isatty()
        )

        if not gh_path:
            if not self._gh_notice_printed:
                print(
                    "\n[Notice] GitHub CLI ('gh') is not installed or not found on PATH."
                )
                print(
                    "Automated Pull Request creation requires 'gh' (https://cli.github.com/)."
                )
                print("To install 'gh':")
                print("  - Windows: winget install --id GitHub.cli")
                print("  - macOS:   brew install gh")
                print("  - Linux:   sudo apt install gh / dnf install gh")
                print("After installing, run 'gh auth login' to authenticate.\n")
                self._gh_notice_printed = True

            if is_interactive:
                try:
                    choice = (
                        input(
                            "Would you like to proceed with web-based PR creation links? (y/n) [y]: "
                        )
                        .strip()
                        .lower()
                    )
                    if choice in ("n", "no"):
                        print(
                            "\nPush aborted. Install 'gh' and re-run 'wikiskill sync --push' to create PRs automatically.\n"
                        )
                        return False, "missing_gh"
                    return True, "web"
                except EOFError, KeyboardInterrupt:
                    return False, "missing_gh"
            else:
                return True, "web"

        # gh is installed, check auth status
        auth_res = subprocess.run(
            ["gh", "auth", "status"],
            cwd=str(self.hub_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        if auth_res.returncode == 0:
            return True, "cli"

        # gh is installed but not authenticated
        if not self._gh_notice_printed:
            print("\n[Notice] GitHub CLI ('gh') is installed but not authenticated.")
            self._gh_notice_printed = True

        if is_interactive:
            try:
                login_choice = (
                    input(
                        "Would you like to run 'gh auth login' now to authenticate? (y/n) [y]: "
                    )
                    .strip()
                    .lower()
                )
                if login_choice not in ("n", "no"):
                    print("\nLaunching 'gh auth login'...\n")
                    subprocess.run(["gh", "auth", "login"], check=False)
                    # Re-check status
                    recheck = subprocess.run(
                        ["gh", "auth", "status"],
                        cwd=str(self.hub_dir),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if recheck.returncode == 0:
                        print("Successfully authenticated with GitHub CLI!\n")
                        return True, "cli"
                    else:
                        print("Authentication was not completed.")

                # If login declined or failed, prompt for web fallback
                web_choice = (
                    input(
                        "Would you like to proceed with web-based PR creation links instead? (y/n) [y]: "
                    )
                    .strip()
                    .lower()
                )
                if web_choice in ("n", "no"):
                    print(
                        "\nPush aborted. Run 'gh auth login' and re-run 'wikiskill sync --push' to create PRs automatically.\n"
                    )
                    return False, "unauthenticated"
                return True, "web"
            except EOFError, KeyboardInterrupt:
                return False, "unauthenticated"
        else:
            return True, "web"

    def _create_pull_request(
        self,
        target_branch: str,
        title: str,
        body: str,
        mode: str = "cli",
        interactive: bool = True,
    ) -> str | None:
        """Create a Pull Request via gh CLI, or fallback to prefilled web URL."""
        if mode == "cli" and not shutil.which("gh"):
            ready, resolved_mode = self._ensure_gh_ready(interactive=interactive)
            if not ready:
                return None
            mode = resolved_mode

        if mode == "cli":
            try:
                gh_res = subprocess.run(
                    [
                        "gh",
                        "pr",
                        "create",
                        "--title",
                        title,
                        "--body",
                        body,
                        "--head",
                        target_branch,
                        "--base",
                        "main",
                    ],
                    cwd=str(self.hub_dir),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if gh_res.returncode == 0 and gh_res.stdout.strip():
                    return gh_res.stdout.strip()
                elif gh_res.returncode != 0:
                    err_msg = gh_res.stderr.strip() or gh_res.stdout.strip()
                    if err_msg and not self._gh_notice_printed:
                        print(
                            f"\n[Notice] 'gh pr create' could not create PR automatically: {err_msg}\n"
                        )
                        self._gh_notice_printed = True
            except (OSError, subprocess.SubprocessError) as e:
                if not self._gh_notice_printed:
                    print(f"\n[Notice] Error executing 'gh' CLI: {e}\n")
                    self._gh_notice_printed = True

        # Fallback to Web Compare / PR creation link
        owner_repo = self._get_remote_owner_repo()
        if owner_repo:
            owner, repo = owner_repo
            return (
                f"https://github.com/{owner}/{repo}/compare/main...{target_branch}"
                f"?expand=1&title={quote_plus(title)}&body={quote_plus(body)}"
            )

        return None

    def push_patterns(
        self,
        commit_message: str = "Auto-sync WikiSkill patterns",
        direct: bool = False,
        branch_name: str | None = None,
        interactive: bool = True,
    ) -> dict[str, Any]:
        """Stage, commit, and push hub updates with PR branch gating per skill."""
        # Ensure hub main is clean and up to date with remote
        self._run_git(["checkout", "main"])
        self._run_git(["pull", "origin", "main"])

        code, status_out = self._run_git(["status", "--porcelain", "-uall"])
        if not status_out or not status_out.strip():
            return {
                "status": "no_changes",
                "message": "No new patterns or skills to push.",
                "success": True,
            }

        if direct:
            self._run_git(["add", "."])
            self._run_git(["commit", "-m", commit_message])
            code, _ = self._run_git(["push", "-u", "origin", "main"])
            if code != 0:
                code, _ = self._run_git(["push", "origin", "main"])
            return {
                "status": "success",
                "mode": "direct",
                "branch": "main",
                "success": code == 0,
            }

        # Check gh CLI availability and authentication before creating candidate branches
        ready, pr_mode = self._ensure_gh_ready(interactive=interactive)
        if not ready:
            return {
                "status": "aborted",
                "message": "Push aborted. Authenticate with GitHub CLI ('gh auth login') or install 'gh' and re-run to create Pull Requests automatically.",
                "success": False,
            }

        # PR Gated flow: create candidate branch and PR per skill
        ts = time.strftime("%Y%m%d-%H%M%S")

        # 1. Identify changed skills and changed patterns strictly from git status
        skills_changed: list[str] = []
        patterns_changed: list[str] = []

        for line in status_out.splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) < 2:
                continue
            path_str = parts[1].replace("\\", "/")
            if "global/skills/" in path_str:
                skill_name = path_str.split("global/skills/")[1].split("/")[0]
                if skill_name not in skills_changed:
                    skills_changed.append(skill_name)
            elif "global/wiki/patterns/" in path_str:
                pat_name = Path(path_str).name
                if pat_name not in patterns_changed:
                    patterns_changed.append(pat_name)

        if not skills_changed and not patterns_changed:
            return {
                "status": "no_changes",
                "message": "No new patterns or skills to push.",
                "success": True,
            }

        proposals: list[dict[str, Any]] = []
        claimed_patterns: set[str] = set()

        # 2. Create isolated PR per skill
        for skill_name in skills_changed:
            target_branch = (
                f"{branch_name}-{skill_name}"
                if branch_name and len(skills_changed) > 1
                else (branch_name or f"proposal/skill-{skill_name}-{ts}")
            )

            # Ensure starting from clean main
            self._run_git(["checkout", "main"])
            # Create candidate branch
            self._run_git(["checkout", "-b", target_branch])

            # Find associated patterns addressed by this skill
            skill_md = self.hub_dir / "global" / "skills" / skill_name / "SKILL.md"
            associated_patterns: list[str] = []
            if skill_md.exists():
                content = skill_md.read_text(encoding="utf-8")
                fm = _parse_frontmatter(content)
                raw_pats = fm.get("patterns_addressed") or fm.get("patterns") or []
                if isinstance(raw_pats, str):
                    pats = [raw_pats]
                else:
                    pats = list(raw_pats)
                for p in pats:
                    p_fname = p if p.endswith(".md") else f"{p}.md"
                    associated_patterns.append(p_fname)

            # Stage this skill folder
            skill_rel = f"global/skills/{skill_name}"
            self._run_git(["add", skill_rel])

            # Stage associated pattern files if present
            for pat_fname in associated_patterns:
                pat_rel = f"global/wiki/patterns/{pat_fname}"
                if (self.hub_dir / pat_rel).exists():
                    self._run_git(["add", pat_rel])
                    claimed_patterns.add(pat_fname)

            # Verify actual staged differences exist
            _, staged_diff = self._run_git(["diff", "--cached", "--name-only"])
            if not staged_diff or not staged_diff.strip():
                self._run_git(["checkout", "main"])
                self._run_git(["branch", "-D", target_branch])
                continue

            # Commit staged changes to candidate branch first
            c_msg = f"feat(skill): propose {skill_name} skill"
            self._run_git(["commit", "-m", c_msg])

            # Generate proposal description strictly for this branch's committed delta
            proposal_desc = self._generate_proposal_description(
                target_branch, base_branch="main"
            )

            # Push branch
            push_code, _ = self._run_git(["push", "-u", "origin", target_branch])
            if push_code != 0:
                push_code, _ = self._run_git(["push", "origin", target_branch])

            # Create PR
            pr_title = f"WikiSkill Proposal: {skill_name}"
            pr_url = self._create_pull_request(
                target_branch=target_branch,
                title=pr_title,
                body=proposal_desc,
                mode=pr_mode,
                interactive=interactive,
            )

            proposals.append(
                {
                    "name": skill_name,
                    "type": "skill",
                    "branch": target_branch,
                    "pr_url": pr_url,
                    "description": proposal_desc,
                    "success": push_code == 0,
                }
            )

            # Switch back to main
            self._run_git(["checkout", "main"])

        # 3. Create standalone PR for any unclaimed pattern updates
        unclaimed_patterns = [p for p in patterns_changed if p not in claimed_patterns]
        if unclaimed_patterns:
            pat_branch = (
                f"{branch_name}-patterns"
                if branch_name and proposals
                else (branch_name or f"proposal/patterns-{ts}")
            )
            self._run_git(["checkout", "main"])
            self._run_git(["checkout", "-b", pat_branch])

            for pat_fname in unclaimed_patterns:
                pat_rel = f"global/wiki/patterns/{pat_fname}"
                if (self.hub_dir / pat_rel).exists():
                    self._run_git(["add", pat_rel])

            _, staged_diff = self._run_git(["diff", "--cached", "--name-only"])
            if staged_diff and staged_diff.strip():
                # Commit staged changes to pattern candidate branch first
                self._run_git(
                    ["commit", "-m", "docs(patterns): propose failure patterns update"]
                )
                # Generate proposal description strictly for pattern updates
                pat_desc = self._generate_proposal_description(
                    pat_branch, base_branch="main"
                )
                push_code, _ = self._run_git(["push", "-u", "origin", pat_branch])
                if push_code != 0:
                    push_code, _ = self._run_git(["push", "origin", pat_branch])

                pr_url = self._create_pull_request(
                    target_branch=pat_branch,
                    title=f"WikiSkill Patterns Update: {ts}",
                    body=pat_desc,
                    mode=pr_mode,
                    interactive=interactive,
                )

                proposals.append(
                    {
                        "name": "patterns",
                        "type": "patterns",
                        "branch": pat_branch,
                        "pr_url": pr_url,
                        "description": pat_desc,
                        "success": push_code == 0,
                    }
                )

            self._run_git(["checkout", "main"])

        # Clean any remaining untracked artifacts from working directory on main
        self._run_git(["clean", "-fd"])
        self._run_git(["checkout", "."])

        if not proposals:
            return {
                "status": "no_changes",
                "message": "No new patterns or skills to push.",
                "success": True,
            }

        # Return result summary
        first_prop = proposals[0]
        return {
            "status": "success",
            "mode": "pr",
            "branch": first_prop.get("branch"),
            "pr_url": first_prop.get("pr_url"),
            "description": first_prop.get("description"),
            "proposals": proposals,
            "success": all(p.get("success", True) for p in proposals),
        }
