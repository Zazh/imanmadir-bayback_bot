from django.contrib import admin
from .models import Product, Task
from steps.models import TaskStep


class TaskStepInline(admin.TabularInline):
    model = TaskStep
    extra = 1
    ordering = ['order']
    fields = [
        'order',
        'title',
        'step_type',
        'instruction',
        'image',
        'publish_time',
        'timeout_minutes',
        'requires_moderation',
    ]


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
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'wb_article']
    list_editable = ['price', 'quantity_total', 'is_active']
    readonly_fields = ['quantity_completed', 'created_at', 'updated_at']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'product', 'payout', 'is_active', 'created_at']
    list_filter = ['is_active', 'product', 'created_at']
    search_fields = ['title', 'product__name']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [TaskStepInline]