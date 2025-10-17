import inspect
import pkgutil
import sys
from importlib import import_module
from typing import Dict, Iterable, List, Optional, Tuple, Type

from django.apps import AppConfig, apps
from django.utils.module_loading import module_has_submodule

from core.services.base import BaseService

ServiceClass = Type[BaseService]
_services_cache: Optional[Dict[str, Tuple[ServiceClass, ...]]] = None


def _import_services_module(app_config: AppConfig):
    module_name = f"{app_config.name}.services"
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        if module_has_submodule(app_config.module, "services"):
            # The module exists but raised; re-raise to highlight the error.
            raise
        return None

    if hasattr(module, "__path__"):
        prefix = module.__name__ + "."
        for finder, name, ispkg in pkgutil.walk_packages(module.__path__, prefix):
            import_module(name)

    return module


def _collect_services_from_module(module) -> Tuple[ServiceClass, ...]:
    services = set()
    modules = [module]
    prefix = module.__name__ + "."
    modules.extend(
        mod for name, mod in sys.modules.items() if name.startswith(prefix)
    )

    for mod in modules:
        for attr in vars(mod).values():
            if (
                inspect.isclass(attr)
                and issubclass(attr, BaseService)
                and attr not in {BaseService}
            ):
                services.add(attr)
    return tuple(sorted(services, key=lambda cls: f"{cls.__module__}.{cls.__name__}"))


def _build_services_cache() -> Dict[str, Tuple[ServiceClass, ...]]:
    cache: Dict[str, Tuple[ServiceClass, ...]] = {}
    for app_config in apps.get_app_configs():
        module = _import_services_module(app_config)
        if not module:
            continue
        services = _collect_services_from_module(module)
        if services:
            cache[app_config.label] = services
    return cache


def refresh_service_cache() -> None:
    global _services_cache
    _services_cache = _build_services_cache()


def get_services(
    app_label: Optional[str] = None,
    *,
    include_base: bool = False,
    refresh: bool = False,
) -> List[ServiceClass]:
    global _services_cache
    if refresh or _services_cache is None:
        refresh_service_cache()

    assert _services_cache is not None

    if app_label is not None:
        services = list(_services_cache.get(app_label, ()))
    else:
        services = [svc for svc_list in _services_cache.values() for svc in svc_list]

    if not include_base:
        services = [svc for svc in services if svc is not BaseService]

    return services


def iter_services(refresh: bool = False) -> Iterable[ServiceClass]:
    for service in get_services(refresh=refresh):
        yield service
