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
    PUBLISH_REVIEW = 'publish_review', 'Публикация отзыва'


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

    # Для шага публикации отзыва
    publish_time = models.TimeField(
        'Время публикации (МСК)',
        null=True,
        blank=True,
        help_text='Только для типа "Публикация отзыва"',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_image = self.image.name if self.image else None

    def save(self, *args, **kwargs):
        if self.image and self.image.name != self._original_image:
            from core.image_utils import compress_image
            new_image = compress_image(self.image)
            if new_image:
                self.image = new_image
        super().save(*args, **kwargs)
        self._original_image = self.image.name if self.image else None

    def __str__(self):
        return f'{self.task.title} — Шаг {self.order}'


class StepTemplate(models.Model):
    """Шаблон шагов задания"""

    name = models.CharField(
        'Название шаблона',
        max_length=255,
        unique=True,
    )
    created_at = models.DateTimeField(
        'Дата создания',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'Шаблон шагов'
        verbose_name_plural = 'Шаблоны шагов'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class StepTemplateItem(models.Model):
    """Шаг внутри шаблона"""

    template = models.ForeignKey(
        StepTemplate,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Шаблон',
    )
    order = models.PositiveIntegerField('Порядок')
    title = models.CharField(
        'Заголовок',
        max_length=255,
        blank=True,
    )
    step_type = models.CharField(
        'Тип шага',
        max_length=20,
        choices=StepType.choices,
    )
    instruction = models.TextField('Инструкция')
    image = models.ImageField(
        'Изображение',
        upload_to='step_templates/',
        blank=True,
    )
    settings = models.JSONField(
        'Настройки',
        default=dict,
        blank=True,
    )
    publish_time = models.TimeField(
        'Время публикации (МСК)',
        null=True,
        blank=True,
    )
    timeout_minutes = models.PositiveIntegerField(
        'Таймаут (минут)',
        null=True,
        blank=True,
    )
    reminder_minutes = models.PositiveIntegerField(
        'Напоминание через (минут)',
        null=True,
        blank=True,
    )
    reminder_text = models.TextField(
        'Текст напоминания',
        blank=True,
    )
    requires_moderation = models.BooleanField(
        'Требует модерации',
        default=False,
    )

    class Meta:
        verbose_name = 'Шаг шаблона'
        verbose_name_plural = 'Шаги шаблона'
        ordering = ['template', 'order']
        unique_together = ['template', 'order']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_image = self.image.name if self.image else None

    def save(self, *args, **kwargs):
        if self.image and self.image.name != self._original_image:
            from core.image_utils import compress_image
            new_image = compress_image(self.image)
            if new_image:
                self.image = new_image
        super().save(*args, **kwargs)
        self._original_image = self.image.name if self.image else None

    def __str__(self):
        return f'{self.template.name} — Шаг {self.order}'