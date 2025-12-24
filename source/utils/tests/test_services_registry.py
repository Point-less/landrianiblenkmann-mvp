from django.test import TestCase

from utils.services import resolve_service, ServiceInvoker, get_services


class ServiceRegistryTests(TestCase):
    def test_resolve_service_by_name(self):
        svc = resolve_service("CreateOpportunityService", app_label="opportunities")
        self.assertIsNotNone(svc)
        self.assertEqual(svc.__name__, "CreateOpportunityService")

    def test_resolve_service_by_path(self):
        svc = resolve_service("opportunities.services.operations.CreateOperationService")
        self.assertEqual(svc.__name__, "CreateOperationService")

    def test_service_invoker_binds_actor(self):
        from django.contrib.auth import get_user_model

        actor = get_user_model().objects.create_user(username="u", password="pass", email="u@example.com")
        invoker = ServiceInvoker(actor=actor, app_label="opportunities")
        instance = invoker.get("CreateOperationService")
        self.assertEqual(instance.actor, actor)

    def test_get_services_returns_many(self):
        services = get_services(app_label="opportunities")
        self.assertGreater(len(services), 0)
