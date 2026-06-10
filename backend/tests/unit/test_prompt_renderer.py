"""
Unit tests for PromptRenderer and PromptTemplateRepository.

Tests cover:
- PromptTemplate construction and full_name property
- PromptRenderer.render_template() with correct variables
- render_template raises ValueError on missing variables
- render() loads from the real YAML template directory
- Repository caches templates (same object returned twice)
- Repository raises FileNotFoundError for missing templates
No external APIs or DB needed.
"""

from __future__ import annotations

import pytest

from app.generation.prompts.renderer import PromptRenderer
from app.generation.prompts.repository import PromptTemplate, PromptTemplateRepository
from app.generation.providers.base import MessageRole


# ── PromptTemplate model ──────────────────────────────────────────────────────

class TestPromptTemplate:
    def test_full_name_format(self):
        t = PromptTemplate(
            name="component_extraction",
            version="1",
            system_prompt="You are an expert.",
            user_prompt_template="Analyse: {document_content}",
        )
        assert t.full_name == "component_extraction_v1"

    def test_full_name_with_version_2(self):
        t = PromptTemplate(
            name="my_template",
            version="2",
            system_prompt="System",
            user_prompt_template="User {x}",
        )
        assert t.full_name == "my_template_v2"

    def test_description_defaults_to_empty(self):
        t = PromptTemplate(
            name="t",
            version="1",
            system_prompt="S",
            user_prompt_template="U",
        )
        assert t.description == ""


# ── PromptRenderer.render_template() — static, no I/O ─────────────────────

class TestRenderTemplate:
    @pytest.fixture
    def simple_template(self) -> PromptTemplate:
        return PromptTemplate(
            name="test_template",
            version="1",
            system_prompt="  You are a LOTO expert.  ",
            user_prompt_template="Document:\n{document_content}\nEnd.",
        )

    def test_returns_two_messages(self, simple_template):
        repo = PromptTemplateRepository.__new__(PromptTemplateRepository)
        renderer = PromptRenderer(repo)
        messages = renderer.render_template(simple_template, document_content="the docs")
        assert len(messages) == 2

    def test_first_message_is_system(self, simple_template):
        messages = PromptRenderer.render_template(simple_template, document_content="x")
        assert messages[0].role == MessageRole.SYSTEM

    def test_second_message_is_user(self, simple_template):
        messages = PromptRenderer.render_template(simple_template, document_content="x")
        assert messages[1].role == MessageRole.USER

    def test_system_prompt_stripped(self, simple_template):
        messages = PromptRenderer.render_template(simple_template, document_content="x")
        assert messages[0].content == "You are a LOTO expert."

    def test_variable_substituted(self, simple_template):
        messages = PromptRenderer.render_template(
            simple_template, document_content="Machine with a red switch"
        )
        assert "Machine with a red switch" in messages[1].content

    def test_missing_variable_raises_value_error(self, simple_template):
        with pytest.raises(ValueError, match="document_content"):
            PromptRenderer.render_template(simple_template)

    def test_extra_variables_ignored(self, simple_template):
        messages = PromptRenderer.render_template(
            simple_template,
            document_content="content",
            unused_extra="ignored",
        )
        assert len(messages) == 2

    def test_multiline_content_preserved(self, simple_template):
        content = "Line one\nLine two\nLine three"
        messages = PromptRenderer.render_template(simple_template, document_content=content)
        assert "Line one" in messages[1].content
        assert "Line three" in messages[1].content


# ── PromptTemplateRepository — real YAML file ─────────────────────────────

class TestPromptTemplateRepository:
    @pytest.fixture
    def repo(self) -> PromptTemplateRepository:
        return PromptTemplateRepository()

    def test_get_component_extraction_v1(self, repo):
        template = repo.get("component_extraction", "1")
        assert template.name == "component_extraction"
        assert template.version == "1"

    def test_system_prompt_not_empty(self, repo):
        template = repo.get("component_extraction", "1")
        assert len(template.system_prompt) > 50

    def test_user_prompt_template_contains_document_variable(self, repo):
        template = repo.get("component_extraction", "1")
        assert "{document_content}" in template.user_prompt_template

    def test_template_cached_on_second_get(self, repo):
        t1 = repo.get("component_extraction", "1")
        t2 = repo.get("component_extraction", "1")
        assert t1 is t2

    def test_missing_template_raises_file_not_found(self, repo):
        with pytest.raises(FileNotFoundError):
            repo.get("nonexistent_template", "999")

    def test_list_available_includes_component_extraction(self, repo):
        available = repo.list_available()
        assert "component_extraction_v1" in available


# ── PromptRenderer.render() — via repository ──────────────────────────────

class TestRendererWithRepository:
    @pytest.fixture
    def renderer(self) -> PromptRenderer:
        return PromptRenderer(PromptTemplateRepository())

    def test_render_component_extraction(self, renderer):
        messages = renderer.render(
            "component_extraction", "1",
            document_content="The machine has a red switch and a battery.",
        )
        assert len(messages) == 2

    def test_system_prompt_is_loto_expert(self, renderer):
        messages = renderer.render(
            "component_extraction", "1",
            document_content="content",
        )
        assert "LOTO" in messages[0].content or "Lockout" in messages[0].content

    def test_document_content_in_user_prompt(self, renderer):
        content = "Blue valve controls hydraulic pressure"
        messages = renderer.render(
            "component_extraction", "1",
            document_content=content,
        )
        assert content in messages[1].content
