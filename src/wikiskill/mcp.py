import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from .wiki_manager import WikiManager


def sanitize_title_to_slug(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower()).strip()
    return re.sub(r"[-\s]+", "-", slug)


def lookup_pattern(query: str, project_dir: str | None = None) -> dict[str, Any]:
    """Search compiled pattern index and pattern markdown files for matching guidance."""
    target_dir = Path(project_dir or os.getcwd()).resolve()
    wiki_dir = target_dir / ".claude" / "wiki"
    patterns_dir = wiki_dir / "patterns"

    search_dirs = [patterns_dir]

    hub_global = Path(
        os.path.expanduser("~/.claude/wikiskill-hub/global/wiki/patterns")
    )
    if hub_global.exists() and hub_global != patterns_dir:
        search_dirs.append(hub_global)

    query_tokens = [t.lower() for t in query.split() if len(t) > 2]

    best_match = None
    best_score = 0

    for s_dir in search_dirs:
        if not s_dir.exists():
            continue
        for p_file in s_dir.glob("*.md"):
            try:
                content = p_file.read_text(encoding="utf-8")
                score = 0
                file_stem = p_file.stem.lower()
                for token in query_tokens:
                    if token in file_stem:
                        score += 3
                    if token in content.lower():
                        score += 1
                if score > best_score:
                    best_score = score
                    best_match = (p_file.stem, content)
            except OSError:
                continue

    if best_match and best_score > 0:
        return {
            "status": "found",
            "pattern_name": best_match[0],
            "content": best_match[1],
        }

    return {
        "status": "not_found",
        "message": f"No matching pattern found for query: '{query}'.",
    }


def get_active_skills(project_dir: str | None = None) -> dict[str, Any]:
    """Return all active operational skills for the project and global context."""
    target_dir = Path(project_dir or os.getcwd()).resolve()
    skills_dir = target_dir / ".claude" / "skills"

    skills: list[dict[str, str]] = []
    seen = set()

    search_dirs = [skills_dir]
    hub_global = Path(os.path.expanduser("~/.claude/wikiskill-hub/global/skills"))
    if hub_global.exists() and hub_global != skills_dir:
        search_dirs.append(hub_global)

    for s_dir in search_dirs:
        if not s_dir.exists():
            continue
        for item in s_dir.iterdir():
            if item.is_dir() and item.name not in seen:
                skill_file = item / "SKILL.md"
                if skill_file.exists():
                    try:
                        content = skill_file.read_text(encoding="utf-8")
                        skills.append(
                            {
                                "name": item.name,
                                "path": str(skill_file),
                                "content": content,
                            }
                        )
                        seen.add(item.name)
                    except OSError:
                        continue

    return {
        "status": "success",
        "skills": skills,
    }


def record_reflection(
    summary: str,
    error_encountered: str,
    fix_applied: str,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Capture an in-flight reflection pattern directly from agent execution."""
    target_dir = Path(project_dir or os.getcwd()).resolve()
    wiki_dir = target_dir / ".claude" / "wiki"
    manager = WikiManager(base_path=str(wiki_dir))

    slug = sanitize_title_to_slug(summary)
    pattern_name = f"in-flight-{slug}" if not slug.startswith("in-flight-") else slug

    content = f"""# {summary}

## Problem
{error_encountered}

## Root Cause
Recorded in-flight reflection during agent reasoning.

## Fix
{fix_applied}
"""
    manager.create_pattern(pattern_name, content)
    manager.update_index(
        [
            f"- [{pattern_name}](wiki/patterns/{pattern_name}.md): {summary}. Fix: {fix_applied}"
        ]
    )
    manager.append_log(f"Recorded in-flight reflection '{pattern_name}'.")

    return {
        "status": "success",
        "pattern_name": pattern_name,
        "file_path": str(Path(manager.patterns_path) / f"{pattern_name}.md"),
    }


def handle_mcp_call(request: dict[str, Any]) -> dict[str, Any]:
    """Handle standard JSON-RPC 2.0 MCP requests."""
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "lookup_pattern",
                        "description": "Look up root causes, failure modes, and fix rules from the compounding WikiSkill knowledge base.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Error message, tool name, or pattern description",
                                },
                                "project_dir": {
                                    "type": "string",
                                    "description": "Optional project directory override",
                                },
                            },
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "get_active_skills",
                        "description": "Retrieve active operational rules and best practices for the current project.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "project_dir": {
                                    "type": "string",
                                    "description": "Optional project directory override",
                                },
                            },
                        },
                    },
                    {
                        "name": "record_reflection",
                        "description": "Record an in-flight insight, failure pattern, and resolution directly into the persistent wiki.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "summary": {
                                    "type": "string",
                                    "description": "Short title of the problem/resolution",
                                },
                                "error_encountered": {
                                    "type": "string",
                                    "description": "Observed error or failure symptom",
                                },
                                "fix_applied": {
                                    "type": "string",
                                    "description": "Working resolution or prevention rule",
                                },
                                "project_dir": {
                                    "type": "string",
                                    "description": "Optional project directory override",
                                },
                            },
                            "required": [
                                "summary",
                                "error_encountered",
                                "fix_applied",
                            ],
                        },
                    },
                ]
            },
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "lookup_pattern":
            result = lookup_pattern(
                args.get("query", ""), project_dir=args.get("project_dir")
            )
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                },
            }
        elif tool_name == "get_active_skills":
            result = get_active_skills(project_dir=args.get("project_dir"))
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                },
            }
        elif tool_name == "record_reflection":
            result = record_reflection(
                summary=args.get("summary", ""),
                error_encountered=args.get("error_encountered", ""),
                fix_applied=args.get("fix_applied", ""),
                project_dir=args.get("project_dir"),
            )
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                },
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}",
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


def run_stdio_server() -> None:
    """Run MCP server reading JSON-RPC lines from stdin and writing to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            response = handle_mcp_call(req)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except (json.JSONDecodeError, OSError, ValueError) as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()
