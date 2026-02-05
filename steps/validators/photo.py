from typing import Any
from .base import BaseValidator, ValidationResult


class PhotoValidator(BaseValidator):
    """Валидатор загрузки фото"""

    async def validate(self, user_input: Any) -> ValidationResult:
        # user_input — это file_path после сохранения
        if not user_input:
            return ValidationResult(
                is_valid=False,
                error_message='📸 Отправь фото, пожалуйста',
            )

        return ValidationResult(
            is_valid=True,
            data={'photo': user_input},
        )