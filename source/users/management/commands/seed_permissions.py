from django.core.management.base import BaseCommand

from utils import authorization
from utils.services import S


ROLE_MATRIX = {
    "admin": {
        "name": "Administrator",
        "profile_ct": None,
        "permissions": "ALL",
    },
    "manager": {
        "name": "Manager",
        "profile_ct": ContentType,  # placeholder replaced at runtime
        "permissions": "ALL",
    },
    "agent": {
        "name": "Agent",
        "profile_ct": ContentType,  # placeholder replaced at runtime
        # Agents get scoped views (no *.view_all) plus the actions they need to run their own pipeline.
        "permissions": {
            authorization.CONTACT_VIEW,
            authorization.CONTACT_CREATE,
            authorization.CONTACT_UPDATE,
            authorization.PROPERTY_VIEW,
            authorization.PROPERTY_CREATE,
            authorization.PROVIDER_INTENTION_VIEW,
            authorization.PROVIDER_INTENTION_CREATE,
            authorization.PROVIDER_INTENTION_VALUATE,
            authorization.PROVIDER_INTENTION_WITHDRAW,
            authorization.PROVIDER_INTENTION_PROMOTE,
            authorization.SEEKER_INTENTION_VIEW,
            authorization.SEEKER_INTENTION_CREATE,
            authorization.SEEKER_INTENTION_ABANDON,
            authorization.PROVIDER_OPPORTUNITY_VIEW,
            authorization.PROVIDER_OPPORTUNITY_CREATE,
            authorization.PROVIDER_OPPORTUNITY_PUBLISH,
            authorization.PROVIDER_OPPORTUNITY_CLOSE,
            authorization.SEEKER_OPPORTUNITY_VIEW,
            authorization.SEEKER_OPPORTUNITY_CREATE,
            authorization.OPERATION_VIEW,
            authorization.OPERATION_CREATE,
            authorization.OPERATION_REINFORCE,
            authorization.OPERATION_LOSE,
            authorization.OPERATION_CLOSE,
            authorization.AGREEMENT_CREATE,
            authorization.AGREEMENT_AGREE,
            authorization.AGREEMENT_SIGN,
            authorization.AGREEMENT_REVOKE,
            authorization.AGREEMENT_CANCEL,
            authorization.REPORT_VIEW,
            authorization.INTEGRATION_VIEW,
            authorization.PROVIDER_OPPORTUNITY_PUBLISH,  # needed for validations/marketing docs
        },
    },
    "viewer": {
        "name": "Viewer",
        "profile_ct": None,
        "permissions": {
            authorization.REPORT_VIEW,
            authorization.INTEGRATION_VIEW,
        },
    },
}


class Command(BaseCommand):
    help = "Seed canonical roles and permissions. Safe to run multiple times."

    def handle(self, *args, **options):
        all_actions = [
            authorization.AGENT_VIEW,
            authorization.AGENT_VIEW_ALL,
            authorization.AGENT_CREATE,
            authorization.AGENT_UPDATE,
            authorization.CONTACT_VIEW,
            authorization.CONTACT_VIEW_ALL,
            authorization.CONTACT_CREATE,
            authorization.CONTACT_UPDATE,
            authorization.PROPERTY_VIEW,
            authorization.PROPERTY_VIEW_ALL,
            authorization.PROPERTY_CREATE,
            authorization.PROPERTY_UPDATE,
            authorization.PROVIDER_INTENTION_VIEW,
            authorization.PROVIDER_INTENTION_VIEW_ALL,
            authorization.PROVIDER_INTENTION_CREATE,
            authorization.PROVIDER_INTENTION_VALUATE,
            authorization.PROVIDER_INTENTION_WITHDRAW,
            authorization.PROVIDER_INTENTION_PROMOTE,
            authorization.SEEKER_INTENTION_VIEW,
            authorization.SEEKER_INTENTION_VIEW_ALL,
            authorization.SEEKER_INTENTION_CREATE,
            authorization.SEEKER_INTENTION_ABANDON,
            authorization.PROVIDER_OPPORTUNITY_VIEW,
            authorization.PROVIDER_OPPORTUNITY_VIEW_ALL,
            authorization.PROVIDER_OPPORTUNITY_CREATE,
            authorization.PROVIDER_OPPORTUNITY_PUBLISH,
            authorization.PROVIDER_OPPORTUNITY_CLOSE,
            authorization.SEEKER_OPPORTUNITY_VIEW,
            authorization.SEEKER_OPPORTUNITY_VIEW_ALL,
            authorization.SEEKER_OPPORTUNITY_CREATE,
            authorization.OPERATION_VIEW,
            authorization.OPERATION_VIEW_ALL,
            authorization.OPERATION_CREATE,
            authorization.OPERATION_REINFORCE,
            authorization.OPERATION_LOSE,
            authorization.OPERATION_CLOSE,
            authorization.AGREEMENT_CREATE,
            authorization.AGREEMENT_AGREE,
            authorization.AGREEMENT_SIGN,
            authorization.AGREEMENT_REVOKE,
            authorization.AGREEMENT_CANCEL,
            authorization.REPORT_VIEW,
            authorization.USER_VIEW,
            authorization.USER_VIEW_ALL,
            authorization.INTEGRATION_VIEW,
            authorization.INTEGRATION_MANAGE,
        ]

        S.users.SeedPermissionsService(actions=all_actions)
        self.stdout.write(self.style.SUCCESS("Roles and permissions seeded."))
