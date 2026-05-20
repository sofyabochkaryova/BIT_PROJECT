from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Conversation(models.Model):
    """Диалог/переписка"""
    
    TYPE_CHOICES = [
        ('private', 'Личная переписка'),
        ('request', 'Переписка по заявке'),
        ('project', 'Переписка по проекту'),
        ('group', 'Групповой чат'),
    ]
    
    title = models.CharField('Название', max_length=200, blank=True)
    conversation_type = models.CharField('Тип', max_length=20, choices=TYPE_CHOICES, default='private')
    
    participants = models.ManyToManyField(
        User, related_name='conversations', verbose_name='Участники'
    )
    
    # Связи с объектами
    related_request = models.ForeignKey(
        'requests_app.ServiceRequest', on_delete=models.CASCADE,
        null=True, blank=True, related_name='chats', verbose_name='Связанная заявка'
    )
    related_project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE,
        null=True, blank=True, related_name='chats', verbose_name='Связанный проект'
    )
    
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)
    
    class Meta:
        verbose_name = 'Диалог'
        verbose_name_plural = 'Диалоги'
        ordering = ['-updated_at']
    
    def __str__(self):
        if self.title:
            return self.title
        participants = self.participants.all()[:3]
        names = ', '.join([u.get_full_name() or u.username for u in participants])
        return f'Чат: {names}'
    
    def get_other_participant(self, user):
        """Получить собеседника в личной переписке"""
        return self.participants.exclude(pk=user.pk).first()
    
    @property
    def last_message(self):
        return self.messages.order_by('-created_at').first()
    
    def unread_count(self, user):
        """Количество непрочитанных сообщений для пользователя"""
        return self.messages.exclude(author=user).filter(read_by__isnull=True).count()


class Message(models.Model):
    """Сообщение в чате"""
    
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE,
        related_name='messages', verbose_name='Диалог'
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='sent_messages', verbose_name='Автор'
    )
    
    text = models.TextField('Текст сообщения', blank=True, default='')
    
    # Прочтения
    read_by = models.ManyToManyField(
        User, blank=True,
        related_name='read_messages', verbose_name='Прочитано'
    )
    
    # Вложения
    attachment = models.FileField(
        'Вложение', upload_to='chat/attachments/%Y/%m/',
        blank=True, null=True
    )
    
    # Редактирование
    is_edited = models.BooleanField('Редактировано', default=False)
    edited_at = models.DateTimeField('Время редактирования', null=True, blank=True)
    
    created_at = models.DateTimeField('Отправлено', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['created_at']
    
    def __str__(self):
        return f'{self.author.username}: {self.text[:50]}'
    
    def mark_as_read(self, user):
        """Отметить как прочитанное"""
        if user != self.author:
            self.read_by.add(user)
    
    @property
    def is_file(self):
        return bool(self.attachment)
    
    @property
    def file_name(self):
        if self.attachment:
            return self.attachment.name.split('/')[-1]
        return None
    
    @property
    def file_extension(self):
        if self.attachment:
            return self.file_name.split('.')[-1].lower()
        return None
    
    @property
    def is_image(self):
        if self.file_extension:
            return self.file_extension in ['jpg', 'jpeg', 'png', 'gif', 'webp']
        return False


class MessageReaction(models.Model):
    """Реакция на сообщение"""
    
    EMOJI_CHOICES = [
        ('👍', 'Нравится'),
        ('❤️', 'Сердце'),
        ('😂', 'Смех'),
        ('😮', 'Удивление'),
        ('😢', 'Грусть'),
        ('🎉', 'Праздник'),
    ]
    
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE,
        related_name='reactions', verbose_name='Сообщение'
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='message_reactions', verbose_name='Пользователь'
    )
    emoji = models.CharField('Эмодзи', max_length=10, choices=EMOJI_CHOICES)
    created_at = models.DateTimeField('Добавлено', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Реакция'
        verbose_name_plural = 'Реакции'
        unique_together = ['message', 'user', 'emoji']
    
    def __str__(self):
        return f'{self.user.username} - {self.emoji}'
