from django.db import models
from django.utils import timezone


class Task(models.Model):
    """Задание на выкуп"""

    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        related_name='tasks',
        verbose_name='Товар',
    )
    title = models.CharField(
        'Название задания',
        max_length=255,
        help_text='Например: Выкуп футболки с отзывом',
    )
    payout = models.DecimalField(
        'Выплата',
        max_digits=10,
        decimal_places=2,
        help_text='Сумма которую получит выкупщик',
    )

    is_active = models.BooleanField(
        'Активно',
        default=True,
    )

    created_at = models.DateTimeField(
        'Дата создания',
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        'Дата обновления',
        auto_now=True,
    )

    class Meta:
        verbose_name = 'Задание'
        verbose_name_plural = 'Задания'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_available(self):
        """Доступно ли задание для взятия"""
        return self.is_active and self.product.is_active and self.product.quantity_available > 0


class TaskStep(models.Model):
    """Шаг задания"""

    class StepType(models.TextChoices):
        PHOTO = 'photo', 'Загрузка фото'
        ARTICLE_CHECK = 'article_check', 'Проверка артикула'
        TEXT_MODERATED = 'text_moderated', 'Текст с модерацией'
        CONFIRM = 'confirm', 'Подтверждение'
        ORDER_NUMBER = 'order_number', 'Номер заказа'
        CHOICE = 'choice', 'Выбор варианта'

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name='Задание',
    )
    order = models.PositiveIntegerField(
        'Порядок',
    )
    step_type = models.CharField(
        'Тип шага',
        max_length=20,
        choices=StepType.choices,
    )
    instruction = models.TextField(
        'Инструкция',
        help_text='Текст, который увидит пользователь',
    )
    image = models.ImageField(
        'Изображение',
        upload_to='task_steps/',
        blank=True,
        help_text='Опциональная картинка-инструкция для шага',
    )
    settings = models.JSONField(
        'Настройки',
        default=dict,
        blank=True,
        help_text='correct_article, choices, hint и т.д.',
    )
    timeout_hours = models.PositiveIntegerField(
        'Таймаут (часы)',
        null=True,
        blank=True,
        help_text='Оставьте пустым если без ограничения',
    )
    requires_moderation = models.BooleanField(
        'Требует модерации',
        default=False,
        help_text='Если включено — ответ отправляется на проверку модератору',
    )

    class Meta:
        verbose_name = 'Шаг задания'
        verbose_name_plural = 'Шаги заданий'
        ordering = ['task', 'order']
        unique_together = ['task', 'order']

    def __str__(self):
        return f'{self.task.title} — Шаг {self.order}'


class Buyback(models.Model):
    """Выкуп пользователя"""

    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'В процессе'
        ON_REVIEW = 'on_review', 'На проверке'
        COMPLETED = 'completed', 'Завершён'
        PAID = 'paid', 'Оплачен'
        CANCELLED = 'cancelled', 'Отменён'
        EXPIRED = 'expired', 'Истёк'

    task = models.ForeignKey(
        Task,
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

    started_at = models.DateTimeField(
        'Дата начала',
        auto_now_add=True,
    )
    completed_at = models.DateTimeField(
        'Дата завершения',
        null=True,
        blank=True,
    )
    paid_at = models.DateTimeField(
        'Дата выплаты',
        null=True,
        blank=True,
    )

    admin_notes = models.TextField(
        'Заметки админа',
        blank=True,
    )

    class Meta:
        verbose_name = 'Выкуп'
        verbose_name_plural = 'Выкупы'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.task.title} — {self.user}'

    def get_current_step(self):
        """Получить текущий объект шага"""
        return self.task.steps.filter(order=self.current_step).first()

    def advance_step(self):
        """Перейти к следующему шагу"""
        next_step = self.task.steps.filter(order__gt=self.current_step).first()
        if next_step:
            self.current_step = next_step.order
            self.save(update_fields=['current_step'])
            return True
        return False

    def complete(self):
        """Завершить выкуп"""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])

        # Обновляем счётчик товара
        self.task.product.quantity_completed += 1
        self.task.product.save(update_fields=['quantity_completed'])

        # Обновляем счётчик пользователя
        self.user.total_completed += 1
        self.user.save(update_fields=['total_completed'])

    def mark_paid(self):
        """Отметить как оплаченный"""
        self.status = self.Status.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=['status', 'paid_at'])


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
        TaskStep,
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
    admin_edited_text = models.TextField(
        'Исправленный текст',
        blank=True,
        help_text='Для text_moderated — текст после правок админа',
    )

    created_at = models.DateTimeField(
        'Дата создания',
        auto_now_add=True,
    )
    deadline_at = models.DateTimeField(
        'Дедлайн',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'Ответ на шаг'
        verbose_name_plural = 'Ответы на шаги'
        ordering = ['buyback', 'step__order']

    def __str__(self):
        return f'{self.buyback} — Шаг {self.step.order}'