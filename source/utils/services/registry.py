import inspect
import pkgutil
import sys
from importlib import import_module
from typing import Dict, Iterable, List, Optional, Tuple, Type, Union

from django.apps import AppConfig, apps
from django.utils.module_loading import module_has_submodule

from utils.services.base import BaseService

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

    module_path = getattr(module, "__path__", None)
    if module_path is not None:
        prefix = module.__name__ + "."
        for _, name, _ in pkgutil.walk_packages(module_path, prefix):
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


def resolve_service(
    identifier: Union[str, ServiceClass],
    *,
    app_label: Optional[str] = None,
    force: bool = False,
) -> ServiceClass:
    """Resolve a service class from a dotted path or class name."""

    if inspect.isclass(identifier) and issubclass(identifier, BaseService):
        return identifier

    if not isinstance(identifier, str):
        raise LookupError(f"Unsupported service identifier: {identifier!r}")

    if "." in identifier:
        module_path, _, class_name = identifier.rpartition(".")
        if not module_path:
            raise LookupError(f"Invalid service path '{identifier}'")
        module = import_module(module_path)
        service_cls = getattr(module, class_name, None)
        if not service_cls or not inspect.isclass(service_cls) or not issubclass(service_cls, BaseService):
            raise LookupError(f"Service '{identifier}' could not be resolved")
        return service_cls

    registry = discover_services(force=force)

    candidates: List[ServiceClass] = []
    if app_label is not None:
        candidates = [svc for svc in registry.get(app_label, ()) if svc.__name__ == identifier]
    else:
        for svc_list in registry.values():
            candidates.extend([svc for svc in svc_list if svc.__name__ == identifier])

    if not candidates:
        raise LookupError(f"Service '{identifier}' not found")
    if len(candidates) > 1:
        raise LookupError(
            f"Service name '{identifier}' is ambiguous; provide a dotted path or app_label"
        )

    return candidates[0]


class ServiceInvoker:
    """Helper to fetch and invoke services with a bound actor/context."""

    def __init__(self, *, actor=None, app_label: Optional[str] = None):
        self.actor = actor
        self.app_label = app_label

    def get(self, service_identifier: Union[str, ServiceClass]) -> ServiceClass:
        service_cls = resolve_service(
            service_identifier,
            app_label=self.app_label,
        )
        return service_cls(actor=self.actor)

    def call(self, service_identifier: Union[str, ServiceClass], *args, **kwargs):
        instance = self.get(service_identifier)
        return instance(*args, **kwargs)


def for_actor(actor, *, app_label: Optional[str] = None) -> ServiceInvoker:
    return ServiceInvoker(actor=actor, app_label=app_label)
