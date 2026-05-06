"""
Prompts for prescription OCR (re-export from the goal module).
"""

from core.apps.base.resources.prescription_ocr.goals.prescription_extraction import (
    SYSTEM_PROMPT,
    prescription_extraction_user_prompt as user_prompt,
)

__all__ = ('SYSTEM_PROMPT', 'user_prompt')
