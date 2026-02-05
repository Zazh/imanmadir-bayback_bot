from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

from .start import start_handler, onboarding_callback
from .menu import profile_handler, help_handler
from .tasks import tasks_list_handler, task_detail_callback, tasks_list_callback
from .buybacks import my_buybacks_handler
from .flow import (
    take_task_callback,
    handle_response,
    confirm_callback,
    choice_callback,
    cancel_callback,
    resume_buyback,
    WAITING_RESPONSE,
)


def register_handlers(application):
    """Регистрация обработчиков"""

    # ConversationHandler для прохождения выкупа
    flow_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(take_task_callback, pattern=r'^take:\d+$'),
            # Возобновление выкупа при отправке фото/текста
            MessageHandler(filters.PHOTO, resume_buyback),
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^(📋|📦|👤|❓)'), resume_buyback),
        ],
        states={
            WAITING_RESPONSE: [
                MessageHandler(filters.PHOTO, handle_response),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_response),
                CallbackQueryHandler(confirm_callback, pattern=r'^confirm:\d+$'),
                CallbackQueryHandler(choice_callback, pattern=r'^choice:\d+:.+$'),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_callback, pattern=r'^cancel:\d+$'),
            CommandHandler('start', start_handler),
        ],
        per_user=True,
        per_chat=True,
    )

    application.add_handler(flow_handler)

    # Команды
    application.add_handler(CommandHandler('start', start_handler))

    # Онбординг
    application.add_handler(CallbackQueryHandler(onboarding_callback, pattern=r'^onboard:.+$'))

    # Меню
    application.add_handler(MessageHandler(filters.Regex('^📋 Задания$'), tasks_list_handler))
    application.add_handler(MessageHandler(filters.Regex('^📦 Мои выкупы$'), my_buybacks_handler))
    application.add_handler(MessageHandler(filters.Regex('^👤 Профиль$'), profile_handler))
    application.add_handler(MessageHandler(filters.Regex('^❓ Помощь$'), help_handler))

    # Задания
    application.add_handler(CallbackQueryHandler(task_detail_callback, pattern=r'^task:\d+$'))
    application.add_handler(CallbackQueryHandler(tasks_list_callback, pattern=r'^tasks_list$'))