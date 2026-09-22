"""Safe, draft-only external news ingestion and AI rewrite pipeline."""

from .openrouter import PROMPT_VERSION, OpenRouterClient, OpenRouterError

__all__ = ('PROMPT_VERSION', 'OpenRouterClient', 'OpenRouterError')
