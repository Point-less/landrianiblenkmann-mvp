from django.apps import AppConfig


class OpportunitiesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'opportunities'

    def ready(self) -> None:  # pragma: no cover - registry configuration
        super().ready()
        try:
            from django_fsm import FSMField
            from strawberry_django.fields import types as field_types

            field_types.field_type_map[FSMField] = str
        except Exception:  # pragma: no cover - best-effort registration
            pass
