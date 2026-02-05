from django.db import models


class StepType(models.TextChoices):
    """Типы шагов"""
    PHOTO = 'photo', 'Загрузка фото'
    ARTICLE_CHECK = 'article_check', 'Проверка артикула'
    TEXT_MODERATED = 'text_moderated', 'Текст с модерацией'
    CONFIRM = 'confirm', 'Подтверждение'
    ORDER_NUMBER = 'order_number', 'Номер заказа'
    CHOICE = 'choice', 'Выбор варианта'
    CHECK_LINK = 'check_link', 'Ссылка на чек'
    PAYMENT_DETAILS = 'payment_details', 'Реквизиты для выплаты'


class TaskStep(models.Model):
    """Шаг задания"""

    task = models.ForeignKey(
        'catalog.Task',
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name='Задание',
    )
    order = models.PositiveIntegerField(
        'Порядок',
    )
    title = models.CharField(
        'Заголовок',
        max_length=255,
        blank=True,
        help_text='Короткий заголовок шага',
    )
    step_type = models.CharField(
        'Тип шага',
        max_length=20,
        choices=StepType.choices,
    )
    instruction = models.TextField(
        'Инструкция',
        help_text='Текст который увидит пользователь',
    )
    image = models.ImageField(
        'Изображение',
        upload_to='task_steps/',
        blank=True,
        help_text='Картинка-инструкция для шага',
    )
    settings = models.JSONField(
        'Настройки',
        default=dict,
        blank=True,
        help_text='correct_article, choices, hint и т.д.',
    )

    # Тайминги
    timeout_minutes = models.PositiveIntegerField(
        'Таймаут (минут)',
        null=True,
        blank=True,
        help_text='Время на выполнение. Пусто = без ограничения',
    )
    reminder_minutes = models.PositiveIntegerField(
        'Напоминание через (минут)',
        null=True,
        blank=True,
    )
    reminder_text = models.TextField(
        'Текст напоминания',
        blank=True,
        help_text='Переменные: {remaining_time}, {task_title}, {step_title}',
    )

    requires_moderation = models.BooleanField(
        'Требует модерации',
        default=False,
        help_text='Если да — ответ идёт на проверку менеджеру',
    )

    class Meta:
        verbose_name = 'Шаг задания'
        verbose_name_plural = 'Шаги заданий'
        ordering = ['task', 'order']
        unique_together = ['task', 'order']

    def __str__(self):
        return f'{self.task.title} — Шаг {self.order}'