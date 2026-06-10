"""
PromptTemplateRepository — loads and caches prompt templates from YAML files.

Templates are stored in app/generation/prompts/templates/ as YAML files
named {template_name}_v{version}.yaml.

Design:
- Templates are loaded once and cached in memory.
- The repository is injected into PromptRenderer (no global state).
- Adding a new template requires only dropping a YAML file in the templates dir.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


_TEMPLATES_DIR = Path(__file__).parent / "templates"


class PromptTemplate(BaseModel):
    """A loaded prompt template with system + user prompt."""
    name: str
    version: str
    description: str = ""
    system_prompt: str
    user_prompt_template: str

    @property
    def full_name(self) -> str:
        return f"{self.name}_v{self.version}"


class PromptTemplateRepository:
    """
    Loads prompt templates from YAML files.

    File naming convention: {name}_v{version}.yaml
    Example: component_extraction_v1.yaml
    """

    def __init__(self, templates_dir: Optional[Path] = None) -> None:
        self._dir = templates_dir or _TEMPLATES_DIR
        self._cache: dict[str, PromptTemplate] = {}

    def get(self, name: str, version: str = "1") -> PromptTemplate:
        """
        Return a template by name + version.
        Raises FileNotFoundError if not found.
        """
        key = f"{name}_v{version}"
        if key not in self._cache:
            self._cache[key] = self._load(name, version)
        return self._cache[key]

    def list_available(self) -> list[str]:
        """Return all available template full names."""
        return [
            f.stem
            for f in self._dir.glob("*.yaml")
            if f.is_file()
        ]

    def _load(self, name: str, version: str) -> PromptTemplate:
        filename = f"{name}_v{version}.yaml"
        path = self._dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Prompt template not found: {filename} "
                f"(looked in {self._dir})"
            )
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return PromptTemplate(**data)


@lru_cache(maxsize=1)
def get_prompt_repository() -> PromptTemplateRepository:
    """Cached singleton repository — safe to call anywhere."""
    return PromptTemplateRepository()
