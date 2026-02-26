from django.contrib import admin
from .models import TelegramUser


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = [
        'telegram_id',
        'username',
        'first_name',
        'phone',
        'total_completed',
        'is_active',
        'is_blocked',
        'created_at',
    ]
    list_filter = [
        'is_active',
        'is_blocked',
        'created_at',
    ]
    search_fields = [
        'telegram_id',
        'username',
        'first_name',
        'last_name',
        'phone',
    ]
    readonly_fields = [
        'telegram_id',
        'total_completed',
        'created_at',
        'updated_at',
    ]
    list_editable = [
        'is_active',
        'is_blocked',
    ]
    ordering = ['-created_at']

    fieldsets = [
        ('Telegram', {
            'fields': ['telegram_id', 'username', 'first_name', 'last_name'],
        }),
        ('Реквизиты для выплат', {
            'fields': ['phone', 'bank_name', 'card_holder_name'],
        }),
        ('Статус', {
            'fields': ['is_active', 'is_blocked'],
        }),
        ('Статистика', {
            'fields': ['total_completed', 'created_at', 'updated_at'],
        }),
    ]