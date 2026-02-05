from django.contrib import admin
from .models import Buyback, BuybackResponse


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
    ]
    list_filter = ['status', 'task', 'started_at']
    search_fields = ['task__title', 'user__username', 'user__telegram_id']
    readonly_fields = ['task', 'user', 'started_at', 'completed_at']
    list_editable = ['status']
    inlines = [BuybackResponseInline]


@admin.register(BuybackResponse)
class BuybackResponseAdmin(admin.ModelAdmin):
    list_display = ['buyback', 'step', 'status', 'created_at']
    list_filter = ['status', 'step__step_type', 'created_at']
    readonly_fields = ['buyback', 'step', 'response_data', 'created_at']
    list_editable = ['status']