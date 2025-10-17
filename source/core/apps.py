from django.apps import AppConfig



class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):  # pragma: no cover - import side effects
        from . import tasks  # noqa: F401 ensures actors register
