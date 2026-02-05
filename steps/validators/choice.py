from typing import Any
from .base import BaseValidator, ValidationResult


class ChoiceValidator(BaseValidator):
    """Валидатор выбора варианта"""

    async def validate(self, user_input: Any) -> ValidationResult:
        choice = str(user_input).strip()
        choices = self.step.settings.get('choices', [])

        if choices and choice not in choices:
            return ValidationResult(
                is_valid=False,
                error_message='❌ Выбери один из предложенных вариантов',
            )

        return ValidationResult(
            is_valid=True,
            data={'choice': choice},
        )