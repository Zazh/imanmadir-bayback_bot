from django.core.management.base import BaseCommand
from django.conf import settings
import requests


class Command(BaseCommand):
    help = 'Установка webhook для Telegram бота'

    def add_arguments(self, parser):
        parser.add_argument('url', type=str, help='URL вебхука (https://yourdomain.com/bot/webhook/)')

    def handle(self, *args, **options):
        webhook_url = options['url']
        api_url = f'https://api.telegram.org/bot{settings.BOT_TOKEN}/setWebhook'

        response = requests.post(api_url, data={'url': webhook_url})
        result = response.json()

        if result.get('ok'):
            self.stdout.write(self.style.SUCCESS(f'✅ Webhook установлен: {webhook_url}'))
        else:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка: {result}'))