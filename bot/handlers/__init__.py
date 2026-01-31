from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

from .start import start_handler, onboarding_callback
from .menu import help_handler, profile_handler
from .tasks import tasks_list_handler, task_detail_callback, tasks_list_callback
from .buybacks import my_buybacks_handler
from .buyback_flow import (
    take_task_callback,
    handle_step_response,
    step_confirm_callback,
    step_choice_callback,
    cancel_buyback_callback,
    cancel_command,
    STEP_RESPONSE,
)


def register_handlers(application):
    """Регистрация всех обработчиков"""

    # ConversationHandler для прохождения выкупа
    buyback_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(take_task_callback, pattern=r'^take_task:\d+$'),
        ],
        states={
            STEP_RESPONSE: [
                MessageHandler(filters.PHOTO, handle_step_response),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_step_response),
                CallbackQueryHandler(step_confirm_callback, pattern=r'^step_confirm:\d+$'),
                CallbackQueryHandler(step_choice_callback, pattern=r'^step_choice:\d+:.+$'),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_command),
            CallbackQueryHandler(cancel_buyback_callback, pattern=r'^cancel_buyback:\d+$'),
        ],
        per_user=True,
        per_chat=True,
    )

    application.add_handler(buyback_conv)

    # Команды
    application.add_handler(CommandHandler('start', start_handler))

    # Онбординг
    application.add_handler(CallbackQueryHandler(onboarding_callback, pattern=r'^onboard:.+$'))

    # Кнопки меню (текстовые)
    application.add_handler(MessageHandler(
        filters.Regex('^📋 Доступные задания$'), tasks_list_handler
    ))
    application.add_handler(MessageHandler(
        filters.Regex('^📦 Мои выкупы$'), my_buybacks_handler
    ))
    application.add_handler(MessageHandler(
        filters.Regex('^👤 Профиль$'), profile_handler
    ))
    application.add_handler(MessageHandler(
        filters.Regex('^❓ Помощь$'), help_handler
    ))

    # Callback handlers
    application.add_handler(CallbackQueryHandler(task_detail_callback, pattern=r'^task_detail:\d+$'))
    application.add_handler(CallbackQueryHandler(tasks_list_callback, pattern=r'^tasks_list$'))