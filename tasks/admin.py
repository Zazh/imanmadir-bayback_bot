from django.contrib import admin
from .models import Task, TaskStep, Buyback, BuybackResponse


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
        'timeout_minutes',
        'reminder_minutes',
        'reminder_text',
        'requires_moderation',
        'settings',
    ]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'product',
        'payout',
        'is_active',
        'created_at',
    ]
    list_filter = [
        'is_active',
        'product',
        'created_at',
    ]
    search_fields = [
        'title',
        'product__name',
    ]
    list_editable = [
        'is_active',
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
    ]
    inlines = [TaskStepInline]

    fieldsets = [
        (None, {
            'fields': ['title', 'product', 'payout'],
        }),
        ('Статус', {
            'fields': ['is_active'],
        }),
        ('Даты', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]


class BuybackResponseInline(admin.TabularInline):
    model = BuybackResponse
    extra = 0
    readonly_fields = ['step', 'response_data', 'created_at']
    fields = ['step', 'status', 'response_data', 'moderator_comment', 'created_at']


@admin.register(Buyback)
class BuybackAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'task',
        'user',
        'current_step',
        'status',
        'started_at',
        'completed_at',
        'paid_at',
    ]
    list_filter = [
        'status',
        'task',
        'started_at',
    ]
    search_fields = [
        'task__title',
        'user__username',
        'user__telegram_id',
    ]
    readonly_fields = [
        'task',
        'user',
        'started_at',
        'completed_at',
        'paid_at',
    ]
    list_editable = [
        'status',
    ]
    inlines = [BuybackResponseInline]

    fieldsets = [
        (None, {
            'fields': ['task', 'user'],
        }),
        ('Прогресс', {
            'fields': ['current_step', 'status'],
        }),
        ('Даты', {
            'fields': ['started_at', 'completed_at', 'paid_at'],
        }),
        ('Заметки', {
            'fields': ['admin_notes'],
        }),
    ]


@admin.register(BuybackResponse)
class BuybackResponseAdmin(admin.ModelAdmin):
    list_display = [
        'buyback',
        'step',
        'status',
        'created_at',
    ]
    list_filter = [
        'status',
        'step__step_type',
        'created_at',
    ]
    readonly_fields = [
        'buyback',
        'step',
        'response_data',
        'created_at',
    ]
    list_editable = [
        'status',
    ]