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

