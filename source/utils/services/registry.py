import inspect
import pkgutil
import sys
from importlib import import_module
from typing import Dict, Iterable, List, Optional, Tuple, Type

from django.apps import AppConfig, apps
from django.utils.module_loading import module_has_submodule

from core.services.base import BaseService

ServiceClass = Type[BaseService]
_service_registry: Optional[Dict[str, Tuple[ServiceClass, ...]]] = None


def _import_services_module(app_config: AppConfig):
    module_name = f"{app_config.name}.services"
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        if module_has_submodule(app_config.module, "services"):
            raise
        return None

    if hasattr(module, "__path__"):
        prefix = module.__name__ + "."
        for _, name, _ in pkgutil.walk_packages(module.__path__, prefix):
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
                and attr is not BaseService
            ):
                services.add(attr)
    return tuple(sorted(services, key=lambda cls: f"{cls.__module__}.{cls.__name__}"))


def _build_service_registry() -> Dict[str, Tuple[ServiceClass, ...]]:
    registry: Dict[str, Tuple[ServiceClass, ...]] = {}
    for app_config in apps.get_app_configs():
        module = _import_services_module(app_config)
        if not module:
            continue
        services = _collect_services_from_module(module)
        if services:
            registry[app_config.label] = services
    return registry


def discover_services(force: bool = False) -> Dict[str, Tuple[ServiceClass, ...]]:
    global _service_registry
    if force or _service_registry is None:
        _service_registry = _build_service_registry()
    return _service_registry


def get_services(
    app_label: Optional[str] = None,
    *,
    include_base: bool = False,
    force: bool = False,
) -> List[ServiceClass]:
    registry = discover_services(force=force)

    if app_label is not None:
        services = list(registry.get(app_label, ()))
    else:
        services = [svc for svc_list in registry.values() for svc in svc_list]

    if not include_base:
        services = [svc for svc in services if svc is not BaseService]

    return services


def iter_services(force: bool = False) -> Iterable[ServiceClass]:
    yield from get_services(force=force)
