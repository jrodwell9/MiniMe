from pathlib import Path

from wikiskill.cli import build_parser, main


def test_cli_parser_post_session_subcommand():
    parser = build_parser()
    args = parser.parse_args(
        ["post-session", "--since", "2026-08-31T12:00:00Z", "--mock", "--dry-run"]
    )
    assert args.command == "post-session"
    assert args.since == "2026-08-31T12:00:00Z"
    assert args.mock is True
    assert args.dry_run is True


def test_cli_parser_legacy_flag():
    parser = build_parser()
    args = parser.parse_args(["--post-session", "--mock"])
    assert args.post_session_flag is True
    assert args.mock is True


def test_cli_parser_init_command():
    parser = build_parser()
    args = parser.parse_args(["init", "--project-dir", "/custom/path"])
    assert args.command == "init"
    assert args.project_dir == "/custom/path"


def test_cli_parser_status_command():
    parser = build_parser()
    args = parser.parse_args(["status", "--project-dir", "/custom/path"])
    assert args.command == "status"
    assert args.project_dir == "/custom/path"


def test_cli_parser_sync_command():
    parser = build_parser()
    args = parser.parse_args(["sync", "--pull", "--prune", "--hub-dir", "/custom/hub"])
    assert args.command == "sync"
    assert args.pull is True
    assert args.prune is True
    assert args.hub_dir == "/custom/hub"


def test_cli_parser_daemon_command():
    parser = build_parser()
    args = parser.parse_args(["daemon", "--interval", "60", "--once"])
    assert args.command == "daemon"
    assert args.interval == 60
    assert args.once is True


def test_cli_parser_setup_hub_command():
    parser = build_parser()
    args = parser.parse_args(["setup-hub", "--remote", "git@github.com:user/hub.git"])
    assert args.command == "setup-hub"
    assert args.remote == "git@github.com:user/hub.git"


def test_cli_init_execution(tmp_path: Path):
    target_dir = tmp_path / "test_repo"
    target_dir.mkdir()

    exit_code = main(["init", "--project-dir", str(target_dir)])
    assert exit_code == 0

    wiki_dir = target_dir / ".claude" / "wiki"
    assert (wiki_dir / "index.md").exists()
    assert (wiki_dir / "patterns").is_dir()
    assert (target_dir / ".claude" / "skills").is_dir()


def test_cli_post_session_dry_run(tmp_path: Path):
    target_dir = tmp_path / "test_repo"
    target_dir.mkdir()

    exit_code = main(
        ["post-session", "--project-dir", str(target_dir), "--mock", "--dry-run"]
    )
    assert exit_code == 0

    wiki_dir = target_dir / ".claude" / "wiki"
    assert not (wiki_dir / "patterns").exists()


def test_cli_post_session_execution(tmp_path: Path):
    target_dir = tmp_path / "test_repo"
    target_dir.mkdir()

    exit_code = main(["post-session", "--project-dir", str(target_dir), "--mock"])
    assert exit_code == 0

    wiki_dir = target_dir / ".claude" / "wiki"
    assert not (wiki_dir / "patterns").exists()
    assert not (target_dir / ".claude" / "skills").exists()


def test_cli_sync_prune_default_project_dir(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    hub_dir = tmp_path / "hub"

    # Initialize workspace
    main(["init"])

    # Create orphaned dummy skill
    dummy_skill = tmp_path / ".claude" / "skills" / "dummy-orphaned"
    dummy_skill.mkdir(parents=True)
    (dummy_skill / "SKILL.md").write_text("dummy", encoding="utf-8")

    exit_code = main(["sync", "--pull", "--prune", "--hub-dir", str(hub_dir)])
    assert exit_code == 0

    # Assert dummy skill was pruned
    assert not dummy_skill.exists()
