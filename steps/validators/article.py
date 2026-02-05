from typing import Any
from .base import BaseValidator, ValidationResult


class ArticleCheckValidator(BaseValidator):
    """Валидатор проверки артикула"""

    async def validate(self, user_input: Any) -> ValidationResult:
        text = str(user_input).strip()

        # Берём артикул из настроек шага или из товара
        correct_article = (
            self.step.settings.get('correct_article') 
            or self.buyback.task.product.wb_article
        )

        if text != correct_article:
            return ValidationResult(
                is_valid=False,
                error_message='❌ Артикул не совпадает. Проверь и введи ещё раз.',
            )

        return ValidationResult(
            is_valid=True,
            data={'article': text},
        )