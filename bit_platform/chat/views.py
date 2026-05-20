from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Q, Max, Count, Prefetch
from django.core.paginator import Paginator
from .models import Conversation, Message, MessageReaction
from notifications.views import create_notification
from requests_app.models import ServiceRequest


def _build_user_meta(user_obj):
    profile = getattr(user_obj, 'profile', None)
    role_code = getattr(profile, 'role', '') if profile else ''
    role_display = profile.get_role_display() if profile else 'Пользователь'
    is_client = role_code == 'client'
    group_label = 'Клиент' if is_client else 'Сотрудник'
    return {
        'id': user_obj.pk,
        'username': user_obj.username,
        'display_name': user_obj.get_full_name() or user_obj.username,
        'role_code': role_code,
        'role_display': role_display,
        'group_label': group_label,
        'is_client': is_client,
    }


@login_required
@require_GET
def widget_data(request):
    """API для виджета чата — возвращает список диалогов с непрочитанными."""
    conversations = Conversation.objects.filter(
        participants=request.user
    ).annotate(
        last_message_time=Max('messages__created_at')
    ).order_by('-last_message_time')[:10]

    total_unread = 0
    items = []
    for conv in conversations:
        unread = conv.messages.exclude(author=request.user).exclude(read_by=request.user).count()
        total_unread += unread
        last = conv.last_message
        other = conv.get_other_participant(request.user) if conv.conversation_type == 'private' else None
        items.append({
            'id': conv.pk,
            'title': conv.title or (other.get_full_name() if other else 'Чат'),
            'unread': unread,
            'last_text': (last.text[:80] if last else ''),
            'last_time': last.created_at.strftime('%H:%M') if last else '',
            'type': conv.conversation_type,
        })

    return JsonResponse({'conversations': items, 'total_unread': total_unread})


@login_required
@require_GET
def widget_messages(request, pk):
    """API для виджета чата — возвращает последние сообщения диалога."""
    conversation = get_object_or_404(Conversation, pk=pk, participants=request.user)
    last_id = int(request.GET.get('last_id', 0))

    if last_id:
        msgs = conversation.messages.filter(pk__gt=last_id).select_related('author').order_by('created_at')
    else:
        msgs = conversation.messages.select_related('author').order_by('-created_at')[:30]
        msgs = list(reversed(msgs))

    # mark read
    for m in msgs:
        if m.author != request.user:
            m.read_by.add(request.user)

    other = conversation.get_other_participant(request.user) if conversation.conversation_type == 'private' else None
    data = {
        'conversation': {
            'id': conversation.pk,
            'title': conversation.title or (other.get_full_name() if other else 'Чат'),
            'type': conversation.conversation_type,
        },
        'messages': [{
            'id': m.pk,
            'text': m.text,
            'author_name': m.author.get_full_name() or m.author.username,
            'is_me': m.author == request.user,
            'time': m.created_at.strftime('%H:%M'),
        } for m in msgs],
    }
    return JsonResponse(data)


@login_required
def conversation_list(request):
    """Список всех диалогов пользователя"""
    conversations = Conversation.objects.filter(
        participants=request.user
    ).annotate(
        last_message_time=Max('messages__created_at')
    ).order_by('-last_message_time')
    
    # Подсчёт непрочитанных для каждого диалога
    conversations_with_unread = []
    for conv in conversations:
        unread = conv.messages.exclude(author=request.user).exclude(read_by=request.user).count()
        participants_preview = [_build_user_meta(p) for p in conv.participants.all()[:5]]
        conversations_with_unread.append({
            'conversation': conv,
            'unread_count': unread,
            'last_message': conv.last_message,
            'other_participant': conv.get_other_participant(request.user) if conv.conversation_type == 'private' else None,
            'participants_preview': participants_preview,
        })
    
    profile = getattr(request.user, 'profile', None)
    role = getattr(profile, 'role', None)
    # Клиенты не могут создавать группы и чаты
    is_client = role == 'client'
    can_create_group = request.user.is_authenticated and not is_client
    
    group_candidates_qs = User.objects.filter(
        is_active=True,
        profile__role__in=['analyst', 'executor', 'admin']
    ).exclude(pk=request.user.pk).order_by('first_name', 'last_name', 'username')[:150]
    # Клиенты видят только аналитиков
    if is_client:
        chat_candidates_qs = User.objects.filter(
            is_active=True,
            profile__role__in=['analyst', 'admin']
        ).exclude(pk=request.user.pk).order_by('first_name', 'last_name', 'username')[:100]
    else:
        chat_candidates_qs = User.objects.filter(
            is_active=True
        ).exclude(pk=request.user.pk).order_by('first_name', 'last_name', 'username')[:100]

    group_candidates = [_build_user_meta(u) for u in group_candidates_qs]
    chat_candidates = [_build_user_meta(u) for u in chat_candidates_qs]

    context = {
        'conversations': conversations_with_unread,
        'can_create_group': can_create_group,
        'is_client': is_client,
        'group_candidates': group_candidates,
        'chat_candidates': chat_candidates,
    }
    return render(request, 'chat/conversation_list.html', context)


@login_required
def conversation_detail(request, pk):
    """Просмотр диалога и отправка сообщений"""
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related('participants', 'messages__author', 'messages__read_by'),
        pk=pk,
        participants=request.user
    )
    
    # Отметить все сообщения как прочитанные
    unread_messages = conversation.messages.exclude(author=request.user).exclude(read_by=request.user)
    for msg in unread_messages:
        msg.read_by.add(request.user)
    
    # Получить сообщения с пагинацией
    messages_qs = conversation.messages.select_related('author').order_by('created_at')
    paginator = Paginator(messages_qs, 50)
    page = request.GET.get('page', 1)
    messages_page = paginator.get_page(page)
    
    # Определить собеседника для приватного чата
    other_participant = conversation.get_other_participant(request.user)
    participants = [_build_user_meta(p) for p in conversation.participants.all()]
    
    context = {
        'conversation': conversation,
        'chat_messages': messages_page,
        'other_participant': other_participant,
        'participants': participants,
    }
    return render(request, 'chat/conversation_detail.html', context)


@login_required
@require_POST
def send_message(request, pk):
    """Отправить сообщение в диалог"""
    conversation = get_object_or_404(Conversation, pk=pk, participants=request.user)
    
    text = request.POST.get('text', '').strip()
    attachment = request.FILES.get('attachment')
    
    if not text and not attachment:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Сообщение не может быть пустым'}, status=400)
        return redirect('chat:conversation', pk=pk)
    
    message = Message.objects.create(
        conversation=conversation,
        author=request.user,
        text=text,
        attachment=attachment
    )
    
    # Обновить время диалога
    conversation.save()  # Обновит updated_at
    
    # Создать уведомления для других участников
    for participant in conversation.participants.exclude(pk=request.user.pk):
        create_notification(
            recipient=participant,
            title='Новое сообщение',
            message='В чате есть новое сообщение',
            notification_type='message',
            sender=request.user,
            link=f'/chat/{conversation.pk}/'
        )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': {
                'id': message.pk,
                'text': message.text,
                'author': {
                    'id': message.author.pk,
                    'name': message.author.get_full_name() or message.author.username,
                    'avatar': message.author.profile.avatar.url if hasattr(message.author, 'profile') and message.author.profile.avatar else None,
                },
                'created_at': message.created_at.strftime('%H:%M'),
                'is_file': message.is_file,
                'is_image': message.is_image,
                'file_url': message.attachment.url if message.attachment else None,
                'file_name': message.file_name,
            }
        })
    
    return redirect('chat:conversation', pk=pk)


@login_required
@require_GET
def get_new_messages(request, pk):
    """API: получить новые сообщения (для polling)"""
    conversation = get_object_or_404(Conversation, pk=pk, participants=request.user)
    
    last_id = request.GET.get('last_id', 0)
    
    messages = conversation.messages.filter(pk__gt=last_id).select_related('author')
    
    # Отметить как прочитанные
    for msg in messages.exclude(author=request.user):
        msg.read_by.add(request.user)
    
    data = [{
        'id': msg.pk,
        'text': msg.text,
        'author': {
            'id': msg.author.pk,
            'name': msg.author.get_full_name() or msg.author.username,
            'avatar': msg.author.profile.avatar.url if hasattr(msg.author, 'profile') and msg.author.profile.avatar else None,
            'is_me': msg.author == request.user,
        },
        'created_at': msg.created_at.strftime('%H:%M'),
        'is_file': msg.is_file,
        'is_image': msg.is_image,
        'file_url': msg.attachment.url if msg.attachment else None,
        'file_name': msg.file_name,
    } for msg in messages]
    
    return JsonResponse({'messages': data})


@login_required
def start_request_chat(request, request_id):
    """Открыть или создать чат по заявке между клиентом и аналитиком"""
    sr = get_object_or_404(ServiceRequest, pk=request_id)

    # Проверим доступ: только клиент, аналитик, исполнитель или админ
    profile = getattr(request.user, 'profile', None)
    role = getattr(profile, 'role', None)
    is_participant = (
        request.user == sr.client
        or request.user == sr.analyst
        or request.user == sr.executor
        or role in ['analyst', 'admin']
    )
    if not is_participant:
        return redirect('chat:list')

    # Ищем существующий чат по этой заявке
    existing = Conversation.objects.filter(
        related_request=sr,
        conversation_type='request',
    ).first()

    if existing:
        # Добавляем текущего пользователя, если его нет
        if not existing.participants.filter(pk=request.user.pk).exists():
            existing.participants.add(request.user)
        return redirect('chat:conversation', pk=existing.pk)

    # Создаём новый чат по заявке
    conversation = Conversation.objects.create(
        title=f'Заявка {sr.number}: {sr.title[:60]}',
        conversation_type='request',
        related_request=sr,
    )
    conversation.participants.add(request.user)
    # Добавляем клиента и аналитика
    if sr.client and sr.client != request.user:
        conversation.participants.add(sr.client)
    if sr.analyst and sr.analyst != request.user:
        conversation.participants.add(sr.analyst)
    if sr.executor and sr.executor != request.user:
        conversation.participants.add(sr.executor)

    # Авто-сообщение
    Message.objects.create(
        conversation=conversation,
        author=request.user,
        text=f'Чат по заявке {sr.number} создан. Здесь можно обсудить детали.',
    )

    return redirect('chat:conversation', pk=conversation.pk)


@login_required
def start_conversation(request, user_id):
    """Начать личный диалог с пользователем"""
    # Клиенты не могут создавать чаты
    profile = getattr(request.user, 'profile', None)
    role = getattr(profile, 'role', None)
    if role == 'client':
        messages.error(request, 'Клиенты могут общаться только через заявки. Перейдите на страницу заявки для начала чата.')
        return redirect('chat:list')
    
    other_user = get_object_or_404(User, pk=user_id)
    
    if other_user == request.user:
        return redirect('chat:list')
    
    # Проверить существующий диалог
    existing = Conversation.objects.filter(
        conversation_type='private',
        participants=request.user
    ).filter(
        participants=other_user
    ).first()
    
    if existing:
        return redirect('chat:conversation', pk=existing.pk)
    
    # Создать новый диалог
    conversation = Conversation.objects.create(conversation_type='private')
    conversation.participants.add(request.user, other_user)
    
    return redirect('chat:conversation', pk=conversation.pk)


@login_required
@require_POST
def start_conversation_post(request):
    """Fallback: начать личный чат через обычную форму (без JS)."""
    # Клиенты не могут создавать чаты
    profile = getattr(request.user, 'profile', None)
    role = getattr(profile, 'role', None)
    if role == 'client':
        messages.error(request, 'Клиенты могут общаться только через заявки. Перейдите на страницу заявки для начала чата.')
        return redirect('chat:list')
    
    user_id = request.POST.get('user_id')
    if not user_id:
        messages.error(request, 'Выберите пользователя для начала чата')
        return redirect('chat:list')

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        messages.error(request, 'Некорректный пользователь')
        return redirect('chat:list')

    return start_conversation(request, user_id_int)


@login_required
@require_POST
def create_group_chat(request):
    """Создать групповой чат"""
    # Клиенты не могут создавать групповые чаты
    profile = getattr(request.user, 'profile', None)
    role = getattr(profile, 'role', None)
    if role == 'client':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Клиенты не могут создавать групповые чаты'}, status=403)
        messages.error(request, 'Клиенты не могут создавать групповые чаты')
        return redirect('chat:list')
    
    if not request.user.is_authenticated:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Требуется авторизация'}, status=403)
        messages.error(request, 'Требуется авторизация')
        return redirect('login')

    title = request.POST.get('title', '').strip()
    participant_ids = request.POST.getlist('participants')
    
    if not title:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Укажите название чата'}, status=400)
        messages.error(request, 'Укажите название группы')
        return redirect('chat:list')

    if not participant_ids:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Выберите хотя бы одного участника'}, status=400)
        messages.error(request, 'Выберите хотя бы одного участника группы')
        return redirect('chat:list')
    
    conversation = Conversation.objects.create(
        title=title,
        conversation_type='group'
    )
    
    # Добавить создателя и выбранных участников
    conversation.participants.add(request.user)
    participants = User.objects.filter(
        pk__in=participant_ids,
        is_active=True,
        profile__role__in=['analyst', 'executor', 'admin'],
    ).exclude(pk=request.user.pk)

    if not participants.exists():
        conversation.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Не удалось добавить выбранных участников'}, status=400)
        messages.error(request, 'Не удалось добавить выбранных участников')
        return redirect('chat:list')

    conversation.participants.add(*participants)

    Message.objects.create(
        conversation=conversation,
        author=request.user,
        text='Группа создана. Можно начинать обсуждение.',
    )

    messages.success(request, f'Группа «{title}» создана')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'conversation_id': conversation.pk
        })
    
    return redirect('chat:conversation', pk=conversation.pk)


@login_required
@require_POST
def delete_conversation(request, pk):
    """Удалить диалог/группу для участника."""
    conversation = get_object_or_404(Conversation, pk=pk, participants=request.user)
    title = conversation.title or f'чат #{conversation.pk}'
    conversation.delete()
    messages.success(request, f'Диалог «{title}» удалён')
    return redirect('chat:list')


@login_required
@require_POST
def add_reaction(request, message_id):
    """Добавить реакцию на сообщение"""
    message = get_object_or_404(Message, pk=message_id)
    
    # Проверить что пользователь участник диалога
    if not message.conversation.participants.filter(pk=request.user.pk).exists():
        return JsonResponse({'error': 'Доступ запрещён'}, status=403)
    
    emoji = request.POST.get('emoji')
    if not emoji:
        return JsonResponse({'error': 'Укажите реакцию'}, status=400)
    
    # Удалить существующую такую же реакцию или создать новую
    existing = MessageReaction.objects.filter(
        message=message, user=request.user, emoji=emoji
    ).first()
    
    if existing:
        existing.delete()
        action = 'removed'
    else:
        MessageReaction.objects.create(
            message=message, user=request.user, emoji=emoji
        )
        action = 'added'
    
    return JsonResponse({
        'success': True,
        'action': action,
        'emoji': emoji
    })


@login_required
@require_POST
def delete_message(request, message_id):
    """Удалить сообщение"""
    message = get_object_or_404(Message, pk=message_id, author=request.user)
    
    message.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('chat:conversation', pk=message.conversation.pk)


@login_required
def search_users(request):
    """API: поиск пользователей для начала диалога"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'users': []})
    
    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query)
    ).exclude(pk=request.user.pk)[:10]
    
    data = [{
        'id': u.pk,
        'username': u.username,
        'name': u.get_full_name() or u.username,
        'avatar': u.profile.avatar.url if hasattr(u, 'profile') and u.profile.avatar else None,
        'role': u.profile.get_role_display() if hasattr(u, 'profile') else 'Пользователь',
        'group': 'Клиент' if (hasattr(u, 'profile') and u.profile.role == 'client') else 'Сотрудник',
    } for u in users]
    
    return JsonResponse({'users': data})
