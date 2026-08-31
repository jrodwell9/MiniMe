import os
from typing import Any

from .wikiskill_dataclasses import SessionTrajectory


class WikiManager:
    def __init__(self, base_path: str = ".claude/wiki"):
        self.base_path = base_path
        self.patterns_path = os.path.join(base_path, "patterns")
        self.index_path = os.path.join(base_path, "index.md")
        self.logs_path = os.path.join(base_path, "logs.md")
        self.skill_impact_path = os.path.join(base_path, "skill-impact.md")

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
        current_content = self._read_file(self.index_path) or ""
        # Remove trailing newline if it exists, so we can consistently add one before new entries
        if current_content.endswith("\n"):
            current_content = current_content.rstrip("\n")

        updated_lines = current_content.splitlines()

        for addition in additions:
            if (
                addition not in updated_lines
            ):  # Check if the addition (line) already exists
                updated_lines.append(addition)

        new_content = (
            "\n".join(updated_lines) + "\n"
        )  # Add a single trailing newline at the end
        self._write_file(self.index_path, new_content)
        print(f"Updated wiki index: {self.index_path}")

    def append_log(self, entry: str):
        self._write_file(self.logs_path, f"{entry}\n", mode="a")
        print(f"Appended to wiki log: {self.logs_path}")

    def process_llm_wiki_response(self, llm_response: dict[str, Any]):
        for pattern in llm_response.get("create_patterns", []):
            self.create_pattern(pattern["name"], pattern["content"])
        for pattern in llm_response.get("update_patterns", []):
            self.update_pattern(pattern["name"], pattern["content"])
        if "update_index" in llm_response:
            self.update_index(llm_response["update_index"].get("additions", []))
        if "append_log" in llm_response:
            self.append_log(llm_response["append_log"])

    def call_llm_for_wiki_update(
        self, trajectory: SessionTrajectory, wiki_context: str
    ) -> dict[str, Any]:
        # This is a placeholder for the LLM interaction.
        # In a real scenario, this would involve making an API call to an LLM.
        # The LLM would analyze the trajectory and wiki_context to propose updates.
        print(
            f"Simulating LLM call for wiki update with session {trajectory.session_id} and wiki context..."
        )
        # For now, return a mock response
        return {
            "create_patterns": [],
            "update_patterns": [],
            "update_index": {"additions": ["- New pattern: example-pattern"]},
            "append_log": "Wiki Maintainer processed session mock-session-123.",
        }
