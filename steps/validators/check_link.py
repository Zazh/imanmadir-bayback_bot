from typing import Any
from .base import BaseValidator, ValidationResult


class CheckLinkValidator(BaseValidator):
    """Валидатор ссылки на чек"""

    async def validate(self, user_input: Any) -> ValidationResult:
        text = str(user_input).strip()

        if not text.startswith('https://'):
            return ValidationResult(
                is_valid=False,
                error_message='🔗 Отправь корректную ссылку (начинается с https://)',
            )

        return ValidationResult(
            is_valid=True,
            data={'link': text},
        )