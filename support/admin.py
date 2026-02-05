from django.contrib import admin
from .models import Ticket, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 1
    readonly_fields = ['sender_type', 'sender_manager', 'created_at']
    fields = ['sender_type', 'sender_manager', 'text', 'is_read', 'created_at']


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'ticket_type', 'subject', 'status', 'assigned_to', 'created_at']
    list_filter = ['status', 'ticket_type', 'created_at']
    search_fields = ['user__username', 'user__telegram_id', 'subject']
    list_editable = ['status', 'assigned_to']
    readonly_fields = ['user', 'buyback', 'buyback_response', 'created_at', 'updated_at']
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'sender_type', 'text_short', 'is_read', 'created_at']
    list_filter = ['sender_type', 'is_read', 'created_at']
    readonly_fields = ['ticket', 'sender_type', 'sender_manager', 'created_at']

    def text_short(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_short.short_description = 'Текст'