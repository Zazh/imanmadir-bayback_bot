from enum import Enum, auto


class BuybackState(Enum):
    """Состояния прохождения выкупа"""
    WAITING_PHOTO = auto()
    WAITING_ARTICLE = auto()
    WAITING_TEXT = auto()
    WAITING_ORDER_NUMBER = auto()
    WAITING_CHOICE = auto()