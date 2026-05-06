"""
Shared primitives for AI / LLM integrations (providers, pricing, preprocessing).

Prescription OCR and other domains should call through provider adapters rather
than embedding SDK-specific logic in Django views or models.
"""