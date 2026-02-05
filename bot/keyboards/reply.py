from telegram import ReplyKeyboardMarkup, KeyboardButton


def main_menu_keyboard():
    """Главное меню"""
    keyboard = [
        [KeyboardButton('📋 Задания')],
        [KeyboardButton('📦 Мои выкупы')],
        [KeyboardButton('👤 Профиль'), KeyboardButton('💬 Поддержка')],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)