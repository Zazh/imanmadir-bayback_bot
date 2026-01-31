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

    # Общее количество
    quantity_total = models.PositiveIntegerField(
        'Всего на выкуп',
        default=0,
        help_text='Общее количество товаров доступных для выкупа',
    )
    quantity_completed = models.PositiveIntegerField(
        'Выкуплено',
        default=0,
    )

    # Персональные ограничения
    limit_per_user = models.PositiveIntegerField(
        'Лимит на пользователя',
        default=1,
        help_text='Сколько раз один человек может выкупить (0 = без лимита)',
    )
    limit_per_user_days = models.PositiveIntegerField(
        'Период лимита (дней)',
        default=0,
        help_text='За какой период считать (0 = за всё время, 1 = в сутки)',
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

    def __str__(self):
        return f'{self.name} ({self.wb_article})'

    @property
    def quantity_available(self):
        """Доступно для выкупа (синхронно, для админки)"""
        from tasks.models import Buyback
        in_progress = Buyback.objects.filter(
            task__product=self,
            status__in=[Buyback.Status.IN_PROGRESS, Buyback.Status.ON_REVIEW]
        ).count()
        return self.quantity_total - self.quantity_completed - in_progress

    async def aget_quantity_available(self):
        """Доступно для выкупа (асинхронно, для бота)"""
        from tasks.models import Buyback
        in_progress = await Buyback.objects.filter(
            task__product=self,
            status__in=[Buyback.Status.IN_PROGRESS, Buyback.Status.ON_REVIEW]
        ).acount()
        return self.quantity_total - self.quantity_completed - in_progress

    def get_limit_display(self):
        """Текстовое описание лимита"""
        if self.limit_per_user == 0:
            return 'Без ограничений'
        if self.limit_per_user_days == 0:
            return f'{self.limit_per_user} раз на человека'
        if self.limit_per_user_days == 1:
            return f'{self.limit_per_user} раз в сутки'
        return f'{self.limit_per_user} раз за {self.limit_per_user_days} дней'