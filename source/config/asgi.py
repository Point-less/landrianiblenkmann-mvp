import os
from django.conf import settings
from django.core.asgi import get_asgi_application
from whitenoise import WhiteNoise

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

application = WhiteNoise(django_asgi_app, root=settings.STATIC_ROOT, prefix='static/')
