import os
from pathlib import Path
from typing import Any

def _parse_frontmatter(content: str) -> dict[str, Any]:
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
        if line.startswith("- ") and current_key:
            item_val = line[2:].strip().strip('"').strip("'")
            if not isinstance(result.get(current_key), list):
                result[current_key] = []
            result[current_key].append(item_val)
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if v.startswith("[") and v.endswith("]"):
                items = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
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
    def __init__(self, hub_dir: Any = None, remote_url: Any = None, **kwargs: Any):
        self.hub_dir = Path(hub_dir or "~/.claude/wikiskill-hub").expanduser()
        self.remote_url = remote_url
    def init_hub(self, remote_url: Any = None) -> bool:
        return True
    def sync_project_to_hub(self, project_dir: Any, prune: bool = False) -> dict[str, Any]:
        return {"copied_patterns": [], "copied_skills": [], "deleted_patterns": [], "deleted_skills": []}
