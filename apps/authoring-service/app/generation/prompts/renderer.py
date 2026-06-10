"""
PromptRenderer — fills template variables and builds message lists.

Variable substitution uses Python's str.format_map(), which supports
{variable_name} placeholders. Curly braces in the template content that
are NOT variables must be escaped as {{ and }}.

The renderer returns a list[Message] ready to pass to any LLMProvider.
"""

from __future__ import annotations

from app.generation.providers.base import Message, MessageRole
from app.generation.prompts.repository import PromptTemplate, PromptTemplateRepository


class PromptRenderer:
    """
    Renders a PromptTemplate with concrete variable values.

    Usage:
        repo = PromptTemplateRepository()
        renderer = PromptRenderer(repo)
        messages = renderer.render(
            "component_extraction", "1",
            document_content="The machine has a red switch..."
        )
    """

    def __init__(self, repository: PromptTemplateRepository) -> None:
        self._repo = repository

    def render(
        self,
        template_name: str,
        version: str = "1",
        **variables: str,
    ) -> list[Message]:
        """
        Load template and substitute variables.

        Returns a list of Messages ready for LLMProvider.complete().
        The system prompt is always first; the rendered user prompt is second.
        """
        template = self._repo.get(template_name, version)
        return self.render_template(template, **variables)

    @staticmethod
    def render_template(template: PromptTemplate, **variables: str) -> list[Message]:
        """
        Render a pre-loaded template without hitting the repository.
        Useful in tests where the template is constructed directly.
        """
        try:
            user_content = template.user_prompt_template.format_map(variables)
        except KeyError as exc:
            raise ValueError(
                f"Prompt template '{template.full_name}' requires variable {exc} "
                f"but it was not provided. Available: {list(variables.keys())}"
            ) from exc

        return [
            Message(role=MessageRole.SYSTEM, content=template.system_prompt.strip()),
            Message(role=MessageRole.USER, content=user_content.strip()),
        ]
