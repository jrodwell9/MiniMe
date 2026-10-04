import argparse
import json
import os
import sys
from collections.abc import Sequence

from .daemon import WikiSkillDaemon
from .harness import WikiSkillHarness
from .sync import GitHubSyncManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wikiskill",
        description="WikiSkill Harness: Compounding knowledge engine for Claude Code agent sessions.",
    )

    # Legacy top-level flag support
    parser.add_argument(
        "--post-session",
        dest="post_session_flag",
        action="store_true",
        help="Run post-session evolution loop (legacy flag).",
    )
    parser.add_argument(
        "--since",
        type=str,
        help="Filter sessions modified after ISO timestamp (YYYY-MM-DDTHH:MM:SSZ).",
    )
    parser.add_argument(
        "--project-dir",
        type=str,
        help="Target project directory root (default: current working directory).",
    )
    parser.add_argument(
        "--wiki-dir",
        type=str,
        help="Custom location for wiki directory (default: <project-dir>/.claude/wiki).",
    )
    parser.add_argument(
        "--skills-dir",
        type=str,
        help="Custom location for skills directory (default: <project-dir>/.claude/skills).",
    )
    parser.add_argument(
        "--claude-dir",
        type=str,
        help="Custom Claude home directory (default: ~/.claude).",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run with synthetic session trajectory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate run without writing files to disk.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # post-session subcommand
    post_parser = subparsers.add_parser(
        "post-session", help="Run post-session evolution on latest transcript."
    )
    post_parser.add_argument(
        "--since",
        type=str,
        help="Filter sessions modified after ISO timestamp (YYYY-MM-DDTHH:MM:SSZ).",
    )
    post_parser.add_argument(
        "--project-dir",
        type=str,
        help="Target project directory root (default: current working directory).",
    )
    post_parser.add_argument(
        "--wiki-dir",
        type=str,
        help="Custom location for wiki directory.",
    )
    post_parser.add_argument(
        "--skills-dir",
        type=str,
        help="Custom location for skills directory.",
    )
    post_parser.add_argument(
        "--claude-dir",
        type=str,
        help="Custom Claude home directory.",
    )
    post_parser.add_argument(
        "--mock",
        action="store_true",
        help="Run with synthetic session trajectory.",
    )
    post_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate run without writing files to disk.",
    )
    post_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output.",
    )

    # init subcommand
    init_parser = subparsers.add_parser(
        "init", help="Scaffold .claude/wiki and .claude/skills in project."
    )
    init_parser.add_argument(
        "--project-dir",
        type=str,
        help="Target project directory root.",
    )
    init_parser.add_argument(
        "--wiki-dir",
        type=str,
        help="Custom location for wiki directory.",
    )
    init_parser.add_argument(
        "--skills-dir",
        type=str,
        help="Custom location for skills directory.",
    )

    # status subcommand
    status_parser = subparsers.add_parser(
        "status", help="Display wiki pattern and skill status."
    )
    status_parser.add_argument(
        "--project-dir",
        type=str,
        help="Target project directory root.",
    )
    status_parser.add_argument(
        "--wiki-dir",
        type=str,
        help="Custom location for wiki directory.",
    )
    status_parser.add_argument(
        "--skills-dir",
        type=str,
        help="Custom location for skills directory.",
    )

    # sync subcommand
    sync_parser = subparsers.add_parser(
        "sync", help="Sync local patterns and skills with central Git hub."
    )
    sync_parser.add_argument(
        "--hub-dir",
        type=str,
        help="Central hub directory (default: ~/.claude/wikiskill-hub).",
    )
    sync_parser.add_argument(
        "--project-dir",
        type=str,
        help="Project directory to sync (default: current working directory).",
    )
    sync_parser.add_argument(
        "--pull",
        action="store_true",
        help="Pull updates from remote hub.",
    )
    sync_parser.add_argument(
        "--push",
        action="store_true",
        help="Push local updates to remote hub.",
    )
    sync_parser.add_argument(
        "--prune",
        action="store_true",
        help="Prune local skills and patterns not present on central hub.",
    )
    sync_parser.add_argument(
        "--direct",
        action="store_true",
        help="Bypass PR gate and push directly to main branch.",
    )

    # daemon subcommand
    daemon_parser = subparsers.add_parser(
        "daemon", help="Run background watcher daemon across all Claude Code projects."
    )
    daemon_parser.add_argument(
        "--claude-dir",
        type=str,
        help="Claude home directory (default: ~/.claude).",
    )
    daemon_parser.add_argument(
        "--hub-dir",
        type=str,
        help="Central hub directory (default: ~/.claude/wikiskill-hub).",
    )
    daemon_parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Scan interval in seconds (default: 300).",
    )
    daemon_parser.add_argument(
        "--once",
        action="store_true",
        help="Run single scan pass and exit.",
    )

    # setup-hub subcommand
    setup_parser = subparsers.add_parser(
        "setup-hub",
        help="Initialize central Git Hub repository for multi-workstation sync.",
    )
    setup_parser.add_argument(
        "--remote",
        type=str,
        help="Remote Git repository URL (e.g. git@github.com:user/wiki-skills.git).",
    )
    setup_parser.add_argument(
        "--hub-dir",
        type=str,
        help="Central hub directory (default: ~/.claude/wikiskill-hub).",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    command = args.command
    if not command and args.post_session_flag:
        command = "post-session"

    if not command:
        parser.print_help()
        return 0

    if command == "init":
        harness = WikiSkillHarness(
            project_dir=getattr(args, "project_dir", None),
            wiki_dir=getattr(args, "wiki_dir", None),
            skills_dir=getattr(args, "skills_dir", None),
        )
        res = harness.init_project()
        print(
            f"Initialized WikiSkill directories for {res['wiki_dir']} and {res['skills_dir']}."
        )
        return 0

    elif command == "status":
        harness = WikiSkillHarness(
            project_dir=getattr(args, "project_dir", None),
            wiki_dir=getattr(args, "wiki_dir", None),
            skills_dir=getattr(args, "skills_dir", None),
        )
        status = harness.get_status()
        print(f"WikiSkill Status for: {status['project_dir']}")
        print(f"Wiki directory: {status['wiki_dir']}")
        print(f"Skills directory: {status['skills_dir']}")
        print(
            f"Active Patterns ({len(status['patterns'])}): {', '.join(status['patterns']) if status['patterns'] else 'None'}"
        )
        print(
            f"Active Skills ({len(status['skills'])}): {', '.join(status['skills']) if status['skills'] else 'None'}"
        )
        return 0

    elif command == "sync":
        manager = GitHubSyncManager(hub_dir=getattr(args, "hub_dir", None))
        manager.init_hub()
        prune_flag = getattr(args, "prune", False)
        direct_flag = getattr(args, "direct", False)
        if getattr(args, "pull", False):
            manager.pull(prune=prune_flag)
            print("Pulled latest updates from remote hub.")
        p_dir = getattr(args, "project_dir", None) or os.getcwd()
        if getattr(args, "push", False):
            res = manager.sync_project_to_hub(p_dir, prune=prune_flag)
            print(
                f"Promoted to global hub: {len(res['synced_patterns'])} patterns, {len(res['synced_skills'])} skills."
            )
            push_res = manager.push_patterns(direct=direct_flag)
            if push_res.get("status") == "no_changes":
                print("No changes to push to remote hub.")
            elif push_res.get("status") == "aborted":
                print(push_res.get("message", "Push aborted."))
                return 0
            elif push_res.get("mode") == "pr":
                proposals = push_res.get("proposals") or [push_res]
                print(
                    f"Created {len(proposals)} candidate proposal branch(es) and Pull Request(s):\n"
                )
                for prop in proposals:
                    prop_name = prop.get("name", prop.get("branch", "proposal"))
                    print(f"[Proposal] {prop_name}")
                    print(f"   Branch: {prop.get('branch')}")
                    if prop.get("description"):
                        print("   --- Proposed Changes ---")
                        for line in prop["description"].splitlines():
                            print(f"   {line}")
                        print("   ------------------------")
                    if prop.get("pr_url"):
                        if "/pull/" in prop["pr_url"]:
                            print(
                                f"   [PR] Successfully opened Pull Request: {prop['pr_url']}\n"
                            )
                        else:
                            print(
                                f"   [Web URL] Open Pull Request via Web: {prop['pr_url']}\n"
                            )
                    else:
                        print(
                            f"   Create a Pull Request on GitHub from branch '{prop.get('branch')}'.\n"
                        )
            else:
                print("Pushed local updates directly to remote main.")
        pull_res = manager.sync_hub_to_project(p_dir, prune=prune_flag)
        if prune_flag and pull_res.get("pruned_skills"):
            print(f"Pruned local skills: {', '.join(pull_res['pruned_skills'])}")
        if prune_flag and pull_res.get("pruned_patterns"):
            print(f"Pruned local patterns: {', '.join(pull_res['pruned_patterns'])}")
        return 0

    elif command == "daemon":
        daemon = WikiSkillDaemon(
            claude_dir=getattr(args, "claude_dir", None),
            hub_dir=getattr(args, "hub_dir", None),
            interval=getattr(args, "interval", 300),
        )
        daemon.run_loop(once=getattr(args, "once", False))
        return 0

    elif command == "setup-hub":
        manager = GitHubSyncManager(
            hub_dir=getattr(args, "hub_dir", None),
            remote_url=getattr(args, "remote", None),
        )
        manager.init_hub(remote_url=getattr(args, "remote", None))
        print(f"Initialized central WikiSkill Hub at: {manager.hub_dir}")
        remote_display = getattr(args, "remote", None)
        if remote_display:
            print(f"Linked remote origin: {remote_display}")
        print("\nWikiSkill plugin is active in .claude/skills/wikiskill/.")
        return 0

    elif command == "post-session":
        harness = WikiSkillHarness(
            project_dir=getattr(args, "project_dir", None),
            wiki_dir=getattr(args, "wiki_dir", None),
            skills_dir=getattr(args, "skills_dir", None),
            claude_dir=getattr(args, "claude_dir", None),
            mock=getattr(args, "mock", False),
            verbose=getattr(args, "verbose", False) or True,
        )
        res = harness.run_post_session(
            since=getattr(args, "since", None),
            dry_run=getattr(args, "dry_run", False),
        )
        if res["status"] == "no_session":
            print(res["message"])
            return 0
        elif res["status"] == "dry_run":
            print("[DRY-RUN] Simulated Post-Session Evolution:")
            print(json.dumps(res, indent=2))
            return 0
        else:
            print(f"Successfully processed session {res['session_id']}.")
            print(f"Patterns extracted: {', '.join(res['patterns_created'])}")
            print(f"Skills applied: {', '.join(p['name'] for p in res['proposals'])}")
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
