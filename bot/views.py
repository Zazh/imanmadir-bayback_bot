import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from telegram import Update

from .loader import application
from .handlers import register_handlers

# Регистрируем handlers один раз
register_handlers(application)


@csrf_exempt
@require_POST
async def webhook(request):
    """Обработка webhook от Telegram"""
    try:
        data = json.loads(request.body)
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
    except Exception as e:
        print(f'Webhook error: {e}')

    return JsonResponse({'status': 'ok'})