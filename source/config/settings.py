from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'insecure-secret-key')
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'
TEMPLATE_DEBUG = DEBUG
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')
REDIS_CACHE_URL = os.environ.get('REDIS_CACHE_URL', 'redis://redis:6379/0')
REDIS_RESULTS_URL = os.environ.get('REDIS_RESULTS_URL', 'redis://redis:6379/1')

TOKKO_BASE_URL = os.environ.get('TOKKO_BASE_URL', 'https://backend-904.sandbox.tokkobroker.com')
TOKKO_USERNAME = os.environ.get('TOKKO_USERNAME', 'admin')
TOKKO_PASSWORD = os.environ.get('TOKKO_PASSWORD', 'admin')
TOKKO_OTP_TOKEN = os.environ.get('TOKKO_OTP_TOKEN', '123456')
TOKKO_TIMEOUT = int(os.environ.get('TOKKO_TIMEOUT', '30'))

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_dramatiq',
    'django_fsm_log',
    'users.apps.UsersConfig',
    'utils.apps.UtilsConfig',
    'integrations.apps.IntegrationsConfig',
    'opportunities.apps.OpportunitiesConfig',
    'intentions.apps.IntentionsConfig',
    'core.apps.CoreConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'config.middleware.RequireLoginMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

default_loaders = [
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
]

cached_loaders = [('django.template.loaders.cached.Loader', default_loaders)]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': False,
        'OPTIONS': {
            'loaders': default_loaders if DEBUG else cached_loaders,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'app_db'),
        'USER': os.environ.get('DB_USER', 'app_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'app_password'),
        'HOST': os.environ.get('DB_HOST', 'postgres'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_CACHE_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.environ.get('TZ', 'UTC')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'users.User'

LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/'
LOGIN_REQUIRED_EXEMPT_URLS = [
    LOGIN_URL,
    '/health/',
    '/trigger-log/',
]
LOGIN_REQUIRED_EXEMPT_PREFIXES = [
    path for path in (
        STATIC_URL,
        MEDIA_URL,
        '/_strawberry/static/',
    )
    if path
]

DRAMATIQ_BROKER = {
    'BROKER': 'dramatiq.brokers.rabbitmq.RabbitmqBroker',
    'OPTIONS': {
        'url': os.environ.get('DRAMATIQ_BROKER_URL', 'amqp://guest:guest@rabbitmq:5672/%2F'),
    },
    'MIDDLEWARE': [
        'django_dramatiq.middleware.DbConnectionsMiddleware',
        'django_dramatiq.middleware.AdminMiddleware',
    ],
}

DRAMATIQ_TASKS_DATABASE = 'default'

DRAMATIQ_RESULT_BACKEND = {
    'BACKEND': 'dramatiq.results.backends.redis.RedisBackend',
    'BACKEND_OPTIONS': {
        'url': REDIS_RESULTS_URL,
    },
}

DRAMATIQ_RESULT_BACKEND_ENABLED = True

CSRF_TRUSTED_ORIGINS = [
    "https://*.marketview.com.ar",
]