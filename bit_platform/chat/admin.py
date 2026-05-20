from django.contrib import admin
from .models import Conversation, Message, MessageReaction


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('author', 'created_at')
    fields = ('author', 'text', 'attachment', 'created_at')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'conversation_type', 'get_participants_count', 'created_at')
    list_filter = ('conversation_type', 'created_at')
    search_fields = ('title', 'participants__username')
    filter_horizontal = ('participants',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [MessageInline]
    
    def get_participants_count(self, obj):
        return obj.participants.count()
    get_participants_count.short_description = 'Участников'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'conversation', 'short_text', 'is_edited', 'created_at')
    list_filter = ('created_at', 'is_edited')
    search_fields = ('text', 'author__username')
    raw_id_fields = ('conversation', 'author')
    readonly_fields = ('created_at', 'edited_at')
    
    def short_text(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    short_text.short_description = 'Текст'


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'emoji', 'created_at')
    list_filter = ('emoji', 'created_at')
    raw_id_fields = ('message', 'user')
