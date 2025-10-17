from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered


def _default_list_display(model):
    concrete_fields = [
        field.name
        for field in model._meta.concrete_fields
        if not getattr(field, 'many_to_many', False)
    ]
    if not concrete_fields:
        return ('__str__',)
    # Ensure the primary key is first for easy identification.
    pk_name = model._meta.pk.name
    field_names = [pk_name] + [
        name for name in concrete_fields if name != pk_name
    ]
    return tuple(field_names[:5])


class AutoAdmin(admin.ModelAdmin):
    list_per_page = 25


for model in apps.get_models():
    try:
        if model in admin.site._registry:
            continue
        admin_class = type(
            f"{model.__name__}AutoAdmin",
            (AutoAdmin,),
            {"list_display": _default_list_display(model)},
        )
        admin.site.register(model, admin_class)
    except AlreadyRegistered:
        continue
