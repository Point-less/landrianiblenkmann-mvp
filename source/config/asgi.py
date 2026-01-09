import os

import django
from django.conf import settings
from django.core.asgi import get_asgi_application
from servestatic import ServeStaticASGI

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

django_asgi_app = get_asgi_application()

static_app = ServeStaticASGI(
    django_asgi_app,
    root=settings.STATIC_ROOT,
    prefix=settings.STATIC_URL,
    autorefresh=settings.DEBUG,
)


application = static_app
