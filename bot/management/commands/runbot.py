from django.core.management.base import BaseCommand
from telegram.ext import Application

from django.conf import settings
from bot.handlers import register_handlers


class Command(BaseCommand):
    help = 'Запуск бота в режиме polling (для разработки)'

    def handle(self, *args, **options):
        self.stdout.write('🤖 Запуск бота в режиме polling...')

        # Создаём application с JobQueue
        application = (
            Application.builder()
            .token(settings.BOT_TOKEN)
            .post_init(self.post_init)
            .build()
        )

        # Регистрируем handlers
        register_handlers(application)

        # Запускаем polling
        application.run_polling(drop_pending_updates=True)

    async def post_init(self, application: Application):
        """Инициализация после запуска"""
        self.stdout.write('✅ JobQueue инициализирован')