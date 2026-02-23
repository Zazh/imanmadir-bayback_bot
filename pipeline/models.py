from django.db import models
from django.utils import timezone


class Buyback(models.Model):
    """Выкуп пользователя"""

    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'В процессе'
        ON_MODERATION = 'on_moderation', 'На модерации'
        PENDING_REVIEW = 'pending_review', 'Ожидает проверки'
        APPROVED = 'approved', 'Одобрен'
        REJECTED = 'rejected', 'Отклонён'
        CANCELLED = 'cancelled', 'Отменён'
        EXPIRED = 'expired', 'Истёк'

    task = models.ForeignKey(
        'catalog.Task',
        on_delete=models.PROTECT,
        related_name='buybacks',
        verbose_name='Задание',
    )
    user = models.ForeignKey(
        'account.TelegramUser',
        on_delete=models.PROTECT,
        related_name='buybacks',
        verbose_name='Пользователь',
    )

    current_step = models.PositiveIntegerField(
        'Текущий шаг',
        default=1,
    )
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )

    rejection_reason = models.TextField(
        'Причина отклонения',
        blank=True,
    )
    admin_notes = models.TextField(
        'Заметки',
        blank=True,
    )

    custom_publish_at = models.DateTimeField(
        'Назначенное время публикации',
        null=True,
        blank=True,
        help_text='Если задано — используется вместо стандартного времени из шага',
    )

    step_started_at = models.DateTimeField(
        'Начало текущего шага',
        null=True,
        blank=True,
        help_text='Когда пользователь начал текущий шаг',
    )
    reminder_sent = models.BooleanField(
        'Напоминание отправлено',
        default=False,
    )

    started_at = models.DateTimeField(
        'Дата начала',
        auto_now_add=True,
    )
    completed_at = models.DateTimeField(
        'Дата завершения',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'Выкуп'
        verbose_name_plural = 'Выкупы'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.task.title} — {self.user}'

    def complete(self):
        """Завершить выкуп (все шаги пройдены)"""
        self.status = self.Status.PENDING_REVIEW
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])

    def approve(self):
        """Одобрить выкуп"""
        self.status = self.Status.APPROVED
        self.save(update_fields=['status'])

        # Обновляем счётчики
        self.task.product.quantity_completed += 1
        self.task.product.save(update_fields=['quantity_completed'])

        self.user.total_completed += 1
        self.user.save(update_fields=['total_completed'])

    def reject(self, reason: str = ''):
        """Отклонить выкуп"""
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.save(update_fields=['status', 'rejection_reason'])


class BuybackResponse(models.Model):
    """Ответ на шаг выкупа"""

    class Status(models.TextChoices):
        PENDING = 'pending', 'На проверке'
        APPROVED = 'approved', 'Одобрен'
        REJECTED = 'rejected', 'Отклонён'
        AUTO_APPROVED = 'auto_approved', 'Авто-одобрен'

    buyback = models.ForeignKey(
        Buyback,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name='Выкуп',
    )
    step = models.ForeignKey(
        'steps.TaskStep',
        on_delete=models.PROTECT,
        related_name='responses',
        verbose_name='Шаг',
    )

    response_data = models.JSONField(
        'Данные ответа',
        default=dict,
        help_text='photo, text, value и т.д.',
    )

    status = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    moderator_comment = models.TextField(
        'Комментарий модератора',
        blank=True,
    )

    created_at = models.DateTimeField(
        'Дата создания',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'Ответ на шаг'
        verbose_name_plural = 'Ответы на шаги'
        ordering = ['buyback', 'step__order']

    def __str__(self):
        return f'{self.buyback} — Шаг {self.step.order}'


class ReviewReminder(models.Model):
    """Напоминание о публикации отзыва"""

    class ReminderType(models.TextChoices):
        BEFORE_3H = 'before_3h', 'За 3 часа'
        BEFORE_2H = 'before_2h', 'За 2 часа'
        BEFORE_1H = 'before_1h', 'За 1 час'
        BEFORE_5M = 'before_5m', 'За 5 минут'
        OVERDUE = 'overdue', 'Просрочено'

    buyback = models.ForeignKey(
        Buyback,
        on_delete=models.CASCADE,
        related_name='reminders',
        verbose_name='Выкуп',
    )
    step = models.ForeignKey(
        'steps.TaskStep',
        on_delete=models.CASCADE,
        related_name='reminders',
        verbose_name='Шаг',
    )

    reminder_type = models.CharField(
        'Тип напоминания',
        max_length=20,
        choices=ReminderType.choices,
    )
    scheduled_at = models.DateTimeField(
        'Запланировано на',
    )
    sent_at = models.DateTimeField(
        'Отправлено',
        null=True,
        blank=True,
    )
    is_cancelled = models.BooleanField(
        'Отменено',
        default=False,
    )
    overdue_count = models.PositiveIntegerField(
        'Счётчик просрочки',
        default=0,
        help_text='Сколько раз отправлено напоминание о просрочке',
    )

    created_at = models.DateTimeField(
        'Создано',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'Напоминание'
        verbose_name_plural = 'Напоминания'
        ordering = ['scheduled_at']

    def __str__(self):
        return f'{self.buyback} — {self.get_reminder_type_display()}'