from telegram import InlineKeyboardMarkup, InlineKeyboardButton


def onboarding_keyboard():
    """Клавиатура онбординга - вопрос об отзывах"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('❌ Исключали', callback_data='onboard:excluded')],
        [InlineKeyboardButton('✅ Не исключали, отзывы публикуются', callback_data='onboard:not_excluded')],
    ])


def task_detail_keyboard(task_id: int, available: bool = True):
    """Клавиатура для просмотра задания"""
    buttons = []
    if available:
        buttons.append([InlineKeyboardButton('✅ Взять задание', callback_data=f'take_task:{task_id}')])
    buttons.append([InlineKeyboardButton('« Назад', callback_data='tasks_list')])
    return InlineKeyboardMarkup(buttons)


def tasks_list_keyboard(tasks):
    """Список заданий"""
    buttons = []
    for task in tasks:
        buttons.append([
            InlineKeyboardButton(
                f'📦 {task.title} — {task.payout}₸',
                callback_data=f'task_detail:{task.id}'
            )
        ])
    return InlineKeyboardMarkup(buttons)


def buyback_detail_keyboard(buyback_id: int):
    """Клавиатура для выкупа"""
    buttons = [
        [InlineKeyboardButton('❌ Отменить выкуп', callback_data=f'cancel_buyback:{buyback_id}')],
        [InlineKeyboardButton('« К моим выкупам', callback_data='my_buybacks')],
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard(action: str, item_id: int):
    """Подтверждение действия"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton('✅ Да', callback_data=f'{action}_yes:{item_id}'),
            InlineKeyboardButton('❌ Нет', callback_data=f'{action}_no:{item_id}'),
        ]
    ])


def profile_keyboard():
    """Клавиатура профиля"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('💳 Изменить реквизиты', callback_data='edit_payment')],
    ])