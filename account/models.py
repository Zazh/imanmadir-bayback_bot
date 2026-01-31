from django.db import models


class TelegramUser(models.Model):
    """Пользователь Telegram (выкупщик)"""

    telegram_id = models.BigIntegerField(
        'Telegram ID',
        unique=True,
        db_index=True,
    )
    username = models.CharField(
        'Username',
        max_length=255,
        blank=True,
    )
    first_name = models.CharField(
        'Имя',
        max_length=255,
        blank=True,
    )
    last_name = models.CharField(
        'Фамилия',
        max_length=255,
        blank=True,
    )
    phone = models.CharField(
        'Телефон',
        max_length=20,
        blank=True,
        help_text='Для связи по выплатам',
    )
    card_number = models.CharField(
        'Номер карты',
        max_length=30,
        blank=True,
        help_text='Для выплат',
    )

    # Онбординг
    is_onboarded = models.BooleanField(
        'Прошёл онбординг',
        default=False,
    )
    has_excluded_reviews = models.BooleanField(
        'Исключали отзывы',
        null=True,
        blank=True,
        help_text='Ответ на вопрос об исключении отзывов',
    )

    is_active = models.BooleanField(
        'Активен',
        default=True,
    )
    is_blocked = models.BooleanField(
        'Заблокирован',
        default=False,
    )

    total_completed = models.PositiveIntegerField(
        'Выполнено выкупов',
        default=0,
    )

    created_at = models.DateTimeField(
        'Дата регистрации',
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        'Дата обновления',
        auto_now=True,
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['-created_at']

    def __str__(self):
        if self.username:
            return f'@{self.username}'
        if self.first_name:
            return self.first_name
        return f'User {self.telegram_id}'

    @property
    def display_name(self):
        """Отображаемое имя для бота"""
        if self.first_name:
            return self.first_name
        if self.username:
            return f'@{self.username}'
        return f'User {self.telegram_id}'

    @property
    def has_payment_info(self):
        """Указаны ли реквизиты для выплат"""
        return bool(self.card_number)