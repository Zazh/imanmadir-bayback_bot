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
    language_code = models.CharField(
        'Язык',
        max_length=10,
        blank=True,
        default='',
    )

    # Реквизиты для выплат
    phone = models.CharField(
        'Телефон привязанный к банку',
        max_length=20,
        blank=True,
        help_text='Номер телефона для перевода',
    )
    bank_name = models.CharField(
        'Название банка',
        max_length=100,
        blank=True,
        help_text='Например: Kaspi, Halyk, Jusan',
    )
    card_holder_name = models.CharField(
        'ФИО владельца карты',
        max_length=255,
        blank=True,
        help_text='Имя как на банковской карте',
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

    bonus_bot_user = models.BooleanField(
        'Пользователь бонус-бота',
        default=False,
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
        """Указаны ли все реквизиты для выплат"""
        return bool(self.phone and self.bank_name and self.card_holder_name)

    @property
    def payment_info_display(self):
        """Отображение реквизитов"""
        if not self.has_payment_info:
            return 'Не заполнены'
        return f'{self.bank_name}: {self.phone} ({self.card_holder_name})'