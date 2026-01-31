from telegram import Bot
from telegram.ext import Application
from django.conf import settings

# Инициализация бота
bot = Bot(token=settings.BOT_TOKEN)

# Application для webhook (без JobQueue, т.к. webhook не поддерживает его напрямую)
application = Application.builder().token(settings.BOT_TOKEN).build()