from django.contrib import admin
from .models import Income, Expense, Event, Document, ChatSession, ChatMessage, UploadedFile


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('date', 'amount', 'category', 'user')
    list_filter = ('category', 'date', 'user')
    search_fields = ('description', 'user__username')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('date', 'amount', 'category', 'user')
    list_filter = ('category', 'date', 'user')
    search_fields = ('description', 'user__username')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('date', 'title', 'user')
    list_filter = ('date', 'user')
    search_fields = ('title', 'description', 'user__username')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'doc_type', 'user', 'created_at')
    list_filter = ('doc_type', 'created_at', 'user')
    search_fields = ('user__username',)


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'file_type', 'user', 'file_size', 'uploaded_at', 'processed')
    list_filter = ('file_type', 'processed', 'uploaded_at', 'user')
    search_fields = ('original_name', 'user__username')
    readonly_fields = ('uploaded_at', 'file_size')


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'title', 'user', 'created_at', 'updated_at', 'message_count')
    list_filter = ('created_at', 'user')
    readonly_fields = ('created_at', 'updated_at')
    search_fields = ('session_id', 'title', 'user__username')
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Сообщений'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'role', 'content_preview', 'user', 'created_at')
    list_filter = ('role', 'created_at', 'session')
    readonly_fields = ('created_at', 'content_hash')
    search_fields = ('content', 'session__session_id', 'session__user__username')
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Содержание'
    
    def user(self, obj):
        return obj.session.user if obj.session.user else None
    user.short_description = 'Пользователь'

