"""
Django settings for bit_platform project.
"""

import os
from pathlib import Path
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ========== БЕЗОПАСНОСТЬ ==========
# SECURITY WARNING: keep the secret key used in production secret!
# Берём SECRET_KEY из переменных окружения (на сервере)
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-md&v@8kn*r$u6)*$_qet4re(+*zob5n#y5(1e%s07yi#w_7i12')

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = True на сервере автоматически станет False
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Разрешённые хосты
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,.onrender.com,.pythonanywhere.com').split(',')


# ========== ПРИЛОЖЕНИЯ ==========
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'accounts',
    'clients',
    'requests_app',
    'proposals',
    'contracts',
    'projects',
    'tasks',
    'documents',
    'chat',
    'reports',
    'dashboard',
    'notifications',
    'time_tracking',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Для статики на сервере
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'bit_platform.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.user_role',
            ],
        },
    },
]

WSGI_APPLICATION = 'bit_platform.wsgi.application'


# ========== БАЗА ДАННЫХ ==========
# На локальном ПК — PostgreSQL
# На Render/PythonAnywhere — берём DATABASE_URL из переменных окружения
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # На сервере (Render или PythonAnywhere с PostgreSQL)
    DATABASES = {
        'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
    }
else:
    # Локальная разработка
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "db_bit",
            "USER": "postgres",
            "PASSWORD": "Test1234",
            "HOST": "localhost",
            "PORT": "5432",
            "OPTIONS": {
                "client_encoding": "UTF8",
            },
        }
    }


# ========== АУТЕНТИФИКАЦИЯ ==========
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_REDIRECT_URL = '/accounts/dashboard/'
LOGOUT_REDIRECT_URL = '/'


# ========== ИНТЕРНАЦИОНАЛИЗАЦИЯ ==========
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True


# ========== СТАТИКА И МЕДИА ==========
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'  # Куда собирается статика на сервере
STATICFILES_DIRS = [BASE_DIR / 'static']  # Откуда брать статику в разработке
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ========== EMAIL (настройки для продакшена) ==========
# На сервере эти переменные будут браться из окружения
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.mail.ru')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 465))
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'True').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'info@bit-company.ru')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'ООО «БИТ» <info@bit-company.ru>')
SITE_URL = os.environ.get('SITE_URL', 'https://your-app.onrender.com')