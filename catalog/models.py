from django.db import models


class Product(models.Model):
    """Товар бренда"""

    name = models.CharField(
        'Название',
        max_length=255,
    )
    wb_article = models.CharField(
        'Артикул WB',
        max_length=50,
        unique=True,
        db_index=True,
    )
    price = models.DecimalField(
        'Цена на WB',
        max_digits=10,
        decimal_places=2,
        help_text='Текущая цена товара на Wildberries',
    )
    image = models.ImageField(
        'Фото товара',
        upload_to='products/',
        blank=True,
    )
    description = models.TextField(
        'Описание',
        blank=True,
        help_text='Краткое описание для выкупщиков',
    )

    quantity_total = models.PositiveIntegerField(
        'Всего на выкуп',
        default=0,
        help_text='Общее количество товаров для выкупа',
    )
    quantity_completed = models.PositiveIntegerField(
        'Выкуплено',
        default=0,
    )

    limit_per_user = models.PositiveIntegerField(
        'Лимит на пользователя',
        default=1,
        help_text='Сколько раз один человек может выкупить (0 = без лимита)',
    )
    limit_per_user_days = models.PositiveIntegerField(
        'Период лимита (дней)',
        default=0,
        help_text='За какой период считать (0 = за всё время)',
    )

    is_active = models.BooleanField(
        'Активен',
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
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['name']

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
        return f'{self.name} ({self.wb_article})'

    def get_limit_display(self):
        """Текстовое описание лимита"""
        if self.limit_per_user == 0:
            return 'Без ограничений'
        if self.limit_per_user_days == 0:
            return f'{self.limit_per_user} раз на человека'
        if self.limit_per_user_days == 1:
            return f'{self.limit_per_user} раз в сутки'
        return f'{self.limit_per_user} раз за {self.limit_per_user_days} дней'

    def get_quantity_available(self):
        """Доступно для выкупа (синхронно)"""
        from pipeline.models import Buyback

        in_progress = Buyback.objects.filter(
            task__product=self,
            status__in=[
                Buyback.Status.IN_PROGRESS,
                Buyback.Status.ON_MODERATION,
                Buyback.Status.PENDING_REVIEW,
            ]
        ).count()

        return self.quantity_total - self.quantity_completed - in_progress

    async def aget_quantity_available(self):
        """Доступно для выкупа (асинхронно)"""
        from pipeline.models import Buyback

        in_progress = await Buyback.objects.filter(
            task__product=self,
            status__in=[
                Buyback.Status.IN_PROGRESS,
                Buyback.Status.ON_MODERATION,
                Buyback.Status.PENDING_REVIEW,
            ]
        ).acount()

        return self.quantity_total - self.quantity_completed - in_progress

    async def acheck_user_limit(self, user) -> tuple[bool, str]:
        """Проверка лимита пользователя. Возвращает (can_take, message)"""
        from pipeline.models import Buyback
        from django.utils import timezone
        from datetime import timedelta

        if self.limit_per_user == 0:
            return True, ''

        queryset = Buyback.objects.filter(
            user=user,
            task__product=self,
            status__in=[
                Buyback.Status.IN_PROGRESS,
                Buyback.Status.ON_MODERATION,
                Buyback.Status.PENDING_REVIEW,
                Buyback.Status.APPROVED,
            ]
        )

        if self.limit_per_user_days > 0:
            since = timezone.now() - timedelta(days=self.limit_per_user_days)
            queryset = queryset.filter(started_at__gte=since)

        count = await queryset.acount()

        if count >= self.limit_per_user:
            return False, self.get_limit_display()

        return True, ''


class Task(models.Model):
    """Задание на выкуп"""

    product = models.ForeignKey(
        Product,
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