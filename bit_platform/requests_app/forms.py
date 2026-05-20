from django import forms
from .models import ServiceRequest, RequestComment


class ServiceRequestForm(forms.ModelForm):
    """Форма создания заявки"""
    
    class Meta:
        model = ServiceRequest
        fields = [
            'title', 'service_type', 'description',
            'company_name', 'contact_phone', 'contact_email',
            'budget_from', 'budget_to', 'deadline', 'priority'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Кратко опишите задачу'
            }),
            'service_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Подробно опишите вашу задачу, требования и пожелания'
            }),
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название вашей компании'
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+7 (___) ___-__-__'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@company.ru'
            }),
            'budget_from': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'От'
            }),
            'budget_to': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'До'
            }),
            'deadline': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }, format='%Y-%m-%d'),
            'priority': forms.Select(attrs={'class': 'form-select'}),
        }


class RequestCommentForm(forms.ModelForm):
    """Форма добавления комментария"""
    
    class Meta:
        model = RequestComment
        fields = ['text', 'is_internal']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Введите комментарий...'
            }),
            'is_internal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RequestStatusForm(forms.ModelForm):
    """Форма изменения статуса заявки (без переназначения ролей)."""

    status_comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Комментарий к смене статуса'}),
        label='Комментарий'
    )

    class Meta:
        model = ServiceRequest
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')

        if instance and user:
            # Фильтруем список статусов по допустимым переходам для роли
            allowed = instance.ALLOWED_TRANSITIONS.get(instance.status, set()) | {instance.status}
            allowed = [s for s in allowed if instance.can_transition(user, s) or s == instance.status]
            self.fields['status'].choices = [
                (value, label) for value, label in ServiceRequest.STATUS_CHOICES if value in allowed
            ]


class RequestAssignmentForm(forms.ModelForm):
    """Переназначение аналитика и исполнителя (только для администраторов)."""

    class Meta:
        model = ServiceRequest
        fields = ['analyst', 'executor']
        widgets = {
            'analyst': forms.Select(attrs={'class': 'form-select'}),
            'executor': forms.Select(attrs={'class': 'form-select'}),
        }
