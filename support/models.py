from django.db import models
from django.conf import settings


class Ticket(models.Model):
    """Тикет поддержки / диалог с менеджером"""

    class Status(models.TextChoices):
        OPEN = 'open', 'Открыт'
        IN_PROGRESS = 'in_progress', 'В работе'
        RESOLVED = 'resolved', 'Решён'
        CLOSED = 'closed', 'Закрыт'

    class Type(models.TextChoices):
        MODERATION = 'moderation', 'Модерация шага'
        REVIEW = 'review', 'Проверка выкупа'
        PAYOUT = 'payout', 'Вопрос по выплате'
        GENERAL = 'general', 'Общий вопрос'

    user = models.ForeignKey(
        'account.TelegramUser',
        on_delete=models.CASCADE,
        related_name='tickets',
        verbose_name='Пользователь',
    )
    buyback = models.ForeignKey(
        'pipeline.Buyback',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        verbose_name='Выкуп',
    )
    buyback_response = models.ForeignKey(
        'pipeline.BuybackResponse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        verbose_name='Ответ на шаг',
    )

    ticket_type = models.CharField(
        'Тип',
        max_length=20,
        choices=Type.choices,
        default=Type.GENERAL,
    )
    subject = models.CharField(
        'Тема',
        max_length=255,
        blank=True,
    )
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        verbose_name='Назначен',
    )

    created_at = models.DateTimeField(
        'Создан',
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        'Обновлён',
        auto_now=True,
    )

    class Meta:
        verbose_name = 'Тикет'
        verbose_name_plural = 'Тикеты'
        ordering = ['-created_at']

    def __str__(self):
        return f'#{self.id} — {self.user} — {self.get_status_display()}'


class Message(models.Model):
    """Сообщение в тикете"""

    class SenderType(models.TextChoices):
        USER = 'user', 'Клиент'
        MANAGER = 'manager', 'Менеджер'
        SYSTEM = 'system', 'Система'

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Тикет',
    )

    sender_type = models.CharField(
        'Отправитель',
        max_length=20,
        choices=SenderType.choices,
    )
    sender_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_messages',
        verbose_name='Менеджер',
    )

    text = models.TextField(
        'Текст',
    )
    attachment = models.FileField(
        'Вложение',
        upload_to='support/',
        blank=True,
    )

    is_read = models.BooleanField(
        'Прочитано',
        default=False,
    )
    created_at = models.DateTimeField(
        'Создано',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.get_sender_type_display()}: {self.text[:50]}'