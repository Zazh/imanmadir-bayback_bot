from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'wb_article',
        'price',
        'quantity_total',
        'quantity_completed',
        'limit_per_user',
        'is_active',
    ]
    list_filter = [
        'is_active',
        'created_at',
    ]
    search_fields = [
        'name',
        'wb_article',
    ]
    list_editable = [
        'price',
        'quantity_total',
        'is_active',
    ]
    readonly_fields = [
        'quantity_completed',
        'created_at',
        'updated_at',
    ]

    fieldsets = [
        (None, {
            'fields': ['name', 'wb_article', 'price'],
        }),
        ('Медиа', {
            'fields': ['image', 'description'],
        }),
        ('Количество', {
            'fields': ['quantity_total', 'quantity_completed'],
            'description': 'Общее количество товаров для выкупа',
        }),
        ('Персональные ограничения', {
            'fields': ['limit_per_user', 'limit_per_user_days'],
            'description': 'Лимиты на одного пользователя',
        }),
        ('Статус', {
            'fields': ['is_active'],
        }),
        ('Даты', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]