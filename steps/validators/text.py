from typing import Any
from .base import BaseValidator, ValidationResult


class TextModeratedValidator(BaseValidator):
    """Валидатор текста с модерацией"""

    async def validate(self, user_input: Any) -> ValidationResult:
        text = str(user_input).strip()

        min_length = self.step.settings.get('min_length', 10)

        if len(text) < min_length:
            return ValidationResult(
                is_valid=False,
                error_message=f'✏️ Текст слишком короткий. Минимум {min_length} символов.',
            )

        return ValidationResult(
            is_valid=True,
            data={'text': text},
        )

    @property
    def requires_moderation(self) -> bool:
        # Текст всегда идёт на модерацию
        return True