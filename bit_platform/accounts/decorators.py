from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def role_required(*allowed_roles):
    """Декоратор проверки роли пользователя."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            profile = getattr(request.user, 'profile', None)
            if not profile or profile.role not in allowed_roles:
                messages.error(request, 'Доступ запрещён')
                return redirect('accounts:dashboard')
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


analyst_required = role_required('analyst', 'admin')
executor_required = role_required('executor', 'admin')
client_required = role_required('client', 'admin')
