from typing import Any
from .base import BaseValidator, ValidationResult


class PaymentDetailsValidator(BaseValidator):
    """Валидатор реквизитов для выплаты"""

    async def validate(self, user_input: Any) -> ValidationResult:
        # user_input — dict с phone, bank_name, card_holder_name
        if not isinstance(user_input, dict):
            return ValidationResult(
                is_valid=False,
                error_message='❌ Ошибка данных',
            )

        phone = user_input.get('phone', '').strip()
        bank_name = user_input.get('bank_name', '').strip()
        card_holder_name = user_input.get('card_holder_name', '').strip()

        if not all([phone, bank_name, card_holder_name]):
            return ValidationResult(
                is_valid=False,
                error_message='❌ Заполни все поля',
            )

        return ValidationResult(
            is_valid=True,
            data={
                'phone': phone,
                'bank_name': bank_name,
                'card_holder_name': card_holder_name,
            },
        )