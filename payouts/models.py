from django.db import models
from django.conf import settings
from django.utils import timezone


class Payout(models.Model):
    """Выплата за выкуп"""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает'
        PROCESSING = 'processing', 'В обработке'
        COMPLETED = 'completed', 'Выплачено'
        FAILED = 'failed', 'Ошибка'

    buyback = models.OneToOneField(
        'pipeline.Buyback',
        on_delete=models.PROTECT,
        related_name='payout',
        verbose_name='Выкуп',
    )
    user = models.ForeignKey(
        'account.TelegramUser',
        on_delete=models.PROTECT,
        related_name='payouts',
        verbose_name='Получатель',
    )

    amount = models.DecimalField(
        'Сумма',
        max_digits=10,
        decimal_places=2,
    )

    # Snapshot реквизитов на момент создания
    payment_phone = models.CharField(
        'Телефон',
        max_length=20,
    )
    payment_bank = models.CharField(
        'Банк',
        max_length=100,
    )
    payment_name = models.CharField(
        'ФИО получателя',
        max_length=255,
    )

    status = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Кто обработал
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_payouts',
        verbose_name='Обработал',
    )
    processed_at = models.DateTimeField(
        'Дата обработки',
        null=True,
        blank=True,
    )

    notes = models.TextField(
        'Заметки',
        blank=True,
    )

    created_at = models.DateTimeField(
        'Дата создания',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'Выплата'
        verbose_name_plural = 'Выплаты'
        ordering = ['-created_at']

    def __str__(self):
        return f'Выплата #{self.id} — {self.amount}₸ — {self.user}'

    def mark_completed(self, manager=None):
        """Отметить как выплачено"""
        self.status = self.Status.COMPLETED
        self.processed_by = manager
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processed_by', 'processed_at'])

    def mark_failed(self, manager=None, notes=''):
        """Отметить как ошибку"""
        self.status = self.Status.FAILED
        self.processed_by = manager
        self.processed_at = timezone.now()
        self.notes = notes
        self.save(update_fields=['status', 'processed_by', 'processed_at', 'notes'])

    @classmethod
    def create_from_buyback(cls, buyback):
        """Создать выплату из одобренного выкупа"""
        user = buyback.user
        return cls.objects.create(
            buyback=buyback,
            user=user,
            amount=buyback.task.payout,
            payment_phone=user.phone or '',
            payment_bank=user.bank_name or '',
            payment_name=user.card_holder_name or '',
        )