from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """Профиль пользователя с ролями"""
    
    ROLE_CHOICES = [
        ('client', 'Клиент'),
        ('analyst', 'Аналитик'),
        ('executor', 'Исполнитель'),
        ('admin', 'Администратор'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField('Роль', max_length=20, choices=ROLE_CHOICES, default='client')
    phone = models.CharField('Телефон', max_length=20, blank=True)
    company = models.CharField('Компания', max_length=200, blank=True)
    position = models.CharField('Должность', max_length=100, blank=True)
    department = models.CharField('Отдел', max_length=100, blank=True)
    avatar = models.ImageField('Аватар', upload_to='avatars/', blank=True, null=True)
    bio = models.TextField('О себе', blank=True)
    telegram = models.CharField('Telegram', max_length=100, blank=True)
    created_at = models.DateTimeField('Дата регистрации', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'
    
    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'
    
    @property
    def is_client(self):
        return self.role == 'client'
    
    @property
    def is_analyst(self):
        return self.role == 'analyst'
    
    @property
    def is_executor(self):
        return self.role == 'executor'
    
    @property
    def is_admin(self):
        return self.role == 'admin'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Автоматическое создание профиля при создании пользователя"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Сохранение профиля при сохранении пользователя"""
    if hasattr(instance, 'profile'):
        instance.profile.save()
