from django.core.management.base import BaseCommand
from telegram.ext import Application
from django.conf import settings

from bot.handlers import register_handlers


class Command(BaseCommand):
    help = 'Запуск бота в режиме polling'

    def handle(self, *args, **options):
        self.stdout.write('🤖 Запуск бота...')

        application = Application.builder().token(settings.BOT_TOKEN).build()
        register_handlers(application)

        self.stdout.write(self.style.SUCCESS('✅ Бот запущен'))
        application.run_polling(drop_pending_updates=True)