from steps.models import StepType
from .base import BaseValidator, ValidationResult
from .photo import PhotoValidator
from .article import ArticleCheckValidator
from .text import TextModeratedValidator
from .confirm import ConfirmValidator
from .order_number import OrderNumberValidator
from .choice import ChoiceValidator
from .check_link import CheckLinkValidator
from .payment import PaymentDetailsValidator


VALIDATORS = {
    StepType.PHOTO: PhotoValidator,
    StepType.ARTICLE_CHECK: ArticleCheckValidator,
    StepType.TEXT_MODERATED: TextModeratedValidator,
    StepType.CONFIRM: ConfirmValidator,
    StepType.ORDER_NUMBER: OrderNumberValidator,
    StepType.CHOICE: ChoiceValidator,
    StepType.CHECK_LINK: CheckLinkValidator,
    StepType.PAYMENT_DETAILS: PaymentDetailsValidator,
}


def get_validator(step, buyback) -> BaseValidator:
    """Получить валидатор для шага"""
    validator_class = VALIDATORS.get(step.step_type)
    if not validator_class:
        raise ValueError(f'Unknown step type: {step.step_type}')
    return validator_class(step, buyback)


__all__ = [
    'BaseValidator',
    'ValidationResult',
    'get_validator',
    'VALIDATORS',
]