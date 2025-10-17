from django.apps import AppConfig


class UtilsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'utils'
    verbose_name = 'Project Utilities'

    def ready(self):  # pragma: no cover
        from utils.services import refresh_service_cache

        refresh_service_cache()
