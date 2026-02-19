from telegram import InlineKeyboardMarkup, InlineKeyboardButton


def onboarding_keyboard():
    """Клавиатура онбординга"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('❌ Да, исключали', callback_data='onboard:excluded')],
        [InlineKeyboardButton('✅ Нет, не исключали', callback_data='onboard:not_excluded')],
    ])


def tasks_list_keyboard(tasks):
    """Список заданий"""
    buttons = []
    for task in tasks:
        buttons.append([
            InlineKeyboardButton(
                f'📦 {task.title} — {task.payout}₽',
                callback_data=f'task:{task.id}',
            )
        ])
    return InlineKeyboardMarkup(buttons)


def task_detail_keyboard(task_id: int, available: bool = True):
    """Детали задания"""
    buttons = []
    if available:
        buttons.append([
            InlineKeyboardButton('✅ Взять задание', callback_data=f'take:{task_id}')
        ])
    buttons.append([
        InlineKeyboardButton('« Назад', callback_data='tasks_list')
    ])
    return InlineKeyboardMarkup(buttons)