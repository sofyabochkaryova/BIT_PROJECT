"""
Наполняет базу шаблонами проектов и навыками.

Использование:
    python manage.py seed_templates
"""

from django.core.management.base import BaseCommand

from core.models import ProjectTemplate, ProjectTemplateStage, Skill


SKILLS = [
    ('Python', 'Разработка'),
    ('Django', 'Разработка'),
    ('JavaScript', 'Разработка'),
    ('React', 'Разработка'),
    ('1С', 'Разработка'),
    ('SQL', 'Разработка'),
    ('DevOps', 'Инфраструктура'),
    ('Linux', 'Инфраструктура'),
    ('Сети (Cisco/MikroTik)', 'Инфраструктура'),
    ('Облачные платформы (AWS/Azure)', 'Инфраструктура'),
    ('Docker/Kubernetes', 'Инфраструктура'),
    ('Информационная безопасность', 'Безопасность'),
    ('Пентестирование', 'Безопасность'),
    ('Системный анализ', 'Аналитика'),
    ('Бизнес-анализ', 'Аналитика'),
    ('Управление проектами', 'Управление'),
    ('QA / Тестирование', 'Тестирование'),
    ('Техническое обучение', 'Обучение'),
    ('UI/UX дизайн', 'Дизайн'),
]

TEMPLATES = {
    'outsourcing': {
        'name': 'ИТ-аутсорсинг',
        'description': 'Типовой шаблон для передачи ИТ-функций на обслуживание',
        'duration': 90,
        'stages': [
            {'name': 'Анализ инфраструктуры',     'type': 'analysis',  'hours': 16, 'price': 3000, 'skills': ['Системный анализ', 'Linux']},
            {'name': 'Настройка и подключение',    'type': 'deploy',    'hours': 24, 'price': 3500, 'skills': ['DevOps', 'Linux']},
            {'name': 'Мониторинг и поддержка',     'type': 'support',   'hours': 40, 'price': 2500, 'skills': ['DevOps', 'Linux']},
        ],
    },
    'implementation': {
        'name': 'Внедрение ПО',
        'description': 'Полный цикл внедрения: обследование → конфигурация → интеграция → тестирование → запуск → обучение',
        'duration': 60,
        'stages': [
            {'name': 'Обследование бизнес-процессов',       'type': 'analysis',     'hours': 24, 'price': 4000, 'skills': ['Бизнес-анализ', 'Системный анализ']},
            {'name': 'Конфигурация системы',                 'type': 'backend',      'hours': 40, 'price': 4000, 'skills': ['1С', 'Python']},
            {'name': 'Интеграция с существующими системами', 'type': 'integration',  'hours': 32, 'price': 4500, 'skills': ['Python', 'SQL']},
            {'name': 'Тестирование',                         'type': 'testing',      'hours': 16, 'price': 3000, 'skills': ['QA / Тестирование']},
            {'name': 'Внедрение и миграция данных',          'type': 'deploy',       'hours': 24, 'price': 3500, 'skills': ['DevOps', 'SQL']},
            {'name': 'Обучение персонала',                   'type': 'training',     'hours': 16, 'price': 3000, 'skills': ['Техническое обучение']},
        ],
    },
    'consulting': {
        'name': 'ИТ-консалтинг',
        'description': 'Аудит, рекомендации, отчёт',
        'duration': 14,
        'stages': [
            {'name': 'Аудит текущего состояния',    'type': 'analysis',    'hours': 16, 'price': 5000, 'skills': ['Системный анализ', 'Бизнес-анализ']},
            {'name': 'Разработка рекомендаций',     'type': 'consulting',  'hours': 24, 'price': 5000, 'skills': ['Системный анализ']},
            {'name': 'Подготовка отчёта',           'type': 'other',       'hours': 8,  'price': 4000, 'skills': ['Бизнес-анализ']},
        ],
    },
    'development': {
        'name': 'Разработка ПО',
        'description': 'Полный цикл разработки: требования → архитектура → backend → frontend → QA → деплой',
        'duration': 90,
        'stages': [
            {'name': 'Сбор и анализ требований',     'type': 'analysis',  'hours': 24, 'price': 4000, 'skills': ['Системный анализ', 'Бизнес-анализ']},
            {'name': 'Проектирование архитектуры',   'type': 'analysis',  'hours': 16, 'price': 5000, 'skills': ['Python', 'DevOps']},
            {'name': 'Backend-разработка',           'type': 'backend',   'hours': 80, 'price': 4000, 'skills': ['Python', 'Django', 'SQL']},
            {'name': 'Frontend-разработка',          'type': 'frontend',  'hours': 60, 'price': 3500, 'skills': ['JavaScript', 'React']},
            {'name': 'Тестирование и QA',            'type': 'testing',   'hours': 40, 'price': 3000, 'skills': ['QA / Тестирование']},
            {'name': 'Развёртывание',                'type': 'deploy',    'hours': 16, 'price': 3500, 'skills': ['DevOps', 'Docker/Kubernetes']},
        ],
    },
    'security': {
        'name': 'Информационная безопасность',
        'description': 'Аудит безопасности, пентест, устранение уязвимостей',
        'duration': 30,
        'stages': [
            {'name': 'Аудит безопасности',         'type': 'security', 'hours': 32, 'price': 6000, 'skills': ['Информационная безопасность']},
            {'name': 'Пентестирование',            'type': 'testing',  'hours': 40, 'price': 6000, 'skills': ['Пентестирование']},
            {'name': 'Устранение уязвимостей',     'type': 'backend',  'hours': 24, 'price': 5000, 'skills': ['Информационная безопасность', 'DevOps']},
            {'name': 'Подготовка отчёта',          'type': 'other',    'hours': 8,  'price': 4000, 'skills': ['Информационная безопасность']},
        ],
    },
    'network': {
        'name': 'Сетевая инфраструктура',
        'description': 'Проектирование, монтаж и настройка сети',
        'duration': 30,
        'stages': [
            {'name': 'Проектирование сети',     'type': 'analysis', 'hours': 16, 'price': 4000, 'skills': ['Сети (Cisco/MikroTik)']},
            {'name': 'Монтаж и настройка',      'type': 'deploy',   'hours': 40, 'price': 3500, 'skills': ['Сети (Cisco/MikroTik)']},
            {'name': 'Тестирование и приёмка',  'type': 'testing',  'hours': 8,  'price': 3000, 'skills': ['QA / Тестирование', 'Сети (Cisco/MikroTik)']},
        ],
    },
    'cloud': {
        'name': 'Облачные решения',
        'description': 'Миграция в облако, настройка мониторинга',
        'duration': 30,
        'stages': [
            {'name': 'Анализ потребностей',      'type': 'analysis', 'hours': 8,  'price': 4000, 'skills': ['Облачные платформы (AWS/Azure)', 'Системный анализ']},
            {'name': 'Миграция в облако',         'type': 'deploy',   'hours': 32, 'price': 4500, 'skills': ['Облачные платформы (AWS/Azure)', 'DevOps']},
            {'name': 'Настройка мониторинга',     'type': 'support',  'hours': 16, 'price': 3500, 'skills': ['DevOps', 'Облачные платформы (AWS/Azure)']},
        ],
    },
    'training': {
        'name': 'Обучение персонала',
        'description': 'Подготовка программы, проведение обучения, тестирование',
        'duration': 14,
        'stages': [
            {'name': 'Подготовка программы обучения',  'type': 'analysis',  'hours': 8,  'price': 3500, 'skills': ['Техническое обучение']},
            {'name': 'Проведение обучения',            'type': 'training',  'hours': 24, 'price': 4000, 'skills': ['Техническое обучение']},
            {'name': 'Итоговое тестирование',          'type': 'testing',   'hours': 4,  'price': 3000, 'skills': ['QA / Тестирование']},
        ],
    },
    'other': {
        'name': 'Общий проект',
        'description': 'Универсальный шаблон ИТ-проекта',
        'duration': 30,
        'stages': [
            {'name': 'Анализ',                 'type': 'analysis', 'hours': 16, 'price': 3500, 'skills': ['Системный анализ']},
            {'name': 'Реализация',             'type': 'backend',  'hours': 40, 'price': 3500, 'skills': ['Python']},
            {'name': 'Тестирование и сдача',   'type': 'testing',  'hours': 8,  'price': 3000, 'skills': ['QA / Тестирование']},
        ],
    },
}


class Command(BaseCommand):
    help = 'Создаёт навыки и шаблоны проектов для всех типов услуг'

    def handle(self, *args, **options):
        # 1. Навыки
        skill_map = {}
        for name, category in SKILLS:
            skill, created = Skill.objects.get_or_create(name=name, defaults={'category': category})
            skill_map[name] = skill
            if created:
                self.stdout.write(self.style.SUCCESS(f'  + Навык: {name}'))

        # 2. Шаблоны и этапы
        for service_type, data in TEMPLATES.items():
            template, created = ProjectTemplate.objects.get_or_create(
                service_type=service_type,
                defaults={
                    'name': data['name'],
                    'description': data['description'],
                    'default_duration_days': data['duration'],
                },
            )
            verb = 'создан' if created else 'уже существует'
            self.stdout.write(self.style.SUCCESS(f'Шаблон «{data["name"]}» — {verb}'))

            if created:
                for idx, stage_data in enumerate(data['stages'], 1):
                    stage = ProjectTemplateStage.objects.create(
                        template=template,
                        name=stage_data['name'],
                        stage_type=stage_data['type'],
                        order=idx,
                        default_hours=stage_data['hours'],
                        default_unit_price=stage_data['price'],
                    )
                    for skill_name in stage_data.get('skills', []):
                        if skill_name in skill_map:
                            stage.required_skills.add(skill_map[skill_name])
                    self.stdout.write(f'    {idx}. {stage_data["name"]}')

        self.stdout.write(self.style.SUCCESS('\nГотово!'))
