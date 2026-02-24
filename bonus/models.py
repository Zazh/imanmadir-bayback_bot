from django.db import models


class BonusMessage(models.Model):
    class SenderType(models.TextChoices):
        USER = 'user', 'Пользователь'
        MANAGER = 'manager', 'Менеджер'

    user = models.ForeignKey(
        'account.TelegramUser',
        on_delete=models.CASCADE,
        related_name='bonus_messages',
        verbose_name='Пользователь',
    )
    sender_type = models.CharField(
        'Отправитель',
        max_length=10,
        choices=SenderType.choices,
    )
    text = models.TextField(
        'Текст сообщения',
    )
    is_read = models.BooleanField(
        'Прочитано',
        default=False,
    )
    telegram_message_id = models.BigIntegerField(
        'Telegram Message ID',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(
        'Дата',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'Сообщение бонус-бота'
        verbose_name_plural = 'Сообщения бонус-бота'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.get_sender_type_display()}: {self.text[:50]}'
