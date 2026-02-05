from typing import Any
from .base import BaseValidator, ValidationResult


class ConfirmValidator(BaseValidator):
    """Валидатор подтверждения (кнопка)"""

    async def validate(self, user_input: Any) -> ValidationResult:
        return ValidationResult(
            is_valid=True,
            data={'confirmed': True},
        )