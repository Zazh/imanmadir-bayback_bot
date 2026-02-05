from django.contrib import admin
from .models import Payout


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user',
        'amount',
        'payment_bank',
        'status',
        'processed_by',
        'created_at',
    ]
    list_filter = ['status', 'payment_bank', 'created_at']
    search_fields = [
        'user__username',
        'user__telegram_id',
        'payment_phone',
        'payment_name',
    ]
    readonly_fields = [
        'buyback',
        'user',
        'amount',
        'payment_phone',
        'payment_bank',
        'payment_name',
        'created_at',
    ]
    list_editable = ['status']

    fieldsets = [
        ('Выкуп', {
            'fields': ['buyback', 'user', 'amount'],
        }),
        ('Реквизиты', {
            'fields': ['payment_phone', 'payment_bank', 'payment_name'],
        }),
        ('Статус', {
            'fields': ['status', 'processed_by', 'processed_at'],
        }),
        ('Заметки', {
            'fields': ['notes'],
        }),
        ('Даты', {
            'fields': ['created_at'],
            'classes': ['collapse'],
        }),
    ]