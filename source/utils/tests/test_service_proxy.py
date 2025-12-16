from django.test import TestCase

from utils.services import service_proxy
from utils.services import registry


class ServiceProxyLazyDiscoveryTests(TestCase):
    def test_discovers_services_when_registry_empty(self):
        previous_registry = registry._service_registry
        registry._service_registry = None
        try:
            _ = service_proxy.opportunities.ProviderOpportunitiesQuery
            self.assertIsNotNone(registry._service_registry)
            self.assertIn("opportunities", registry._service_registry)
        finally:
            registry._service_registry = previous_registry
