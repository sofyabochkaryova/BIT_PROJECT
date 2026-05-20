from accounts.models import UserProfile


def user_role(request):
    """Добавляет информацию о роли пользователя во все шаблоны."""
    if not request.user.is_authenticated:
        return {'user_role': None, 'user_role_display': '', 'is_staff_user': False}

    profile = getattr(request.user, 'profile', None)
    if not profile:
        return {'user_role': None, 'user_role_display': '', 'is_staff_user': False}

    return {
        'user_role': profile.role,
        'user_role_display': profile.get_role_display(),
        'is_staff_user': profile.role in ('analyst', 'executor', 'admin'),
    }
