import os
from pathlib import Path
from typing import Any

from .llm import WikiSkillLLMAdapter
from .models import SessionTrajectory


class WikiManager:
    def __init__(
        self,
        base_path: str = ".claude/wiki",
        llm_adapter: WikiSkillLLMAdapter | None = None,
        model: str | None = None,
        lm: Any | None = None,
        mock: bool = False,
        compiled_module_path: str | Path | None = None,
    ):
        self.base_path = base_path
        self.patterns_path = os.path.join(base_path, "patterns")
        self.index_path = os.path.join(base_path, "index.md")
        self.logs_path = os.path.join(base_path, "logs.md")
        self.skill_impact_path = os.path.join(base_path, "skill-impact.md")
        self.mock = mock
        self.llm_adapter = llm_adapter or WikiSkillLLMAdapter(
            model=model,
            lm=lm,
            mock=mock,
            compiled_wiki_module_path=compiled_module_path,
        )

    def initialize_wiki(self) -> None:
        """Ensure wiki directory and core index file exist."""
        os.makedirs(self.patterns_path, exist_ok=True)
        if not os.path.exists(self.index_path):
            self._write_file(self.index_path, "# Wiki Pattern Index\n\n")

    def _read_file(self, file_path: str) -> str | None:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def _write_file(self, file_path: str, content: str, mode: str = "w"):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, mode, encoding="utf-8") as f:
            f.write(content)

    def get_wiki_index(self) -> str | None:
        return self._read_file(self.index_path)

    def get_skill_impact_log(self) -> str | None:
        return self._read_file(self.skill_impact_path)

    def get_existing_patterns(self) -> list[dict[str, str]]:
        """Return existing pattern files sorted by name for LLM consolidation context."""
        patterns_dir = Path(self.patterns_path)
        if not patterns_dir.exists():
            return []
        existing: list[dict[str, str]] = []
        for pat_file in sorted(patterns_dir.glob("*.md"), key=lambda p: p.stem):
            try:
                existing.append(
                    {
                        "name": pat_file.stem,
                        "content": pat_file.read_text(encoding="utf-8"),
                    }
                )
            except OSError:
                continue
        return existing

    def create_pattern(self, pattern_name: str, content: str):
        file_path = os.path.join(self.patterns_path, f"{pattern_name}.md")
        self._write_file(file_path, content)
        print(f"Created new pattern file: {file_path}")

    def update_pattern(self, pattern_name: str, content: str):
        file_path = os.path.join(self.patterns_path, f"{pattern_name}.md")
        if os.path.exists(file_path):
            self._write_file(file_path, content)
            print(f"Updated pattern file: {file_path}")
        else:
            print(f"Warning: Pattern file {file_path} not found for update.")

    def update_index(self, additions: list[str]):
        if not additions:
            return
        current_content = self._read_file(self.index_path) or ""
        if current_content.endswith("\n"):
            current_content = current_content.rstrip("\n")

        updated_lines = current_content.splitlines()

        for addition in additions:
            if addition not in updated_lines:
                updated_lines.append(addition)

        new_content = "\n".join(updated_lines) + "\n"
        self._write_file(self.index_path, new_content)
        print(f"Updated wiki index: {self.index_path}")

    def append_log(self, entry: str):
        self._write_file(self.logs_path, f"{entry}\n", mode="a")
        print(f"Appended to wiki log: {self.logs_path}")

    def process_llm_wiki_response(self, llm_response: dict[str, Any]):
        for pattern in llm_response.get("create_patterns", []):
            self.create_pattern(pattern["name"], pattern["content"])
        for pattern in llm_response.get("update_patterns", []):
            file_path = os.path.join(self.patterns_path, f"{pattern['name']}.md")
            if os.path.exists(file_path):
                self.update_pattern(pattern["name"], pattern["content"])
            else:
                self.create_pattern(pattern["name"], pattern["content"])
        if "update_index" in llm_response:
            self.update_index(llm_response["update_index"].get("additions", []))
        if "append_log" in llm_response:
            self.append_log(llm_response["append_log"])

    def call_llm_for_wiki_update(
        self, trajectory: SessionTrajectory, wiki_context: str
    ) -> dict[str, Any]:
        """
        Analyze session trajectory for failure patterns using the configured DSPy LLM adapter.
        Short-circuits clean sessions (0 error steps) without making an LLM network call.
        """
        error_steps = [s for s in trajectory.steps if s.is_error]
        if not error_steps:
            log_entry = (
                f"Session {trajectory.session_id}: Analyzed {len(trajectory.steps)} steps "
                f"(0 errors); clean execution, no new patterns required."
            )
            return {
                "create_patterns": [],
                "update_patterns": [],
                "update_index": {"additions": []},
                "append_log": log_entry,
            }

        existing_patterns = self.get_existing_patterns()
        return self.llm_adapter.synthesize_wiki_update(
            trajectory,
            wiki_context,
            existing_patterns=existing_patterns,
        )
