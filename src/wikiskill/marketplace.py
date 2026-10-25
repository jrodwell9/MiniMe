"""Zero-Copy Group-Scoped Plugin Marketplace and Semantic Versioning Manager.

Organizes operational skills as domain-grouped plugins (`groups/<group>/plugins/<skill>/`),
maintains dual manifests for Antigravity (`plugin.json`) and Claude Code (`.claude-plugin/plugin.json`),
and computes Conventional Commit SemVer bumps using Commitizen.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from commitizen.config import BaseConfig
from commitizen.cz.conventional_commits import ConventionalCommitsCz
from commitizen.version_schemes import SemVer


def bump_plugin_version(current_version: str | None, commit_message: str) -> str:
    """Calculate the next SemVer version for a plugin using Commitizen conventional commit rules."""
    if not current_version or not current_version.strip():
        return "1.0.0"

    msg = commit_message.strip()
    header = msg.splitlines()[0] if msg else ""
    increment = "PATCH"

    if "BREAKING CHANGE" in msg or "!:" in header:
        increment = "MAJOR"
    else:
        cz = ConventionalCommitsCz(BaseConfig())
        bump_pattern = cz.bump_pattern
        bump_map = cz.bump_map or {}
        match = re.match(bump_pattern, msg) if bump_pattern else None
        if match:
            prefix = match.group(0)
            for pattern, mapped_increment in bump_map.items():
                if re.match(pattern, prefix):
                    if isinstance(mapped_increment, str) and mapped_increment in (
                        "MAJOR",
                        "MINOR",
                        "PATCH",
                    ):
                        increment = mapped_increment
                    break
        elif header.startswith("feat"):
            increment = "MINOR"

    return str(SemVer(current_version.strip()).bump(increment))


class MarketplaceManager:
    """Encapsulates group-scoped plugin catalog generation, dual-manifest writing, and zero-copy workspace subscriptions."""

    def __init__(
        self,
        hub_dir: Path | str,
        git_runner: Callable[[list[str]], tuple[int, str]] | None = None,
    ) -> None:
        self.hub_dir = Path(hub_dir).resolve()
        self.git_runner = git_runner

    def _git_add(self, rel_path: str) -> None:
        if self.git_runner is not None:
            self.git_runner(["add", rel_path])

    def list_hub_groups_and_plugins(self) -> dict[str, list[dict[str, str]]]:
        """Inspect the central hub and return a mapping of group names to their discovered plugins."""
        groups_map: dict[str, list[dict[str, str]]] = {"global": []}
        groups_root = self.hub_dir / "groups"
        if groups_root.exists():
            for grp_dir in sorted(groups_root.iterdir(), key=lambda p: p.name):
                if not grp_dir.is_dir():
                    continue
                plugins_dir = grp_dir / "plugins"
                plugins_list: list[dict[str, str]] = []
                if plugins_dir.exists():
                    for p_dir in sorted(plugins_dir.iterdir(), key=lambda p: p.name):
                        if not p_dir.is_dir():
                            continue
                        p_json = p_dir / "plugin.json"
                        name = p_dir.name
                        desc = ""
                        ver = "1.0.0"
                        if p_json.exists():
                            try:
                                data = json.loads(p_json.read_text(encoding="utf-8"))
                                name = data.get("name", name)
                                desc = data.get("description", "")
                                ver = data.get("version", ver)
                            except OSError, json.JSONDecodeError:
                                pass
                        plugins_list.append(
                            {
                                "name": name,
                                "description": desc,
                                "version": ver,
                                "group": grp_dir.name,
                                "path": p_dir.as_posix(),
                            }
                        )
                groups_map[grp_dir.name] = plugins_list

        legacy_skills_root = self.hub_dir / "global" / "skills"
        if legacy_skills_root.exists():
            for s_dir in sorted(legacy_skills_root.iterdir(), key=lambda p: p.name):
                if not s_dir.is_dir():
                    continue
                if not any(p["name"] == s_dir.name for p in groups_map["global"]):
                    groups_map["global"].append(
                        {
                            "name": s_dir.name,
                            "description": "",
                            "version": "1.0.0",
                            "group": "global",
                            "path": s_dir.as_posix(),
                        }
                    )
        return groups_map

    def ensure_cz_and_marketplace_manifests(self) -> None:
        """Ensure `.cz.toml`, `groups/<group>/{skills,plugins}.json`, and `.claude-plugin/marketplace.json` are up-to-date in `hub_dir`."""
        cz_toml = self.hub_dir / ".cz.toml"
        if not cz_toml.exists():
            cz_toml.write_text(
                '[tool.commitizen]\nname = "cz_conventional_commits"\ntag_format = "v$version"\nversion_scheme = "semver"\n',
                encoding="utf-8",
            )
            self._git_add(".cz.toml")

        groups_root = self.hub_dir / "groups"
        marketplace_plugins: list[dict[str, Any]] = []

        if groups_root.exists():
            for grp_dir in sorted(groups_root.iterdir(), key=lambda p: p.name):
                if not grp_dir.is_dir():
                    continue
                plugins_dir = grp_dir / "plugins"
                group_entries: list[dict[str, str]] = []
                if plugins_dir.exists():
                    for p_dir in sorted(plugins_dir.iterdir(), key=lambda p: p.name):
                        p_json = p_dir / "plugin.json"
                        if not p_dir.is_dir() or not p_json.exists():
                            continue
                        try:
                            p_data = json.loads(p_json.read_text(encoding="utf-8"))
                        except OSError, json.JSONDecodeError:
                            continue
                        s_name = p_data.get("name", p_dir.name)
                        group_entries.append(
                            {
                                "path": f"~/.claude/wikiskill-hub/groups/{grp_dir.name}/plugins/{s_name}/skills"
                            }
                        )
                        marketplace_plugins.append(
                            {
                                "name": s_name,
                                "category": grp_dir.name,
                                "version": p_data.get("version", "1.0.0"),
                                "source": f"./groups/{grp_dir.name}/plugins/{s_name}",
                                "description": p_data.get("description", ""),
                            }
                        )
                group_skills_json = grp_dir / "skills.json"
                group_skills_json.write_text(
                    json.dumps({"entries": group_entries}, indent=2) + "\n",
                    encoding="utf-8",
                )
                group_plugins_json = grp_dir / "plugins.json"
                group_plugins_json.write_text(
                    json.dumps(
                        {
                            "entries": [
                                {
                                    "path": f"~/.claude/wikiskill-hub/groups/{grp_dir.name}/plugins"
                                }
                            ]
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                self._git_add(f"groups/{grp_dir.name}/skills.json")
                self._git_add(f"groups/{grp_dir.name}/plugins.json")

        marketplace_dir = self.hub_dir / ".claude-plugin"
        marketplace_dir.mkdir(parents=True, exist_ok=True)
        marketplace_file = marketplace_dir / "marketplace.json"
        marketplace_payload = {
            "name": "wikiskill-marketplace",
            "description": "WikiSkill domain-grouped operational skill marketplace",
            "owner": {"name": "WikiSkill Hub"},
            "plugins": marketplace_plugins,
        }
        marketplace_file.write_text(
            json.dumps(marketplace_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        self._git_add(".claude-plugin/marketplace.json")

    def write_plugin_files(
        self,
        safe_skill: str,
        safe_group: str,
        description: str,
        version: str,
        skill_md_content: str,
        purpose_md_content: str,
    ) -> Path:
        """Write dual manifests and skill files for `groups/<safe_group>/plugins/<safe_skill>`."""
        plugin_root = (
            self.hub_dir / "groups" / safe_group / "plugins" / safe_skill
        ).resolve()
        plugin_skill_dir = plugin_root / "skills" / safe_skill
        claude_plugin_dir = plugin_root / ".claude-plugin"
        plugin_skill_dir.mkdir(parents=True, exist_ok=True)
        claude_plugin_dir.mkdir(parents=True, exist_ok=True)

        plugin_manifest = {
            "name": safe_skill,
            "description": description,
            "version": version,
            "group": safe_group,
            "author": {"name": "WikiSkill Curator"},
        }
        claude_plugin_manifest = {
            "name": safe_skill,
            "description": description,
            "version": version,
            "author": {"name": "WikiSkill Curator"},
        }
        (plugin_root / "plugin.json").write_text(
            json.dumps(plugin_manifest, indent=2) + "\n", encoding="utf-8"
        )
        (claude_plugin_dir / "plugin.json").write_text(
            json.dumps(claude_plugin_manifest, indent=2) + "\n", encoding="utf-8"
        )
        (plugin_skill_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")
        (plugin_skill_dir / "PURPOSE.md").write_text(
            purpose_md_content, encoding="utf-8"
        )
        self._git_add(f"groups/{safe_group}/plugins/{safe_skill}")

        legacy_skill_dir = self.hub_dir / "global" / "skills" / safe_skill
        if safe_group == "global" or legacy_skill_dir.exists():
            legacy_skill_dir.mkdir(parents=True, exist_ok=True)
            (legacy_skill_dir / "SKILL.md").write_text(
                skill_md_content, encoding="utf-8"
            )
            (legacy_skill_dir / "PURPOSE.md").write_text(
                purpose_md_content, encoding="utf-8"
            )
            self._git_add(f"global/skills/{safe_skill}")

        return plugin_root

    def configure_workspace_groups(
        self,
        agents_dir: Path | str,
        groups: Sequence[str] = ("global",),
    ) -> dict[str, Any]:
        """Write `<project_dir>/.agents/{skills,plugins}.json` inheriting `global` plus requested domain groups without copying SKILL.md files."""
        target_agents_dir = Path(agents_dir).resolve()
        ordered_groups: list[str] = ["global"]
        for grp in groups:
            cleaned = grp.strip()
            if cleaned and cleaned not in ordered_groups:
                ordered_groups.append(cleaned)

        home_dir = Path.home().resolve()
        if self.hub_dir.is_relative_to(home_dir):
            rel_hub = self.hub_dir.relative_to(home_dir).as_posix()
            hub_prefix = f"~/{rel_hub}"
        else:
            hub_prefix = self.hub_dir.as_posix()

        skills_inherits = [
            {"path": f"{hub_prefix}/groups/{grp}/skills.json"} for grp in ordered_groups
        ]
        plugins_inherits = [
            {"path": f"{hub_prefix}/groups/{grp}/plugins.json"}
            for grp in ordered_groups
        ]
        target_agents_dir.mkdir(parents=True, exist_ok=True)
        skills_json_path = target_agents_dir / "skills.json"
        skills_json_path.write_text(
            json.dumps({"inherits": skills_inherits}, indent=2) + "\n",
            encoding="utf-8",
        )
        plugins_json_path = target_agents_dir / "plugins.json"
        plugins_json_path.write_text(
            json.dumps({"inherits": plugins_inherits}, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "status": "success",
            "groups": ordered_groups,
            "skills_json": str(skills_json_path),
            "plugins_json": str(plugins_json_path),
        }

