from telegram.ext import Application
from django.conf import settings

application = Application.builder().token(settings.BOT_TOKEN).build()