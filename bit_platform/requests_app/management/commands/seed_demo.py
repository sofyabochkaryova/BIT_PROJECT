"""
Управляющая команда для заполнения БД демо-данными.
Запуск: python manage.py seed_demo
       python manage.py seed_demo --reset   (очистить и пересоздать)
"""
import random
from datetime import timedelta, date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone

from accounts.models import UserProfile
from clients.models import ClientCompany
from requests_app.models import ServiceRequest, RequestComment, RequestStatusHistory
from proposals.models import CommercialProposal, ProposalItem
from contracts.models import Contract
from projects.models import Project
from tasks.models import Task, TaskAssignment
from documents.models import BusinessDocument
from chat.models import Conversation, Message


class Command(BaseCommand):
    help = 'Заполняет базу данных демо-данными для демонстрации'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Удалить старые демо-данные перед созданием')

    def handle(self, *args, **options):
        now = timezone.now()

        if options['reset']:
            self.stdout.write('Удаление старых демо-данных...')
            demo_usernames = ['ivanov_ceo', 'petrova_dir', 'smirnov_cto', 'kozlova_pm']
            demo_users = User.objects.filter(username__in=demo_usernames)
            # Удаляем по порядку зависимостей
            Message.objects.filter(conversation__participants__in=demo_users).delete()
            Conversation.objects.filter(participants__in=demo_users).delete()
            TaskAssignment.objects.filter(task__service_request__client__in=demo_users).delete()
            Task.objects.filter(service_request__client__in=demo_users).delete()
            BusinessDocument.objects.filter(request__client__in=demo_users).delete()
            Contract.objects.filter(request__client__in=demo_users).delete()
            ProposalItem.objects.filter(proposal__request__client__in=demo_users).delete()
            CommercialProposal.objects.filter(request__client__in=demo_users).delete()
            RequestComment.objects.filter(request__client__in=demo_users).delete()
            RequestStatusHistory.objects.filter(request__client__in=demo_users).delete()
            Project.objects.filter(service_request__client__in=demo_users).delete()
            ServiceRequest.objects.filter(client__in=demo_users).delete()
            ClientCompany.objects.filter(owner__in=demo_users).delete()
            # Удалим групповые чаты
            Conversation.objects.filter(conversation_type='group', title='Команда разработки').delete()
            self.stdout.write('  Старые данные удалены.')

        self.stdout.write('Создание демо-данных...')

        # ─── 1. Клиентские пользователи ───
        clients_data = [
            {'username': 'ivanov_ceo', 'first_name': 'Иван', 'last_name': 'Иванов',
             'email': 'ivanov@techprom.ru', 'password': 'demo12345'},
            {'username': 'petrova_dir', 'first_name': 'Анна', 'last_name': 'Петрова',
             'email': 'petrova@logistica.ru', 'password': 'demo12345'},
            {'username': 'smirnov_cto', 'first_name': 'Сергей', 'last_name': 'Смирнов',
             'email': 'smirnov@financeplus.ru', 'password': 'demo12345'},
            {'username': 'kozlova_pm', 'first_name': 'Екатерина', 'last_name': 'Козлова',
             'email': 'kozlova@medline.ru', 'password': 'demo12345'},
        ]

        client_users = []
        for cd in clients_data:
            user, created = User.objects.get_or_create(
                username=cd['username'],
                defaults={
                    'first_name': cd['first_name'],
                    'last_name': cd['last_name'],
                    'email': cd['email'],
                }
            )
            if created:
                user.set_password(cd['password'])
                user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = 'client'
            profile.phone = f'+7 (9{random.randint(10,99)}) {random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10,99)}'
            profile.save()
            client_users.append(user)

        self.stdout.write(f'  Клиенты: {len(client_users)} пользователей')

        # Получаем аналитика и исполнителей
        analyst = User.objects.filter(profile__role='analyst').first()
        executors = list(User.objects.filter(profile__role='executor'))

        if not analyst:
            self.stderr.write('Нет аналитика! Создайте пользователя с ролью analyst.')
            return
        if not executors:
            self.stderr.write('Нет исполнителей!')
            return

        # ─── 2. Компании клиентов ───
        companies_data = [
            {
                'owner': client_users[0],
                'short_name': 'ООО «ТехноПром»',
                'full_name': 'Общество с ограниченной ответственностью «ТехноПром»',
                'legal_form': 'ooo',
                'inn': '7701234567',
                'kpp': '770101001',
                'ogrn': '1027700001234',
                'legal_address': '127015, г. Москва, ул. Бутырская, д. 76, стр. 1, офис 402',
                'actual_address': '127015, г. Москва, ул. Бутырская, д. 76, стр. 1, офис 402',
                'bank_name': 'ПАО Сбербанк',
                'bik': '044525225',
                'corr_account': '30101810400000000225',
                'settlement_account': '40702810538000012345',
                'director_name': 'Иванов Иван Сергеевич',
                'phone': '+7 (495) 123-45-67',
                'email': 'info@technoprom.ru',
                'website': 'https://technoprom.ru',
            },
            {
                'owner': client_users[1],
                'short_name': 'ООО «ЛогистикаПро»',
                'full_name': 'Общество с ограниченной ответственностью «ЛогистикаПро»',
                'legal_form': 'ooo',
                'inn': '7802345678',
                'kpp': '780201001',
                'ogrn': '1087800054321',
                'legal_address': '190000, г. Санкт-Петербург, Невский пр-т, д. 28, лит. А',
                'actual_address': '190000, г. Санкт-Петербург, Невский пр-т, д. 28, лит. А',
                'bank_name': 'АО «Альфа-Банк»',
                'bik': '044525593',
                'corr_account': '30101810200000000593',
                'settlement_account': '40702810001100023456',
                'director_name': 'Петрова Анна Владимировна',
                'phone': '+7 (812) 234-56-78',
                'email': 'info@logisticapro.ru',
            },
            {
                'owner': client_users[2],
                'short_name': 'АО «ФинансПлюс»',
                'full_name': 'Акционерное общество «ФинансПлюс»',
                'legal_form': 'ao',
                'inn': '5001234567',
                'kpp': '500101001',
                'ogrn': '1155000067890',
                'legal_address': '394000, г. Воронеж, ул. Плехановская, д. 53',
                'actual_address': '394000, г. Воронеж, ул. Плехановская, д. 53',
                'bank_name': 'ПАО «ВТБ»',
                'bik': '044525187',
                'corr_account': '30101810700000000187',
                'settlement_account': '40702810900060034567',
                'director_name': 'Смирнов Сергей Алексеевич',
                'phone': '+7 (473) 345-67-89',
                'email': 'contact@financeplus.ru',
            },
            {
                'owner': client_users[3],
                'short_name': 'ООО «МедЛайн»',
                'full_name': 'Общество с ограниченной ответственностью «МедЛайн»',
                'legal_form': 'ooo',
                'inn': '6301234567',
                'kpp': '630101001',
                'ogrn': '1196300012345',
                'legal_address': '443010, г. Самара, ул. Куйбышева, д. 90, офис 15',
                'actual_address': '443010, г. Самара, ул. Куйбышева, д. 90, офис 15',
                'bank_name': 'ПАО Сбербанк',
                'bik': '044525225',
                'corr_account': '30101810400000000225',
                'settlement_account': '40702810538000045678',
                'director_name': 'Козлова Екатерина Дмитриевна',
                'phone': '+7 (846) 456-78-90',
                'email': 'info@medline-samara.ru',
            },
        ]

        companies = []
        for cd in companies_data:
            comp, _ = ClientCompany.objects.get_or_create(
                owner=cd['owner'],
                short_name=cd['short_name'],
                defaults=cd,
            )
            companies.append(comp)

        self.stdout.write(f'  Компании: {len(companies)}')

        # ─── 3. Заявки (ServiceRequests) ───
        # SERVICE_CHOICES: outsourcing, implementation, consulting, development,
        #     security, network, cloud, training, other
        # STATUS_CHOICES: IN_ANALYSIS, ESTIMATION, PROPOSAL_DRAFT, PROPOSAL_SENT,
        #     CLIENT_REVIEW, NEGOTIATION, CLIENT_APPROVED, INTERNAL_APPROVAL,
        #     LEGAL_REVIEW, FINANCIAL_CHECK, CONTRACT_DRAFT, CONTRACT_SENT,
        #     CONTRACT_SIGNED, ADVANCE_PAYMENT, CONVERTED, IN_PROGRESS,
        #     COMPLETED, REJECTED, CANCELLED, ARCHIVED
        requests_data = [
            # ── Завершённые ──
            {
                'title': 'Разработка корпоративного портала',
                'service_type': 'development',
                'description': 'Необходимо разработать корпоративный портал для внутренней коммуникации сотрудников. '
                               'Функционал: новости компании, внутренний чат, система заявок на ИТ-поддержку, '
                               'каталог сотрудников, база знаний.',
                'client': client_users[0],
                'client_company': companies[0],
                'company_name': 'ООО «ТехноПром»',
                'contact_phone': '+7 (495) 123-45-67',
                'contact_email': 'ivanov@techprom.ru',
                'status': 'COMPLETED',
                'priority': 'high',
                'budget_from': Decimal('800000'),
                'budget_to': Decimal('1500000'),
                'deadline': now - timedelta(days=10),
                'days_ago': 90,
                'has_executor': True,
            },
            {
                'title': 'Настройка CRM-системы для отдела продаж',
                'service_type': 'consulting',
                'description': 'Требуется настройка и кастомизация CRM-системы Bitrix24 для отдела продаж. '
                               'Интеграция с 1С:Бухгалтерия, настройка воронки продаж, автоматизация email-рассылок, '
                               'подключение телефонии.',
                'client': client_users[1],
                'client_company': companies[1],
                'company_name': 'ООО «ЛогистикаПро»',
                'contact_phone': '+7 (812) 234-56-78',
                'contact_email': 'petrova@logistica.ru',
                'status': 'COMPLETED',
                'priority': 'medium',
                'budget_from': Decimal('300000'),
                'budget_to': Decimal('500000'),
                'deadline': now - timedelta(days=30),
                'days_ago': 120,
                'has_executor': True,
            },
            # ── Договор отправлен на подпись ──
            {
                'title': 'Миграция серверов в облачную инфраструктуру',
                'service_type': 'cloud',
                'description': 'Перенос текущей серверной инфраструктуры (12 серверов) в AWS/Yandex Cloud. '
                               'Настройка CI/CD, мониторинга, бэкапов. Обеспечение минимального даунтайма.',
                'client': client_users[2],
                'client_company': companies[2],
                'company_name': 'АО «ФинансПлюс»',
                'contact_phone': '+7 (473) 345-67-89',
                'contact_email': 'smirnov@financeplus.ru',
                'status': 'CONTRACT_SENT',
                'priority': 'high',
                'budget_from': Decimal('1200000'),
                'budget_to': Decimal('2000000'),
                'deadline': now + timedelta(days=45),
                'days_ago': 25,
                'has_executor': True,
            },
            # ── Подготовка КП ──
            {
                'title': 'Разработка мобильного приложения для записи пациентов',
                'service_type': 'development',
                'description': 'Разработка iOS и Android приложения для онлайн-записи пациентов. '
                               'Личный кабинет, история посещений, push-уведомления, интеграция с МИС, '
                               'онлайн-оплата.',
                'client': client_users[3],
                'client_company': companies[3],
                'company_name': 'ООО «МедЛайн»',
                'contact_phone': '+7 (846) 456-78-90',
                'contact_email': 'kozlova@medline-samara.ru',
                'status': 'PROPOSAL_DRAFT',
                'priority': 'high',
                'budget_from': Decimal('2000000'),
                'budget_to': Decimal('3500000'),
                'deadline': now + timedelta(days=90),
                'days_ago': 12,
                'has_executor': True,
            },
            # ── На анализе ──
            {
                'title': 'Автоматизация складского учёта',
                'service_type': 'implementation',
                'description': 'Внедрение системы автоматизации складского учёта. '
                               'Штрих-кодирование, интеграция со сканерами, учёт в реальном времени, '
                               'отчёты о движении товаров, интеграция с 1С.',
                'client': client_users[1],
                'client_company': companies[1],
                'company_name': 'ООО «ЛогистикаПро»',
                'contact_phone': '+7 (812) 234-56-78',
                'contact_email': 'petrova@logistica.ru',
                'status': 'IN_ANALYSIS',
                'priority': 'medium',
                'budget_from': Decimal('600000'),
                'budget_to': Decimal('1000000'),
                'deadline': now + timedelta(days=60),
                'days_ago': 5,
                'has_executor': False,
            },
            # ── Свежая — только на анализе ──
            {
                'title': 'Редизайн корпоративного сайта',
                'service_type': 'development',
                'description': 'Полный редизайн корпоративного сайта с адаптивной вёрсткой. '
                               'SEO-оптимизация, интеграция с Яндекс.Метрикой и Google Analytics, '
                               'CMS для самостоятельного управления контентом.',
                'client': client_users[0],
                'client_company': companies[0],
                'company_name': 'ООО «ТехноПром»',
                'contact_phone': '+7 (495) 123-45-67',
                'contact_email': 'ivanov@techprom.ru',
                'status': 'IN_ANALYSIS',
                'priority': 'low',
                'budget_from': Decimal('200000'),
                'budget_to': Decimal('400000'),
                'deadline': now + timedelta(days=120),
                'days_ago': 2,
                'has_executor': False,
            },
            # ── На оценке ──
            {
                'title': 'Разработка системы электронного документооборота',
                'service_type': 'development',
                'description': 'Создание внутренней системы ЭДО с ЭЦП, маршрутизацией документов, '
                               'контролем версий, интеграцией с 1С и СБиС. Поддержка согласований.',
                'client': client_users[2],
                'client_company': companies[2],
                'company_name': 'АО «ФинансПлюс»',
                'contact_phone': '+7 (473) 345-67-89',
                'contact_email': 'smirnov@financeplus.ru',
                'status': 'ESTIMATION',
                'priority': 'high',
                'budget_from': Decimal('1500000'),
                'budget_to': Decimal('2500000'),
                'deadline': now + timedelta(days=75),
                'days_ago': 8,
                'has_executor': True,
            },
            # ── КП отправлено ──
            {
                'title': 'Интеграция платёжного шлюза на сайт',
                'service_type': 'other',
                'description': 'Интеграция онлайн-оплаты через ЮKassa и СБП на существующий сайт. '
                               'Формирование чеков через ОФД, возвраты, рекуррентные платежи.',
                'client': client_users[3],
                'client_company': companies[3],
                'company_name': 'ООО «МедЛайн»',
                'contact_phone': '+7 (846) 456-78-90',
                'contact_email': 'kozlova@medline-samara.ru',
                'status': 'PROPOSAL_SENT',
                'priority': 'medium',
                'budget_from': Decimal('150000'),
                'budget_to': Decimal('300000'),
                'deadline': now + timedelta(days=30),
                'days_ago': 15,
                'has_executor': True,
            },
            # ── В работе — проект запущен ──
            {
                'title': 'Внедрение системы информационной безопасности',
                'service_type': 'security',
                'description': 'Аудит ИБ, настройка SIEM, DLP, антивирусной защиты. '
                               'Разработка политик безопасности, обучение сотрудников.',
                'client': client_users[0],
                'client_company': companies[0],
                'company_name': 'ООО «ТехноПром»',
                'contact_phone': '+7 (495) 123-45-67',
                'contact_email': 'ivanov@techprom.ru',
                'status': 'IN_PROGRESS',
                'priority': 'urgent',
                'budget_from': Decimal('900000'),
                'budget_to': Decimal('1500000'),
                'deadline': now + timedelta(days=20),
                'days_ago': 40,
                'has_executor': True,
            },
            # ── Архивная ──
            {
                'title': 'Техническая поддержка ИТ-инфраструктуры (2024)',
                'service_type': 'outsourcing',
                'description': 'Годовой контракт на техническую поддержку: серверы, сеть, рабочие станции. '
                               'SLA 4 часа. Удалённое и выездное обслуживание.',
                'client': client_users[2],
                'client_company': companies[2],
                'company_name': 'АО «ФинансПлюс»',
                'contact_phone': '+7 (473) 345-67-89',
                'contact_email': 'smirnov@financeplus.ru',
                'status': 'ARCHIVED',
                'priority': 'medium',
                'budget_from': Decimal('480000'),
                'budget_to': Decimal('480000'),
                'deadline': now - timedelta(days=60),
                'days_ago': 370,
                'has_executor': True,
            },
            # ── Сетевые решения — клиент рассматривает ──
            {
                'title': 'Модернизация сетевой инфраструктуры офиса',
                'service_type': 'network',
                'description': 'Проектирование и развёртывание новой СКС, настройка коммутаторов, '
                               'Wi-Fi 6, VLAN-ов, межсетевых экранов. Оптимизация маршрутизации.',
                'client': client_users[1],
                'client_company': companies[1],
                'company_name': 'ООО «ЛогистикаПро»',
                'contact_phone': '+7 (812) 234-56-78',
                'contact_email': 'petrova@logistica.ru',
                'status': 'CLIENT_REVIEW',
                'priority': 'medium',
                'budget_from': Decimal('350000'),
                'budget_to': Decimal('700000'),
                'deadline': now + timedelta(days=50),
                'days_ago': 18,
                'has_executor': True,
            },
            # ── Обучение — отклонена ──
            {
                'title': 'Обучение сотрудников работе с 1С:ERP',
                'service_type': 'training',
                'description': 'Корпоративное обучение (30 человек) работе с модулями 1С:ERP. '
                               'Программа на 5 дней: теория + практические кейсы.',
                'client': client_users[3],
                'client_company': companies[3],
                'company_name': 'ООО «МедЛайн»',
                'contact_phone': '+7 (846) 456-78-90',
                'contact_email': 'kozlova@medline-samara.ru',
                'status': 'REJECTED',
                'priority': 'low',
                'budget_from': Decimal('120000'),
                'budget_to': Decimal('200000'),
                'deadline': now + timedelta(days=30),
                'days_ago': 35,
                'has_executor': False,
            },
        ]

        service_requests = []
        for rd in requests_data:
            days_ago = rd.pop('days_ago')
            has_executor = rd.pop('has_executor')
            created = now - timedelta(days=days_ago)
            sr, sr_created = ServiceRequest.objects.get_or_create(
                title=rd['title'],
                defaults={
                    'service_type': rd['service_type'],
                    'description': rd['description'],
                    'client': rd['client'],
                    'client_company': rd['client_company'],
                    'company_name': rd['company_name'],
                    'contact_phone': rd['contact_phone'],
                    'contact_email': rd['contact_email'],
                    'status': rd['status'],
                    'priority': rd['priority'],
                    'analyst': analyst,
                    'executor': random.choice(executors) if has_executor else None,
                    'budget_from': rd['budget_from'],
                    'budget_to': rd['budget_to'],
                    'deadline': rd['deadline'],
                },
            )
            if sr_created:
                ServiceRequest.objects.filter(pk=sr.pk).update(created_at=created)
                sr.refresh_from_db()
            service_requests.append(sr)

        self.stdout.write(f'  Заявки: {len(service_requests)}')

        # ─── 4. История статусов ───
        status_sequences = {
            'COMPLETED': [
                'IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT', 'PROPOSAL_SENT',
                'CLIENT_APPROVED', 'CONTRACT_DRAFT', 'CONTRACT_SENT', 'CONTRACT_SIGNED',
                'CONVERTED', 'IN_PROGRESS', 'COMPLETED',
            ],
            'IN_PROGRESS': [
                'IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT', 'PROPOSAL_SENT',
                'CLIENT_APPROVED', 'CONTRACT_DRAFT', 'CONTRACT_SENT', 'CONTRACT_SIGNED',
                'CONVERTED', 'IN_PROGRESS',
            ],
            'CONTRACT_SENT': [
                'IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT', 'PROPOSAL_SENT',
                'CLIENT_APPROVED', 'CONTRACT_DRAFT', 'CONTRACT_SENT',
            ],
            'CONTRACT_SIGNED': [
                'IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT', 'PROPOSAL_SENT',
                'CLIENT_APPROVED', 'CONTRACT_DRAFT', 'CONTRACT_SENT', 'CONTRACT_SIGNED',
            ],
            'PROPOSAL_DRAFT': [
                'IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT',
            ],
            'PROPOSAL_SENT': [
                'IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT', 'PROPOSAL_SENT',
            ],
            'CLIENT_REVIEW': [
                'IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT', 'PROPOSAL_SENT', 'CLIENT_REVIEW',
            ],
            'ESTIMATION': [
                'IN_ANALYSIS', 'ESTIMATION',
            ],
            'IN_ANALYSIS': [
                'IN_ANALYSIS',
            ],
            'ARCHIVED': [
                'IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT', 'PROPOSAL_SENT',
                'CLIENT_APPROVED', 'CONTRACT_DRAFT', 'CONTRACT_SENT', 'CONTRACT_SIGNED',
                'CONVERTED', 'IN_PROGRESS', 'COMPLETED', 'ARCHIVED',
            ],
            'REJECTED': [
                'IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT', 'PROPOSAL_SENT', 'REJECTED',
            ],
        }

        status_labels = dict(ServiceRequest.STATUS_CHOICES)

        for sr in service_requests:
            if RequestStatusHistory.objects.filter(request=sr).exists():
                continue
            seq = status_sequences.get(sr.status, ['IN_ANALYSIS'])
            t = sr.created_at
            for i, st in enumerate(seq):
                h = RequestStatusHistory.objects.create(
                    request=sr,
                    old_status=seq[i - 1] if i > 0 else '',
                    new_status=st,
                    changed_by=analyst,
                    comment=f'Статус изменён на «{status_labels.get(st, st)}»',
                )
                RequestStatusHistory.objects.filter(pk=h.pk).update(changed_at=t)
                t += timedelta(days=random.randint(1, 5), hours=random.randint(1, 12))

        self.stdout.write('  История статусов создана')

        # ─── 5. Комментарии к заявкам ───
        comments_pool = [
            'Уточнил требования с заказчиком по телефону.',
            'Необходимо согласовать бюджет с руководством.',
            'Прикрепил ТЗ от клиента.',
            'Исполнитель приступил к оценке сроков.',
            'Клиент подтвердил приоритет задачи.',
            'Ожидаем дополнительные материалы от клиента.',
            'Провели встречу — зафиксировали основные пожелания.',
            'КП готово, отправляю на внутреннее согласование.',
            'Клиент просит ускорить сроки.',
            'Договор на подписании у юриста.',
            'Работы идут по графику.',
            'Еженедельный отчёт направлен клиенту.',
        ]

        for sr in service_requests:
            if RequestComment.objects.filter(request=sr).exists():
                continue
            num_comments = random.randint(1, 4)
            t = sr.created_at + timedelta(hours=random.randint(2, 24))
            for _ in range(num_comments):
                author = random.choice([analyst, sr.client] + ([sr.executor] if sr.executor else []))
                c = RequestComment.objects.create(
                    request=sr,
                    author=author,
                    text=random.choice(comments_pool),
                )
                RequestComment.objects.filter(pk=c.pk).update(created_at=t)
                t += timedelta(days=random.randint(1, 7))

        self.stdout.write('  Комментарии к заявкам созданы')

        # ─── 6. Коммерческие предложения ───
        kp_statuses = {
            'PROPOSAL_DRAFT', 'PROPOSAL_SENT', 'CLIENT_REVIEW', 'NEGOTIATION',
            'CLIENT_APPROVED', 'INTERNAL_APPROVAL', 'LEGAL_REVIEW', 'FINANCIAL_CHECK',
            'CONTRACT_DRAFT', 'CONTRACT_SENT', 'CONTRACT_SIGNED', 'ADVANCE_PAYMENT',
            'CONVERTED', 'IN_PROGRESS', 'COMPLETED', 'ARCHIVED',
        }

        proposals = []
        for sr in service_requests:
            if sr.status not in kp_statuses:
                continue
            if CommercialProposal.objects.filter(request=sr).exists():
                proposals.extend(list(CommercialProposal.objects.filter(request=sr)))
                continue

            kp_status_map = {
                'PROPOSAL_DRAFT': 'draft',
                'PROPOSAL_SENT': 'sent',
                'CLIENT_REVIEW': 'sent',
                'NEGOTIATION': 'sent',
                'CLIENT_APPROVED': 'accepted',
                'CONTRACT_DRAFT': 'accepted',
                'CONTRACT_SENT': 'accepted',
                'CONTRACT_SIGNED': 'accepted',
                'IN_PROGRESS': 'accepted',
                'COMPLETED': 'accepted',
                'ARCHIVED': 'accepted',
            }

            total = sr.budget_from + (sr.budget_to - sr.budget_from) * Decimal('0.7')

            kp = CommercialProposal.objects.create(
                request=sr,
                author=analyst,
                title=f'КП: {sr.title}',
                scope=f'Предлагаем выполнить работы по проекту «{sr.title}».\n\n'
                      f'В рамках проекта будут выполнены следующие этапы:\n'
                      f'1. Анализ требований и проектирование\n'
                      f'2. Разработка / настройка\n'
                      f'3. Тестирование и отладка\n'
                      f'4. Внедрение и обучение\n'
                      f'5. Гарантийная поддержка — 3 месяца',
                assumptions='Заказчик предоставляет доступ к текущей инфраструктуре и материалы по требованиям. '
                            'Сроки указаны в рабочих днях.',
                total_amount=total,
                duration_days=random.choice([30, 45, 60, 90]),
                status=kp_status_map.get(sr.status, 'draft'),
                valid_until=(now + timedelta(days=30)).date(),
            )

            # Позиции КП
            stages = [
                ('Анализ и проектирование', total * Decimal('0.15')),
                ('Разработка', total * Decimal('0.45')),
                ('Тестирование', total * Decimal('0.15')),
                ('Внедрение', total * Decimal('0.15')),
                ('Документирование и обучение', total * Decimal('0.10')),
            ]
            for idx, (name, price) in enumerate(stages, 1):
                ProposalItem.objects.create(
                    proposal=kp,
                    stage_name=name,
                    description=f'{name} в рамках проекта',
                    quantity=1,
                    unit='этап',
                    unit_price=price.quantize(Decimal('0.01')),
                    total_price=price.quantize(Decimal('0.01')),
                    order=idx,
                )

            proposals.append(kp)

        self.stdout.write(f'  Коммерческие предложения: {len(proposals)}')

        # ─── 7. Договоры ───
        contract_statuses_needed = {
            'CONTRACT_SENT', 'CONTRACT_SIGNED', 'ADVANCE_PAYMENT',
            'CONVERTED', 'IN_PROGRESS', 'COMPLETED', 'ARCHIVED',
        }
        contracts = []
        for sr in service_requests:
            if sr.status not in contract_statuses_needed:
                continue
            if Contract.objects.filter(request=sr).exists():
                contracts.extend(list(Contract.objects.filter(request=sr)))
                continue

            kp = CommercialProposal.objects.filter(request=sr).first()
            contract_status_map = {
                'CONTRACT_SENT': 'sent',
                'CONTRACT_SIGNED': 'signed',
                'ADVANCE_PAYMENT': 'signed',
                'CONVERTED': 'active',
                'IN_PROGRESS': 'active',
                'COMPLETED': 'closed',
                'ARCHIVED': 'closed',
            }

            c = Contract.objects.create(
                request=sr,
                proposal=kp,
                responsible=analyst,
                subject=f'Договор на выполнение работ: {sr.title}',
                amount=kp.total_amount if kp else sr.budget_from,
                start_date=date.today() - timedelta(days=random.randint(5, 30)),
                end_date=date.today() + timedelta(days=random.randint(30, 180)),
                payment_terms='Предоплата 30%, оплата по этапам. Окончательный расчёт в течение 5 рабочих дней после подписания акта.',
                status=contract_status_map.get(sr.status, 'draft'),
            )
            contracts.append(c)

        self.stdout.write(f'  Договоры: {len(contracts)}')

        # ─── 8. Проекты ───
        project_statuses_needed = {'CONVERTED', 'IN_PROGRESS', 'COMPLETED', 'ARCHIVED'}
        projects = []
        for sr in service_requests:
            if sr.status not in project_statuses_needed:
                continue
            if Project.objects.filter(service_request=sr).exists():
                projects.extend(list(Project.objects.filter(service_request=sr)))
                continue

            proj_status_map = {
                'CONVERTED': 'planning',
                'IN_PROGRESS': 'active',
                'COMPLETED': 'completed',
                'ARCHIVED': 'completed',
            }

            proj = Project.objects.create(
                name=sr.title,
                description=sr.description,
                client=sr.client,
                service_request=sr,
                manager=analyst,
                status=proj_status_map.get(sr.status, 'planning'),
                start_date=date.today() - timedelta(days=random.randint(10, 60)),
                end_date=date.today() + timedelta(days=random.randint(30, 120)),
                budget=sr.budget_to,
                progress=random.randint(30, 100) if sr.status == 'IN_PROGRESS' else 100,
            )
            team = random.sample(executors, min(4, len(executors)))
            proj.team.add(*team)
            if sr.executor and sr.executor not in team:
                proj.team.add(sr.executor)
            projects.append(proj)

        self.stdout.write(f'  Проекты: {len(projects)}')

        # ─── 9. Задачи ───
        task_templates = [
            ('Анализ требований', 'Провести детальный анализ требований заказчика', 'task', 'done', 16),
            ('Проектирование архитектуры', 'Разработать архитектуру решения', 'task', 'done', 24),
            ('Разработка backend', 'Реализация серверной части', 'feature', 'in_progress', 80),
            ('Разработка frontend', 'Реализация клиентской части', 'feature', 'in_progress', 60),
            ('Настройка CI/CD', 'Настроить pipeline для автоматической сборки и деплоя', 'improvement', 'todo', 8),
            ('Интеграция с внешними сервисами', 'API интеграции с сервисами заказчика', 'task', 'in_progress', 32),
            ('Unit-тестирование', 'Написать unit-тесты для критичных модулей', 'task', 'todo', 24),
            ('Нагрузочное тестирование', 'Провести нагрузочное тестирование', 'task', 'backlog', 16),
            ('Исправить баг авторизации', 'При вводе email с точкой возникает ошибка 500', 'bug', 'done', 4),
            ('Документация API', 'Подготовить Swagger-документацию для API', 'task', 'review', 12),
            ('Миграция данных', 'Перенос данных из старой системы', 'task', 'in_progress', 40),
            ('Обучение пользователей', 'Провести обучающие вебинары для сотрудников', 'task', 'backlog', 8),
        ]

        all_tasks = []
        for proj in projects:
            if Task.objects.filter(project=proj).exists():
                continue
            num_tasks = random.randint(5, len(task_templates))
            chosen = random.sample(task_templates, num_tasks)
            for title, desc, ttype, status, hours in chosen:
                assignee = random.choice(list(proj.team.all())) if proj.team.exists() else random.choice(executors)
                task = Task.objects.create(
                    title=title,
                    description=desc,
                    task_type=ttype,
                    project=proj,
                    service_request=proj.service_request,
                    assignee=assignee,
                    created_by=analyst,
                    status=status,
                    priority=random.choice(['low', 'medium', 'high', 'critical']),
                    estimated_hours=Decimal(str(hours)),
                    spent_hours=Decimal(str(random.randint(0, hours))) if status in ('done', 'in_progress', 'review') else Decimal('0'),
                    due_date=date.today() + timedelta(days=random.randint(5, 60)),
                )
                if status == 'done':
                    Task.objects.filter(pk=task.pk).update(
                        completed_at=now - timedelta(days=random.randint(1, 20))
                    )

                stage = random.choice(['analysis', 'backend', 'frontend', 'qa', 'deploy'])
                ta_status = {'backlog': 'todo', 'todo': 'todo', 'in_progress': 'in_progress',
                             'review': 'review', 'done': 'done'}.get(status, 'todo')
                TaskAssignment.objects.get_or_create(
                    task=task,
                    assignee=assignee,
                    stage=stage,
                    defaults={
                        'status': ta_status,
                        'description': f'Работа над задачей «{title}»',
                        'planned_start': date.today(),
                        'planned_end': date.today() + timedelta(days=random.randint(5, 30)),
                    }
                )
                all_tasks.append(task)

        self.stdout.write(f'  Задачи: {len(all_tasks)}')

        # ─── 10. Документы ───
        documents = []
        for c in contracts:
            if BusinessDocument.objects.filter(contract=c).exists():
                continue
            sr = c.request
            doc_inv = BusinessDocument.objects.create(
                request=sr,
                contract=c,
                doc_type='invoice',
                title=f'Счёт на оплату по договору {c.number}',
                amount=c.amount * Decimal('0.3'),
                description='Счёт на предоплату 30%',
                status='issued' if c.status in ('active', 'closed') else 'draft',
                issue_date=date.today() - timedelta(days=random.randint(5, 30)),
                due_date=date.today() + timedelta(days=10),
                created_by=analyst,
            )
            documents.append(doc_inv)

            if c.status == 'closed':
                doc_act = BusinessDocument.objects.create(
                    request=sr,
                    contract=c,
                    doc_type='act',
                    title=f'Акт выполненных работ по договору {c.number}',
                    amount=c.amount,
                    description='Акт сдачи-приёмки выполненных работ',
                    status='signed',
                    issue_date=date.today() - timedelta(days=random.randint(1, 10)),
                    created_by=analyst,
                )
                documents.append(doc_act)

        self.stdout.write(f'  Документы: {len(documents)}')

        # ─── 11. Чаты и сообщения ───
        conversations = []
        messages_created = 0

        for cu in client_users[:3]:
            existing = Conversation.objects.filter(
                conversation_type='private', participants=cu
            ).filter(participants=analyst).first()
            if existing:
                conversations.append(existing)
                continue

            conv = Conversation.objects.create(conversation_type='private')
            conv.participants.add(cu, analyst)
            conversations.append(conv)

            msgs = [
                (cu, 'Добрый день! Хотел уточнить статус нашей заявки.'),
                (analyst, 'Здравствуйте! Заявка принята в работу, аналитик назначен.'),
                (cu, 'Отлично, спасибо! Когда можно ожидать коммерческое предложение?'),
                (analyst, 'КП будет готово в течение 3-5 рабочих дней. Я пришлю вам уведомление.'),
                (cu, 'Хорошо, буду ждать. Если понадобятся дополнительные данные — пишите.'),
                (analyst, 'Обязательно. Также хотел уточнить — предпочитаете облачное или коробочное решение?'),
                (cu, 'Облачное будет удобнее для нас, у нас нет своей серверной.'),
                (analyst, 'Принято, учтём в КП. Хорошего дня!'),
            ]
            t = now - timedelta(days=random.randint(3, 15))
            for author, text in msgs:
                m = Message.objects.create(conversation=conv, author=author, text=text)
                Message.objects.filter(pk=m.pk).update(created_at=t)
                messages_created += 1
                t += timedelta(minutes=random.randint(5, 120))

        for sr in service_requests[:4]:
            existing = Conversation.objects.filter(
                conversation_type='request', related_request=sr
            ).first()
            if existing:
                conversations.append(existing)
                continue

            conv = Conversation.objects.create(
                title=f'Заявка: {sr.title[:50]}',
                conversation_type='request',
                related_request=sr,
            )
            conv.participants.add(sr.client, analyst)
            if sr.executor:
                conv.participants.add(sr.executor)
            conversations.append(conv)

            msgs = [
                (analyst, f'Чат по заявке «{sr.title[:40]}» создан.'),
                (sr.client, 'Спасибо, удобно обсуждать здесь.'),
                (analyst, 'Да, все участники проекта подключены к этому чату.'),
            ]
            if sr.executor:
                msgs.append((sr.executor, 'Добрый день! Приступаю к оценке.'))
                msgs.append((analyst, 'Отлично. Жду результатов к концу недели.'))

            t = now - timedelta(days=random.randint(2, 20))
            for author, text in msgs:
                m = Message.objects.create(conversation=conv, author=author, text=text)
                Message.objects.filter(pk=m.pk).update(created_at=t)
                messages_created += 1
                t += timedelta(minutes=random.randint(10, 300))

        existing_group = Conversation.objects.filter(conversation_type='group', title='Команда разработки').first()
        if not existing_group:
            group_chat = Conversation.objects.create(
                title='Команда разработки',
                conversation_type='group',
            )
            group_chat.participants.add(analyst, *executors[:6])
            conversations.append(group_chat)

            team_msgs = [
                (analyst, 'Всем привет! Создал общий чат команды для координации.'),
                (executors[0], 'Привет! Отличная идея.'),
                (executors[1], 'Здравствуйте! Я подключился.'),
                (analyst, 'На этой неделе приоритет — проект для ТехноПром. Задачи распределены в Kanban.'),
                (executors[2], 'Принял. Начну с бэкенда, API уже почти готово.'),
                (executors[0], 'Я займусь фронтом, есть вопрос по макетам — кидайте в чат.'),
                (analyst, 'Макеты обновил в Figma, ссылку скину отдельно.'),
                (executors[3] if len(executors) > 3 else executors[0],
                 'Тесты по первому модулю написаны, можно запускать ревью.'),
            ]
            t = now - timedelta(days=3)
            for author, text in team_msgs:
                m = Message.objects.create(conversation=group_chat, author=author, text=text)
                Message.objects.filter(pk=m.pk).update(created_at=t)
                messages_created += 1
                t += timedelta(minutes=random.randint(15, 180))

        self.stdout.write(f'  Чаты: {len(conversations)}, Сообщения: {messages_created}')

        # ─── 12. Обновляем профили клиентов ───
        client_positions = ['Генеральный директор', 'Директор по развитию', 'Технический директор', 'Руководитель проектов']
        for i, cu in enumerate(client_users):
            p = cu.profile
            p.company = companies[i].short_name
            p.position = client_positions[i]
            p.save()

        try:
            admin_user = User.objects.get(username='admin')
            admin_user.first_name = 'Администратор'
            admin_user.last_name = 'Системы'
            admin_user.save()
            p = admin_user.profile
            p.role = 'admin'
            p.company = 'ООО «БИТ»'
            p.position = 'Системный администратор'
            p.save()
        except User.DoesNotExist:
            pass

        self.stdout.write(self.style.SUCCESS('\n✅ Демо-данные успешно созданы!'))
        self.stdout.write(f'''
Итого:
  • Клиенты: {len(client_users)}
  • Компании: {len(companies)}
  • Заявки: {len(service_requests)}
  • КП: {len(proposals)}
  • Договоры: {len(contracts)}
  • Проекты: {len(projects)}
  • Задачи: {len(all_tasks)}
  • Документы: {len(documents)}
  • Чаты: {len(conversations)}
  • Сообщения: {messages_created}
''')
