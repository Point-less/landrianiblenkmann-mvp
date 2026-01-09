from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction
from django.utils import timezone

from core.models import Agent, Contact, Currency, Property
from core.services import LinkContactAgentService
from integrations.models import TokkobrokerProperty
from intentions.models import ProviderIntention, SeekerIntention
from intentions.services import (
    AbandonSeekerIntentionService,
    CreateSeekerIntentionService,
    DeliverValuationService,
    PromoteProviderIntentionService,
    WithdrawProviderIntentionService,
)
from opportunities.models import (
    Operation,
    OperationAgreement,
    OperationType,
    ProviderOpportunity,
    Validation,
    ValidationDocumentType,
)
from opportunities.services import (
    CreateOperationAgreementService,
    CreateSeekerOpportunityService,
    CreateValidationDocumentService,
    MarketingPackageActivateService,
    MarketingPackageUpdateService,
    OperationReinforceService,
    AgreeOperationAgreementService,
    OpportunityPublishService,
    ReviewValidationDocumentService,
    SignOperationAgreementService,
    ValidationAcceptService,
    ValidationPresentService,
)
from users.models import RoleMembership


class Command(BaseCommand):
    help = "Populate the database with a rich demo workflow (intentions → opportunities → operations). Safe to re-run."

    def handle(self, *args, **options):
        call_command("seed_permissions")
        call_command("seed_demo_users")
        self._bootstrap()

        with transaction.atomic():
            self._seed_reference_data()
            agents = self._seed_people()
            contacts, seekers = self._seed_contacts()
            properties, tokko = self._seed_properties()
            provider_intentions = self._seed_provider_intentions(agents, contacts, properties, tokko)
            seeker_intentions = self._seed_seeker_intentions(agents, seekers)
            self._wire_relationships(agents, contacts, seekers)
            self._seed_opportunities_and_operations(provider_intentions, seeker_intentions, agents, tokko)

        self.stdout.write(self.style.SUCCESS("Demo dataset ready."))

    # --- setup helpers -------------------------------------------------
    def _bootstrap(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.filter(is_superuser=True).first()  # service-guard: allow
        if not self.admin_user:
            raise CommandError("A superuser is required; run manage.py createsuperuser or seed_demo_users first.")
        try:
            self.agent_user = user_model.objects.get(username="agent_demo")  # service-guard: allow
        except user_model.DoesNotExist as exc:
            raise CommandError("Expected demo agent user 'agent_demo'. Run seed_demo_users first.") from exc
        agent_membership = RoleMembership.objects.filter(user=self.agent_user).select_related("profile_content_type").first()  # service-guard: allow
        self.agent_profile = getattr(agent_membership, "profile", None) if agent_membership else None
        if not isinstance(self.agent_profile, Agent):
            self.agent_profile = Agent.objects.filter(email="agent@example.com").first()  # service-guard: allow
        if not self.agent_profile:
            raise CommandError("Demo agent profile not found (agent@example.com).")

    # --- data factories -------------------------------------------------
    def _seed_reference_data(self):
        self.currencies = {
            "USD": self._upsert_currency("USD", "US Dollar", "$"),
            "ARS": self._upsert_currency("ARS", "Argentine Peso", "$"),
        }
        self.operation_types = {
            "sale": OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})[0],  # service-guard: allow
            "rent": OperationType.objects.get_or_create(code="rent", defaults={"label": "Rent"})[0],  # service-guard: allow
        }
        # Ensure required validation document types allow PDF uploads.
        for dtype in ValidationDocumentType.objects.filter(required=True):  # service-guard: allow
            if not dtype.accepted_formats:
                dtype.accepted_formats = [".pdf"]
                dtype.save(update_fields=["accepted_formats"])
        ValidationDocumentType.objects.filter(code="other", accepted_formats=[]).update(accepted_formats=[".pdf", ".jpg"])  # service-guard: allow

    def _seed_people(self):
        agents = {
            "agent": self.agent_profile,
            "manager": self._upsert_agent(
                email="manager@example.com",
                first_name="Mariana",
                last_name="Manager",
                phone_number="+54 11 4000-0002",
                commission_split=Decimal("0.55"),
            ),
        }
        return agents

    def _seed_contacts(self):
        owners = {
            "carlos": self._upsert_contact(
                email="carlos.rios@example.com",
                first_name="Carlos",
                last_name="Rios",
                tax_condition=Contact.TaxCondition.CONSUMIDOR_FINAL,
            ),
            "laura": self._upsert_contact(
                email="laura.perez@example.com",
                first_name="Laura",
                last_name="Perez",
                tax_condition=Contact.TaxCondition.RESPONSABLE_INSCRIPTO,
            ),
            "valentina": self._upsert_contact(
                email="valentina.gomez@example.com",
                first_name="Valentina",
                last_name="Gomez",
                tax_condition=Contact.TaxCondition.MONOTRIBUTO,
            ),
            "mateo": self._upsert_contact(
                email="mateo.lopez@example.com",
                first_name="Mateo",
                last_name="Lopez",
                tax_condition=Contact.TaxCondition.EXENTO,
            ),
        }
        seekers = {
            "monica": self._upsert_contact(email="monica.buyer@example.com", first_name="Monica", last_name="Buyer"),
            "karen": self._upsert_contact(email="karen.renter@example.com", first_name="Karen", last_name="Renter"),
            "lucas": self._upsert_contact(email="lucas.investor@example.com", first_name="Lucas", last_name="Investor"),
        }
        return owners, seekers

    def _seed_properties(self):
        properties = {
            "palermo": self._upsert_property("Palermo Loft", "Gorriti 4800, Palermo, CABA"),
            "recoleta": self._upsert_property("Recoleta Townhouse", "Av. Alvear 1500, Recoleta, CABA"),
            "belgrano": self._upsert_property("Belgrano Office", "Av. Libertador 6100, Belgrano, CABA"),
            "nunez": self._upsert_property("Nuñez Studio", "Vedia 1800, Nuñez, CABA"),
            "caballito": self._upsert_property("Caballito Loft", "Av. Pedro Goyena 1200, Caballito, CABA"),
        }
        tokko = {
            "palermo": self._upsert_tokko(1001, "PAL-1001", properties["palermo"]),
            "recoleta": self._upsert_tokko(1002, "REC-1002", properties["recoleta"]),
            "belgrano": self._upsert_tokko(1003, "BEL-1003", properties["belgrano"]),
            "caballito": self._upsert_tokko(1004, "CAB-1004", properties["caballito"]),
        }
        return properties, tokko

    # --- domain seeding -------------------------------------------------
    def _seed_provider_intentions(self, agents, owners, properties, tokko):
        op_sale = self.operation_types["sale"]
        op_rent = self.operation_types["rent"]
        usd = self.currencies["USD"]

        intentions: dict[str, ProviderIntention] = {}

        intentions["assessing"] = self._ensure_provider_intention(
            slug="assessing",
            owner=owners["carlos"],
            agent=agents["agent"],
            property=properties["palermo"],
            operation_type=op_sale,
            notes="Initial walkthrough scheduled; docs pending.",
        )

        intentions["valuated"] = self._ensure_provider_intention(
            slug="valuated",
            owner=owners["laura"],
            agent=agents["agent"],
            property=properties["recoleta"],
            operation_type=op_sale,
            notes="Seller wants quick sale; priced aggressively.",
        )
        if intentions["valuated"].state == ProviderIntention.State.ASSESSING:
            DeliverValuationService.call(
                actor=self.admin_user,
                intention=intentions["valuated"],
                amount=Decimal("2450000.00"),
                currency=usd,
                notes="Based on recent townhouse comps.",
                test_value=Decimal("2500000.00"),
                close_value=Decimal("2400000.00"),
            )

        intentions["promotable"] = self._ensure_provider_intention(
            slug="promotable",
            owner=owners["valentina"],
            agent=agents["agent"],
            property=properties["belgrano"],
            operation_type=op_sale,
            notes="Corner office floor, ideal for SMEs.",
        )
        if intentions["promotable"].state == ProviderIntention.State.ASSESSING:
            DeliverValuationService.call(
                actor=self.admin_user,
                intention=intentions["promotable"],
                amount=Decimal("890000.00"),
                currency=usd,
                notes="Includes garage spots and storage.",
                test_value=Decimal("910000.00"),
                close_value=Decimal("870000.00"),
            )

        intentions["withdrawn"] = self._ensure_provider_intention(
            slug="withdrawn",
            owner=owners["mateo"],
            agent=agents["manager"],
            property=properties["nunez"],
            operation_type=op_rent,
            notes="Owner paused listing for legal review.",
        )
        if intentions["withdrawn"].state != ProviderIntention.State.WITHDRAWN:
            WithdrawProviderIntentionService.call(
                actor=self.admin_user,
                intention=intentions["withdrawn"],
                reason=ProviderIntention.WithdrawReason.CANNOT_SELL,
                notes="Title survey pending.",
            )

        intentions["marketing_demo"] = self._ensure_provider_intention(
            slug="marketing_demo",
            owner=owners["valentina"],
            agent=agents["agent"],
            property=properties["caballito"],
            operation_type=op_sale,
            notes="Showcase listing with multiple marketing revisions.",
        )
        if intentions["marketing_demo"].state == ProviderIntention.State.ASSESSING:
            DeliverValuationService.call(
                actor=self.admin_user,
                intention=intentions["marketing_demo"],
                amount=Decimal("320000.00"),
                currency=usd,
                notes="Caballito loft with balcony.",
                test_value=Decimal("330000.00"),
                close_value=Decimal("315000.00"),
            )

        # Promote the promotable intention into an opportunity if missing.
        if not hasattr(intentions["promotable"], "provider_opportunity"):
            PromoteProviderIntentionService.call(
                actor=self.admin_user,
                intention=intentions["promotable"],
                marketing_package_data={"headline": "Premium Belgrano offices with river views"},
                gross_commission_pct=Decimal("0.05"),
                tokkobroker_property=tokko["belgrano"],
                listing_kind=ProviderOpportunity.ListingKind.EXCLUSIVE,
                contract_effective_on=date.today() - timedelta(days=10),
                contract_expires_on=date.today() + timedelta(days=90),
            )

        return intentions

    def _seed_seeker_intentions(self, agents, seekers):
        usd = self.currencies["USD"]
        sale = self.operation_types["sale"]
        rent = self.operation_types["rent"]
        intentions: dict[str, SeekerIntention] = {}

        intentions["active_buyer"] = SeekerIntention.objects.filter(contact=seekers["monica"]).first()  # service-guard: allow
        if not intentions["active_buyer"]:
            intentions["active_buyer"] = CreateSeekerIntentionService.call(
                actor=self.admin_user,
                contact=seekers["monica"],
                agent=agents["agent"],
                operation_type=sale,
                budget_min=Decimal("750000.00"),
                budget_max=Decimal("900000.00"),
                currency=usd,
                desired_features={"bedrooms": 3, "parking": True, "neighborhoods": ["Belgrano", "Nuñez"]},
                notes="Prefers north-facing units with balcony.",
            )

        intentions["renter_abandoned"] = SeekerIntention.objects.filter(contact=seekers["karen"]).first()  # service-guard: allow
        if not intentions["renter_abandoned"]:
            intentions["renter_abandoned"] = CreateSeekerIntentionService.call(
                actor=self.admin_user,
                contact=seekers["karen"],
                agent=agents["agent"],
                operation_type=rent,
                budget_min=Decimal("800.00"),
                budget_max=Decimal("1200.00"),
                currency=self.currencies["ARS"],
                desired_features={"pets": True, "balcony": True},
            )
            AbandonSeekerIntentionService.call(
                actor=self.admin_user,
                intention=intentions["renter_abandoned"],
                reason="Tenant decided to relocate abroad.",
            )

        intentions["investor_qualifying"] = SeekerIntention.objects.filter(contact=seekers["lucas"]).first()  # service-guard: allow
        if not intentions["investor_qualifying"]:
            intentions["investor_qualifying"] = CreateSeekerIntentionService.call(
                actor=self.admin_user,
                contact=seekers["lucas"],
                agent=agents["agent"],
                operation_type=sale,
                budget_min=Decimal("500000.00"),
                budget_max=Decimal("700000.00"),
                currency=usd,
                desired_features={"use": "office", "yield_target": "5%+"},
            )

        return intentions

    def _wire_relationships(self, agents, owners, seekers):
        # Link owners and seekers to the demo agent for quick lookups.
        for contact in [*owners.values(), *seekers.values()]:
            LinkContactAgentService.call(actor=self.admin_user, contact=contact, agent=agents["agent"])

    def _seed_opportunities_and_operations(self, provider_intentions, seeker_intentions, agents, tokko):
        # Work with the promoted intention/opportunity
        promoted_intention = provider_intentions["promotable"]
        provider_opportunity = promoted_intention.provider_opportunity
        validation = Validation.objects.get(opportunity=provider_opportunity)  # service-guard: allow

        self._ensure_validation_documents(validation)
        self._ensure_validation_approval(validation)
        if provider_opportunity.state == ProviderOpportunity.State.VALIDATING:
            OpportunityPublishService.call(actor=self.admin_user, opportunity=provider_opportunity)
        self._activate_marketing(provider_opportunity)

        # Create a seeker opportunity for the active buyer
        buyer_intention = seeker_intentions["active_buyer"]
        try:
            seeker_opportunity = buyer_intention.seeker_opportunity
        except SeekerIntention.seeker_opportunity.RelatedObjectDoesNotExist:
            seeker_opportunity = CreateSeekerOpportunityService.call(
                actor=self.admin_user,
                intention=buyer_intention,
                gross_commission_pct=Decimal("0.03"),
            )

        agreement = OperationAgreement.objects.filter(  # service-guard: allow
            provider_opportunity=provider_opportunity,
            seeker_opportunity=seeker_opportunity,
        ).first()
        if not agreement:
            agreement = CreateOperationAgreementService.call(
                actor=self.agent_user,
                provider_opportunity=provider_opportunity,
                seeker_opportunity=seeker_opportunity,
                initial_offered_amount=Decimal("880000.00"),
                notes="Buyer toured property with agent_demo.",
            )

        if agreement.state == OperationAgreement.State.PENDING:
            agreement = AgreeOperationAgreementService.call(actor=self.admin_user, agreement=agreement)

        operation = getattr(agreement, "operation", None)
        if not operation:
            _, operation = SignOperationAgreementService.call(
                actor=self.admin_user,
                agreement=agreement,
                signed_document=self._fake_pdf("agreement.pdf", "Signed agreement"),
                reserve_amount=Decimal("200000.00"),
                reserve_deadline=date.today() + timedelta(days=20),
                currency=self.currencies["USD"],
                notes="Reserve collected via escrow.",
            )

        if operation.state == Operation.State.OFFERED:
            OperationReinforceService.call(
                actor=self.admin_user,
                operation=operation,
                offered_amount=Decimal("885000.00"),
                reinforcement_amount=Decimal("50000.00"),
                declared_deed_value=Decimal("880000.00"),
            )
        # Leave reinforced (do not close) so the opportunity remains in MARKETING for demo lists.

        self._seed_marketing_revision_demo(provider_intentions, tokko)

    def _seed_marketing_revision_demo(self, provider_intentions, tokko):
        intention = provider_intentions["marketing_demo"]
        try:
            opportunity = intention.provider_opportunity
        except ProviderOpportunity.DoesNotExist:
            opportunity = PromoteProviderIntentionService.call(
                actor=self.admin_user,
                intention=intention,
                marketing_package_data={"headline": "Modern Caballito loft"},
                gross_commission_pct=Decimal("0.05"),
                tokkobroker_property=tokko["caballito"],
                listing_kind=ProviderOpportunity.ListingKind.EXCLUSIVE,
                contract_expires_on=date.today() + timedelta(days=180),
            )

        validation = Validation.objects.get(opportunity=opportunity)  # service-guard: allow
        self._ensure_validation_documents(validation)
        self._ensure_validation_approval(validation)
        if opportunity.state == ProviderOpportunity.State.VALIDATING:
            OpportunityPublishService.call(actor=self.admin_user, opportunity=opportunity)

        package = opportunity.marketing_packages.filter(is_active=True).first()
        if package and package.state == package.State.PREPARING:
            package.headline = package.headline or "Modern Caballito loft"
            package.price = package.price or Decimal("325000.00")
            package.currency = package.currency or self.currencies["USD"]
            package.description = package.description or "Bright 2BR with open kitchen and balcony."
            package.features = ["2 bedrooms", "Balcony", "Open kitchen", "Low expenses"]
            package.media_assets = [
                "https://picsum.photos/seed/cab1/1200/800",
                "https://picsum.photos/seed/cab2/1200/800",
            ]
            package.save()
            MarketingPackageActivateService.call(actor=self.admin_user, package=package)

        # Create a couple of content revisions while still in marketing
        if package:
            package = MarketingPackageUpdateService.call(
                actor=self.admin_user,
                package=package,
                headline="Caballito loft with balcony",
                price=Decimal("335000.00"),
                features=["2 bedrooms", "Balcony", "Refitted kitchen", "Laundry"],
            )
            MarketingPackageUpdateService.call(
                actor=self.admin_user,
                package=package,
                description="Staged unit ready to show; near subway line A.",
                media_assets=[
                    "https://picsum.photos/seed/cab3/1200/800",
                    "https://picsum.photos/seed/cab4/1200/800",
                ],
            )

    # --- validation helpers --------------------------------------------
    def _ensure_validation_documents(self, validation: Validation):
        required_types = list(validation.required_document_types())
        for dtype in required_types:
            if not validation.documents.filter(document_type=dtype).exists():
                CreateValidationDocumentService.call(
                    actor=self.admin_user,
                    validation=validation,
                    document_type=dtype,
                    document=self._fake_pdf(f"{dtype.code}.pdf", f"{dtype.label} sample"),
                    observations="Auto-generated demo document",
                )

    def _ensure_validation_approval(self, validation: Validation):
        if validation.state == Validation.State.PREPARING:
            ValidationPresentService.call(actor=self.admin_user, validation=validation)

        if validation.state == Validation.State.PRESENTED:
            for doc in validation.documents.filter(status="pending"):
                ReviewValidationDocumentService.call(
                    actor=self.admin_user,
                    document=doc,
                    action="accept",
                    reviewer=self.admin_user,
                    comment="Looks good for demo.",
                )
            ValidationAcceptService.call(actor=self.admin_user, validation=validation)

    def _activate_marketing(self, opportunity: ProviderOpportunity):
        package = opportunity.marketing_packages.order_by("-created_at").first()
        if package and package.state == package.State.PREPARING:
            package.headline = package.headline or f"Listing for {opportunity.property}"
            package.description = package.description or "Published for demo traffic; includes staged media assets."
            package.price = package.price or opportunity.valuation_test_value
            package.currency = package.currency or self.currencies["USD"]
            package.media_assets = package.media_assets or [
                "https://picsum.photos/seed/belgrano1/1200/800",
                "https://picsum.photos/seed/belgrano2/1200/800",
            ]
            package.features = package.features or ["River view", "2 parking spots", "24/7 security"]
            package.save()
            MarketingPackageActivateService.call(actor=self.admin_user, package=package)

    # --- persistence helpers -------------------------------------------
    def _upsert_currency(self, code: str, name: str, symbol: str) -> Currency:
        return self._get_or_fix_single(
            model=Currency,
            lookup={"code": code},
            defaults={"name": name, "symbol": symbol},
        )

    def _upsert_agent(self, email: str, first_name: str, last_name: str, phone_number: str, commission_split: Decimal):
        return self._get_or_fix_single(
            model=Agent,
            lookup={"email": email},
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "phone_number": phone_number,
                "commission_split": commission_split,
            },
        )

    def _upsert_contact(self, email: str, first_name: str, last_name: str, tax_condition: str | None = None):
        return self._get_or_fix_single(
            model=Contact,
            lookup={"email": email},
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "tax_condition": tax_condition or "",
            },
        )

    def _upsert_property(self, name: str, full_address: str):
        return self._get_or_fix_single(
            model=Property,
            lookup={"name": name},
            defaults={"full_address": full_address},
        )

    def _upsert_tokko(self, tokko_id: int, ref_code: str, property: Property):
        return self._get_or_fix_single(
            model=TokkobrokerProperty,
            lookup={"tokko_id": tokko_id},
            defaults={"ref_code": ref_code, "address": property.full_address},
        )

    def _get_or_fix_single(self, *, model, lookup: dict, defaults: dict):
        """Return a single instance, updating or cleaning duplicates instead of raising."""

        qs = model.objects.filter(**lookup)  # service-guard: allow
        if not qs.exists():
            return model.objects.create(**lookup, **defaults)  # service-guard: allow

        obj = qs.order_by("id").first()
        if qs.count() > 1:
            qs.exclude(pk=obj.pk).delete()  # service-guard: allow (dedupe seeded data)

        updated_fields = []
        for field, value in defaults.items():
            if getattr(obj, field) != value:
                setattr(obj, field, value)
                updated_fields.append(field)
        if updated_fields:
            obj.save(update_fields=updated_fields)
        return obj

    def _ensure_provider_intention(self, slug: str, owner, agent, property, operation_type, notes: str):
        intention, created = ProviderIntention.objects.update_or_create(  # service-guard: allow
            owner=owner,
            agent=agent,
            property=property,
            defaults={"operation_type": operation_type, "notes": notes},
        )
        # Preserve existing state transitions; only reset notes/operation_type.
        if created and intention.state != ProviderIntention.State.ASSESSING:
            intention.state = ProviderIntention.State.ASSESSING
            intention.save(update_fields=["state"])
        return intention

    # --- misc ----------------------------------------------------------
    @staticmethod
    def _fake_pdf(name: str, text: str):
        return ContentFile(f"{text}\nGenerated at {timezone.now()}".encode("utf-8"), name=name)
