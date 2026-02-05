from typing import Any
from .base import BaseValidator, ValidationResult


class OrderNumberValidator(BaseValidator):
    """Валидатор номера заказа"""

    async def validate(self, user_input: Any) -> ValidationResult:
        text = str(user_input).strip()

        if not text:
            return ValidationResult(
                is_valid=False,
                error_message='🔢 Введи номер заказа',
            )

        # Можно добавить проверку формата если нужно
        # if not text.isdigit():
        #     return ValidationResult(...)

        return ValidationResult(
            is_valid=True,
            data={'order_number': text},
        )