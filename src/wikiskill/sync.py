import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .claude_log_adapter import sanitize_project_path


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
        """Initialize the central hub repository structure."""
        self.hub_dir.mkdir(parents=True, exist_ok=True)

        global_wiki = self.hub_dir / "global" / "wiki" / "patterns"
        global_skills = self.hub_dir / "global" / "skills"
        projects_dir = self.hub_dir / "projects"

        global_wiki.mkdir(parents=True, exist_ok=True)
        global_skills.mkdir(parents=True, exist_ok=True)
        projects_dir.mkdir(parents=True, exist_ok=True)

        # Initialize git if not present
        if not (self.hub_dir / ".git").exists():
            self._run_git(["init", "-b", "main"])

        effective_remote = remote_url or self.remote_url
        if effective_remote:
            self._run_git(["remote", "remove", "origin"])
            self._run_git(["remote", "add", "origin", effective_remote])

        return True

    def sync_project_to_hub(self, project_dir: Path | str) -> dict[str, Any]:
        """Sync a local repository's .claude/wiki and .claude/skills into the central hub."""
        p_dir = Path(project_dir).resolve()
        slug = sanitize_project_path(p_dir)

        proj_hub = self.hub_dir / "projects" / slug
        proj_hub_wiki = proj_hub / "wiki" / "patterns"
        proj_hub_skills = proj_hub / "skills"

        proj_hub_wiki.mkdir(parents=True, exist_ok=True)
        proj_hub_skills.mkdir(parents=True, exist_ok=True)

        local_wiki_patterns = p_dir / ".claude" / "wiki" / "patterns"
        local_skills = p_dir / ".claude" / "skills"

        synced_patterns = []
        if local_wiki_patterns.exists():
            for f in local_wiki_patterns.glob("*.md"):
                dest = proj_hub_wiki / f.name
                shutil.copy2(f, dest)
                synced_patterns.append(f.stem)

                # Promote universal engineering patterns to global
                if any(
                    k in f.stem
                    for k in (
                        "edit-string",
                        "python-runner",
                        "dependency",
                        "clean-session",
                        "in-flight",
                    )
                ):
                    global_dest = self.hub_dir / "global" / "wiki" / "patterns" / f.name
                    global_dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, global_dest)

        synced_skills = []
        if local_skills.exists():
            for s_dir in local_skills.iterdir():
                if s_dir.is_dir() and (s_dir / "SKILL.md").exists():
                    dest_dir = proj_hub_skills / s_dir.name
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    for item in s_dir.iterdir():
                        if item.is_file():
                            shutil.copy2(item, dest_dir / item.name)
                    synced_skills.append(s_dir.name)

        return {
            "status": "success",
            "project_slug": slug,
            "synced_patterns": synced_patterns,
            "synced_skills": synced_skills,
        }

    def sync_hub_to_project(self, project_dir: Path | str) -> dict[str, Any]:
        """Sync global and hub project skills back into a local repository."""
        p_dir = Path(project_dir).resolve()
        local_skills = p_dir / ".claude" / "skills"
        local_wiki_patterns = p_dir / ".claude" / "wiki" / "patterns"

        local_skills.mkdir(parents=True, exist_ok=True)
        local_wiki_patterns.mkdir(parents=True, exist_ok=True)

        applied_skills = []
        # Copy global skills to project
        global_skills = self.hub_dir / "global" / "skills"
        if global_skills.exists():
            for s_dir in global_skills.iterdir():
                if s_dir.is_dir() and (s_dir / "SKILL.md").exists():
                    dest_dir = local_skills / s_dir.name
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    for item in s_dir.iterdir():
                        if item.is_file():
                            shutil.copy2(item, dest_dir / item.name)
                    applied_skills.append(s_dir.name)

        return {
            "status": "success",
            "applied_skills": applied_skills,
        }

    def pull(self) -> bool:
        """Pull latest changes from remote Git hub."""
        code, _ = self._run_git(["pull", "origin", "main"])
        return code == 0

    def push_patterns(
        self, commit_message: str = "Auto-sync WikiSkill patterns"
    ) -> bool:
        """Stage, commit, and push hub updates to remote."""
        self._run_git(["add", "."])
        self._run_git(["commit", "-m", commit_message])
        code, _ = self._run_git(["push", "origin", "main"])
        return code == 0
