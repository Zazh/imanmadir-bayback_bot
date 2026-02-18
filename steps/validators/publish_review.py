from typing import Any
from .base import BaseValidator, ValidationResult


class PublishReviewValidator(BaseValidator):
    """Валидатор публикации отзыва (фото скриншота)"""

    async def validate(self, user_input: Any) -> ValidationResult:
        # user_input — это file_path после сохранения фото
        if not user_input:
            return ValidationResult(
                is_valid=False,
                error_message='📸 Отправь скриншот опубликованного отзыва',
            )

        return ValidationResult(
            is_valid=True,
            data={'photo': user_input},
        )

    @property
    def requires_moderation(self) -> bool:
        # Скриншот отзыва всегда идёт на модерацию
        return True