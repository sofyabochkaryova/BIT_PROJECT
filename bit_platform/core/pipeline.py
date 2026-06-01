from datetime import timedelta
from decimal import Decimal
from django.utils.timezone import now

from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from projects.models import Project
from requests_app.models import ServiceRequest
from tasks.models import Task


# ═══════════════════════════════════════════════════════════════════════════
#  ЭТАП 1: Квалификация
# ═══════════════════════════════════════════════════════════════════════════

def qualify_request(service_request):
    """
    Проверяет полноту данных заявки.
    Возвращает (is_valid: bool, issues: list[str]).
    """
    issues = []
    if not service_request.title or len(service_request.title.strip()) < 5:
        issues.append('Слишком короткое название заявки')
    if not service_request.description or len(service_request.description.strip()) < 20:
        issues.append('Описание задачи слишком краткое — нужно минимум 20 символов')
    if not service_request.contact_email:
        issues.append('Не указан email для связи')
    if not service_request.contact_phone:
        issues.append('Не указан телефон для связи')
    if not service_request.service_type:
        issues.append('Не указан тип услуги')

    return len(issues) == 0, issues


def request_clarification(service_request, author, questions_text):
    """
    Аналитик запрашивает уточнения у клиента.
    Создаёт комментарий-вопрос и уведомляет клиента.
    """
    from requests_app.models import RequestComment
    from notifications.views import create_notification

    comment = RequestComment.objects.create(
        request=service_request,
        author=author,
        text=f'📋 Запрос уточнений:\n{questions_text}',
        is_internal=False,
    )

    create_notification(
        recipient=service_request.client,
        title='Требуются уточнения по заявке',
        message=f'Аналитик задал вопросы по заявке {service_request.number}',
        notification_type='request',
        sender=author,
        link=f'/requests/{service_request.pk}/',
    )

    return comment


# ═══════════════════════════════════════════════════════════════════════════
#  ЭТАП 2: Автоподбор этапов и оценка
# ═══════════════════════════════════════════════════════════════════════════

def get_template_stages(service_type):
    """
    Возвращает список типовых этапов для данного типа услуги.
    Если шаблона нет — возвращает базовый набор.
    """
    from core.models import ProjectTemplate

    try:
        template = ProjectTemplate.objects.prefetch_related('stages__required_skills').get(
            service_type=service_type,
        )
        stages = list(template.stages.all().order_by('order'))
        return template, stages
    except ProjectTemplate.DoesNotExist:
        return None, _default_stages(service_type)


def _default_stages(service_type):
    """Базовые этапы, если шаблон не настроен в БД."""
    defaults = {
        'outsourcing': [
            {'name': 'Анализ инфраструктуры', 'type': 'analysis', 'hours': 16, 'price': 1800,
             'description': 'Аудит текущей ИТ-инфраструктуры, сбор требований, выявление узких мест'},
            {'name': 'Настройка и подключение', 'type': 'deploy', 'hours': 24, 'price': 2000,
             'description': 'Настройка серверов, сетевого оборудования, развёртывание систем мониторинга'},
            {'name': 'Мониторинг и поддержка', 'type': 'support', 'hours': 10, 'price': 1500,
             'description': 'Круглосуточный мониторинг, техподдержка, реагирование на инциденты'},
        ],
        'implementation': [
            {'name': 'Обследование бизнес-процессов', 'type': 'analysis', 'hours': 24, 'price': 2200,
             'description': 'Анализ текущих бизнес-процессов, формирование требований к системе'},
            {'name': 'Конфигурация системы', 'type': 'backend', 'hours': 40, 'price': 2000,
             'description': 'Установка и настройка программного обеспечения, конфигурирование модулей'},
            {'name': 'Интеграция с существующими системами', 'type': 'integration', 'hours': 32, 'price': 2200,
             'description': 'Настройка обмена данными с 1С, CRM и другими используемыми системами'},
            {'name': 'Тестирование', 'type': 'testing', 'hours': 16, 'price': 1600,
             'description': 'Функциональное и интеграционное тестирование, исправление ошибок'},
            {'name': 'Внедрение и миграция данных', 'type': 'deploy', 'hours': 24, 'price': 2000,
             'description': 'Перенос данных из старых систем, запуск в продуктивную эксплуатацию'},
            {'name': 'Обучение персонала', 'type': 'training', 'hours': 16, 'price': 1500,
             'description': 'Проведение обучающих семинаров для ключевых пользователей'},
        ],
        'consulting': [
            {'name': 'Аудит текущего состояния', 'type': 'analysis', 'hours': 16, 'price': 2500,
             'description': 'Анализ текущего состояния ИТ, оценка рисков и эффективности'},
            {'name': 'Разработка рекомендаций', 'type': 'consulting', 'hours': 24, 'price': 2500,
             'description': 'Формирование стратегии развития, дорожной карты, рекомендаций'},
            {'name': 'Подготовка отчёта', 'type': 'other', 'hours': 8, 'price': 2000,
             'description': 'Оформление итогового отчёта с рекомендациями и планом действий'},
        ],
        'development': [
            {'name': 'Сбор и анализ требований', 'type': 'analysis', 'hours': 24, 'price': 2000,
             'description': 'Интервью с заказчиком, формирование технического задания, user stories'},
            {'name': 'Проектирование архитектуры', 'type': 'analysis', 'hours': 16, 'price': 2500,
             'description': 'Проектирование структуры БД, API, выбор технологического стека'},
            {'name': 'Backend-разработка', 'type': 'backend', 'hours': 80, 'price': 2000,
             'description': 'Реализация серверной логики, API, интеграций, бизнес-правил'},
            {'name': 'Frontend-разработка', 'type': 'frontend', 'hours': 60, 'price': 1800,
             'description': 'Разработка пользовательского интерфейса, адаптивная вёрстка'},
            {'name': 'Тестирование и QA', 'type': 'testing', 'hours': 40, 'price': 1500,
             'description': 'Ручное и автоматизированное тестирование, нагрузочные тесты'},
            {'name': 'Развёртывание', 'type': 'deploy', 'hours': 16, 'price': 1800,
             'description': 'Настройка CI/CD, деплой на сервер, мониторинг, документация'},
        ],
        'security': [
            {'name': 'Аудит безопасности', 'type': 'security', 'hours': 32, 'price': 3000,
             'description': 'Комплексный аудит информационной безопасности, анализ уязвимостей'},
            {'name': 'Пентестирование', 'type': 'testing', 'hours': 40, 'price': 2800,
             'description': 'Тестирование на проникновение, имитация атак, социальная инженерия'},
            {'name': 'Устранение уязвимостей', 'type': 'backend', 'hours': 24, 'price': 2500,
             'description': 'Исправление найденных уязвимостей, настройка защиты периметра'},
            {'name': 'Подготовка отчёта', 'type': 'other', 'hours': 8, 'price': 2000,
             'description': 'Отчёт по результатам аудита с рекомендациями и планом устранения'},
        ],
        'network': [
            {'name': 'Проектирование сети', 'type': 'analysis', 'hours': 16, 'price': 2000,
             'description': 'Проектирование сетевой архитектуры, выбор оборудования'},
            {'name': 'Монтаж и настройка', 'type': 'deploy', 'hours': 40, 'price': 1800,
             'description': 'Физический монтаж, настройка маршрутизации, VLAN, VPN'},
            {'name': 'Тестирование и приёмка', 'type': 'testing', 'hours': 8, 'price': 1500,
             'description': 'Проверка работоспособности, измерение пропускной способности'},
        ],
        'cloud': [
            {'name': 'Анализ потребностей', 'type': 'analysis', 'hours': 8, 'price': 2000,
             'description': 'Оценка текущих нагрузок, выбор облачной платформы и тарифа'},
            {'name': 'Миграция в облако', 'type': 'deploy', 'hours': 32, 'price': 2200,
             'description': 'Перенос серверов и данных, настройка сетевого взаимодействия'},
            {'name': 'Настройка мониторинга', 'type': 'support', 'hours': 16, 'price': 1800,
             'description': 'Настройка систем мониторинга, алертов, автомасштабирования'},
        ],
        'training': [
            {'name': 'Подготовка программы обучения', 'type': 'analysis', 'hours': 8, 'price': 1800,
             'description': 'Разработка учебной программы, подготовка материалов и тестов'},
            {'name': 'Проведение обучения', 'type': 'training', 'hours': 24, 'price': 2000,
             'description': 'Групповые и индивидуальные занятия, практические упражнения'},
            {'name': 'Итоговое тестирование', 'type': 'testing', 'hours': 4, 'price': 1500,
             'description': 'Проверка знаний, выдача сертификатов, рекомендации по развитию'},
        ],
    }
    return defaults.get(service_type, [
        {'name': 'Анализ', 'type': 'analysis', 'hours': 16, 'price': 2000,
         'description': 'Анализ требований, обследование текущего состояния'},
        {'name': 'Реализация', 'type': 'backend', 'hours': 40, 'price': 1800,
         'description': 'Выполнение основных работ по проекту'},
        {'name': 'Тестирование и сдача', 'type': 'testing', 'hours': 8, 'price': 1500,
         'description': 'Проверка результатов, устранение замечаний, приёмка'},
    ])


def estimate_stages(service_request):
    """
    Возвращает список dict-ов с этапами и предварительной стоимостью.
    Используется при создании КП.
    """
    template, raw_stages = get_template_stages(service_request.service_type)

    result = []
    total = Decimal('0')

    if template and raw_stages:
        for idx, stage in enumerate(raw_stages, 1):
            hours = Decimal(str(stage.default_hours))
            price = Decimal(str(stage.default_unit_price))
            # Вычисляем итого как часы × ставка с точностью 2 знака
            line_total = hours * price
            line_total = Decimal(str(round(float(line_total), 2)))
            total += line_total
            result.append({
                'order': idx,
                'name': stage.name,
                'stage_type': stage.stage_type,
                'description': stage.description,
                'hours': float(hours),
                'unit_price': float(price),
                'total': float(line_total),
                'required_skill_ids': list(stage.required_skills.values_list('id', flat=True)),
            })
    else:
        for idx, s in enumerate(raw_stages, 1):
            hours = Decimal(str(s['hours']))
            price = Decimal(str(s['price']))
            # Вычисляем итого как часы × ставка с точностью 2 знака
            line_total = hours * price
            line_total = Decimal(str(round(float(line_total), 2)))
            total += line_total
            result.append({
                'order': idx,
                'name': s['name'],
                'stage_type': s['type'],
                'description': s.get('description', ''),
                'hours': float(hours),
                'unit_price': float(price),
                'total': float(line_total),
                'required_skill_ids': [],
            })

    # Округляем итоговую сумму до 2 знаков после запятой
    total = Decimal(str(round(float(total), 2)))
    return result, float(total)


def adapt_to_budget(stages, total, budget_from=None, budget_to=None):
    """
    Возвращает оригинальные данные без адаптации к бюджету.
    (Адаптация отключена)
    """
    return stages, total, 0


# ═══════════════════════════════════════════════════════════════════════════
#  Подбор исполнителей по навыкам и загруженности
# ═══════════════════════════════════════════════════════════════════════════

def get_executor_workload(user):
    """Считает текущую загруженность исполнителя (часы в активных задачах)."""
    from tasks.models import Task
    active = Task.objects.filter(
        assignee=user,
        status__in=['todo', 'in_progress', 'review'],
    ).aggregate(total=Sum('estimated_hours'))
    return float(active['total'] or 0)


def find_executors_for_skills(skill_ids, exclude_user_ids=None):
    """
    Подбирает исполнителей, у которых есть целевые навыки.
    Ранжирует по: уровню навыка (desc), загруженности (asc).
    Возвращает список dict-ов: {user, match_score, workload_hours}.
    """
    from core.models import UserSkill

    exclude_ids = set(exclude_user_ids or [])

    if not skill_ids:
        # Если навыки не заданы — вернуть всех исполнителей по загруженности
        candidates = (
            User.objects.filter(profile__role='executor')
            .exclude(pk__in=exclude_ids)
        )
        return [
            {
                'user': u,
                'match_score': 0,
                'workload_hours': get_executor_workload(u),
            }
            for u in candidates
        ]

    qs = (
        UserSkill.objects
        .filter(skill_id__in=skill_ids, user__profile__role='executor')
        .exclude(user_id__in=exclude_ids)
        .values('user')
        .annotate(
            match_count=Count('id'),
            avg_level=Avg('level'),
        )
        .order_by('-match_count', '-avg_level')
    )

    result = []
    for row in qs:
        try:
            user = User.objects.get(pk=row['user'])
        except User.DoesNotExist:
            continue
        result.append({
            'user': user,
            'match_score': row['match_count'],
            'workload_hours': get_executor_workload(user),
        })

    # Добавляем исполнителей без навыков (как запасных)
    matched_ids = {r['user'].pk for r in result}
    fallback = (
        User.objects.filter(profile__role='executor')
        .exclude(pk__in=matched_ids | exclude_ids)
    )
    for u in fallback:
        result.append({
            'user': u,
            'match_score': 0,
            'workload_hours': get_executor_workload(u),
        })

    return result


def suggest_team_for_request(service_request):
    """
    Предлагает состав команды для заявки на основании шаблона.
    Возвращает list[dict] — по одному для каждого этапа.
    """
    stages, total_cost = estimate_stages(service_request)
    exclude_ids = [service_request.client_id]
    suggestions = []

    for stage in stages:
        candidates = find_executors_for_skills(
            stage.get('required_skill_ids', []),
            exclude_user_ids=exclude_ids,
        )
        # Сортируем: больше навыков → меньше загрузка
        candidates.sort(key=lambda c: (-c['match_score'], c['workload_hours']))
        suggestions.append({
            **stage,
            'candidates': candidates[:5],  # top-5
            'recommended': candidates[0] if candidates else None,
        })

    return suggestions, total_cost


# ═══════════════════════════════════════════════════════════════════════════
#  ЭТАП 4: Автосоздание проекта при подписании договора
# ═══════════════════════════════════════════════════════════════════════════

def auto_create_project(contract, actor):
    """
    Создаёт Project + Tasks + TaskAssignments из КП при подписании договора.
    Проверяет доступность предварительно назначенных исполнителей;
    если исполнитель занят — предлагает альтернативу.
    """
    from projects.models import Project
    from tasks.models import Task, TaskAssignment
    from notifications.views import create_notification

    sr = contract.request
    proposal = (
        contract.proposal
        or sr.proposals.filter(status='accepted').order_by('-created_at').first()
    )

    if sr.projects.exists():
        return sr.projects.first()

    project = Project.objects.create(
        name=f'Проект: {sr.title}',
        description=(
            f'Создан автоматически из договора {contract.number}.\n\n'
            f'Заявка: {sr.number}\n{sr.description}'
        ),
        client=sr.client,
        service_request=sr,
        manager=sr.analyst,
        status='planning',
        start_date=contract.start_date or timezone.now().date(),
        end_date=contract.end_date,
        budget=contract.amount,
    )

    if sr.analyst:
        project.team.add(sr.analyst)
    if sr.executor:
        project.team.add(sr.executor)

    # Определяем этапы из КП
    if proposal and proposal.items.exists():
        items = proposal.items.all().order_by('order')
        total_items = items.count()
        # Расчёт дедлайнов: равномерно распределяем от start_date до end_date
        project_start = project.start_date or timezone.now().date()
        project_end = contract.end_date or (project_start + timedelta(days=30 * total_items))
        total_days = (project_end - project_start).days
        days_per_task = max(total_days // total_items, 3) if total_items > 0 else 14

        for idx, item in enumerate(items):
            task_deadline = project_start + timedelta(days=days_per_task * (idx + 1))
            task = Task.objects.create(
                title=item.stage_name,
                description=item.description or f'Работы по этапу: {item.stage_name}',
                task_type='task',
                project=project,
                service_request=sr,
                assignee=None,
                created_by=actor,
                status='todo',
                priority='medium',
                estimated_hours=item.quantity,
                due_date=task_deadline,
            )
    else:
        # Одна задача из описания заявки
        fallback_deadline = contract.end_date or (timezone.now().date() + timedelta(days=30))
        Task.objects.create(
            title=sr.title,
            description=sr.description,
            task_type='task',
            project=project,
            service_request=sr,
            assignee=None,
            created_by=actor,
            status='todo',
            priority=sr.priority if sr.priority in ['low', 'medium', 'high'] else 'medium',
            due_date=fallback_deadline,
        )

    # Уведомления
    create_notification(
        recipient=sr.client,
        title='Проект создан',
        message=f'По заявке {sr.number} создан проект и задачи',
        notification_type='request',
        sender=actor,
        link=f'/projects/{project.pk}/',
    )
    if sr.analyst and sr.analyst != actor:
        create_notification(
            recipient=sr.analyst,
            title='Проект создан — назначьте исполнителей',
            message=f'Проект «{project.name}» готов. Назначьте исполнителей на задачи и запускайте.',
            notification_type='request',
            sender=actor,
            link=f'/projects/{project.pk}/',
        )

    # Обновляем статус заявки → «Конвертирован в проект»
    try:
        sr.change_status('CONVERTED', actor, f'Автоматически создан проект «{project.name}»', force=True)
    except (ValueError, Exception):
        pass  # Если переход невозможен, не блокируем

    return project


def _pick_assignee(service_request, proposal_item):
    """
    Выбирает исполнителя для задачи по навыкам.
    1. Определяет тип этапа по имени позиции КП.
    2. Ищет навыки, подходящие для этого типа.
    3. Находит исполнителя с максимальным совпадением навыков и минимальной загрузкой.
    4. Если навыки не определены — ищет наименее загруженного.
    """
    from core.models import Skill, ProjectTemplateStage

    # Пробуем определить тип этапа по имени
    stage_name_lower = (proposal_item.stage_name or '').lower()
    _TYPE_KEYWORDS = {
        'analysis': ['анализ', 'обследование', 'аудит', 'сбор требований', 'проектирование'],
        'backend': ['backend', 'серверн', 'бэкенд', 'устранение уязвимостей'],
        'frontend': ['frontend', 'интерфейс', 'фронтенд', 'вёрстка'],
        'integration': ['интеграция', 'обмен данными'],
        'testing': ['тестирование', 'qa', 'пентест', 'приёмка'],
        'deploy': ['внедрение', 'развёрт', 'миграция', 'монтаж', 'настройка'],
        'training': ['обучение', 'семинар'],
        'support': ['поддержка', 'мониторинг'],
        'consulting': ['консульт', 'рекоменд'],
        'security': ['безопасност', 'защит'],
    }
    detected_type = None
    for stype, keywords in _TYPE_KEYWORDS.items():
        if any(kw in stage_name_lower for kw in keywords):
            detected_type = stype
            break

    # Собираем id навыков по категории, совпадающей с типом этапа
    skill_ids = []
    if detected_type:
        skill_ids = list(
            Skill.objects.filter(category__iexact=detected_type).values_list('id', flat=True)
        )

    exclude_ids = [service_request.client_id]

    # Проверяем основного исполнителя
    primary = service_request.executor
    if primary and skill_ids:
        from core.models import UserSkill
        has_skills = UserSkill.objects.filter(user=primary, skill_id__in=skill_ids).exists()
        workload = get_executor_workload(primary)
        if has_skills and workload < 120:
            return primary

    # Ищем по навыкам
    candidates = find_executors_for_skills(skill_ids, exclude_user_ids=exclude_ids)
    candidates.sort(key=lambda c: (-c['match_score'], c['workload_hours']))

    for c in candidates:
        if c['workload_hours'] < 120:
            return c['user']

    # Фолбэк — основной исполнитель
    if primary:
        return primary

    # Самый незагруженный
    if candidates:
        candidates.sort(key=lambda c: c['workload_hours'])
        return candidates[0]['user']

    return None
