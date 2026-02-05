from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationResult:
    """Результат валидации"""
    is_valid: bool
    data: dict = None  # Данные для сохранения в response_data
    error_message: str = ''


class BaseValidator(ABC):
    """Базовый класс валидатора шага"""

    def __init__(self, step, buyback):
        self.step = step
        self.buyback = buyback

    @abstractmethod
    async def validate(self, user_input: Any) -> ValidationResult:
        """Валидация ввода пользователя"""
        pass

    @property
    def requires_moderation(self) -> bool:
        """Требует ли шаг модерации"""
        return self.step.requires_moderation