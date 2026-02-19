from django.core.management.base import BaseCommand
from telegram.ext import Application
from django.conf import settings

from bot.handlers import register_handlers
from bot.reminders import check_reminders_job, check_timeouts_job, check_step_reminders_job


class Command(BaseCommand):
    help = 'Запуск бота в режиме polling'

    def handle(self, *args, **options):
        self.stdout.write('🤖 Запуск бота...')

        application = Application.builder().token(settings.BOT_TOKEN).build()
        register_handlers(application)

        # Периодическая проверка напоминаний (publish_review) каждые 30 секунд
        application.job_queue.run_repeating(
            check_reminders_job,
            interval=30,
            first=10,
            name='check_reminders',
        )

        # Проверка таймаутов каждые 60 секунд
        application.job_queue.run_repeating(
            check_timeouts_job,
            interval=60,
            first=15,
            name='check_timeouts',
        )

        # Напоминания по шагам каждые 60 секунд
        application.job_queue.run_repeating(
            check_step_reminders_job,
            interval=60,
            first=20,
            name='check_step_reminders',
        )

        self.stdout.write('📅 Планировщик задач запущен')
        self.stdout.write(self.style.SUCCESS('✅ Бот запущен'))
        application.run_polling(drop_pending_updates=True)