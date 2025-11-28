from __future__ import annotations

from builtins import property as builtin_property

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django_fsm import FSMField, transition

from core.models import Agent, Currency
from integrations.models import TokkobrokerProperty
from utils.mixins import FSMLoggableMixin, TimeStampedMixin


class ProviderOpportunity(TimeStampedMixin, FSMLoggableMixin):
    class State(models.TextChoices):
        CAPTURING = "capturing", "Capturing"
        VALIDATING = "validating", "Validating"
        MARKETING = "marketing", "Marketing"
        CLOSED = "closed", "Closed"

    class ListingKind(models.TextChoices):
        EXCLUSIVE = "exclusive", "Exclusive"
        NON_EXCLUSIVE = "non_exclusive", "Non-exclusive"

    source_intention = models.OneToOneField(
        "intentions.SaleProviderIntention",
        on_delete=models.PROTECT,
        related_name="provider_opportunity",
    )
    tokkobroker_property = models.OneToOneField(
        TokkobrokerProperty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="provider_opportunity",
    )
    listing_kind = models.CharField(
        max_length=20,
        choices=ListingKind.choices,
        default=ListingKind.EXCLUSIVE,
    )
    state = FSMField(
        max_length=20,
        choices=State.choices,
        default=State.CAPTURING,
        protected=False,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "provider opportunity"
        verbose_name_plural = "provider opportunities"

    def __str__(self) -> str:
        return f"Provider opportunity for {self.property}"

    @builtin_property
    def property(self):
        return self.source_intention.property

    @builtin_property
    def agent(self):
        return self.source_intention.agent

    @builtin_property
    def owner(self):
        return self.source_intention.owner

    @transition(field="state", source=State.CAPTURING, target=State.VALIDATING)
    def start_validation(self) -> None:
        """Move the opportunity into the validating stage."""

    @transition(field="state", source=State.VALIDATING, target=State.MARKETING)
    def start_marketing(self) -> None:
        """Begin marketing the opportunity."""

    @transition(field="state", source=State.MARKETING, target=State.CLOSED)
    def close_opportunity(self) -> None:
        """Close the opportunity once an operation is completed."""

        if not self.operations.filter(state=Operation.State.CLOSED).exists():
            raise ValidationError("Provider opportunity cannot be closed without a closed operation.")


class SeekerOpportunity(TimeStampedMixin, FSMLoggableMixin):
    class State(models.TextChoices):
        MATCHING = "matching", "Matching"
        NEGOTIATING = "negotiating", "Negotiating"
        CLOSED = "closed", "Closed"
        LOST = "lost", "Lost"

    source_intention = models.OneToOneField(
        "intentions.SaleSeekerIntention",
        on_delete=models.PROTECT,
        related_name="seeker_opportunity",
    )
    notes = models.TextField(blank=True)
    state = FSMField(
        max_length=20,
        choices=State.choices,
        default=State.MATCHING,
        protected=False,
    )
    class Meta:
        ordering = ("-created_at",)
        verbose_name = "seeker opportunity"
        verbose_name_plural = "seeker opportunities"

    def __str__(self) -> str:
        return f"Seeker opportunity for {self.contact}"

    @builtin_property
    def contact(self):
        return self.source_intention.contact

    @builtin_property
    def agent(self):
        return self.source_intention.agent

    @builtin_property
    def currency(self):
        return self.source_intention.currency

    @builtin_property
    def budget_min(self):
        return self.source_intention.budget_min

    @builtin_property
    def budget_max(self):
        return self.source_intention.budget_max

    @transition(field="state", source=State.MATCHING, target=State.NEGOTIATING)
    def start_negotiation(self) -> None:
        if not self.source_intention.currency or not self.source_intention.budget_max:
            raise ValidationError("Seeker opportunity must define budget and currency before negotiating.")

    @transition(field="state", source=State.NEGOTIATING, target=State.CLOSED)
    def close(self) -> None:
        """Signifies the seeker fulfilled their purchase via an operation."""

    @transition(field="state", source=[State.MATCHING, State.NEGOTIATING], target=State.LOST)
    def mark_lost(self, reason: str | None = None) -> None:
        if reason:
            self.notes = (self.notes or "") + f"\nLost: {reason}"

    @transition(field="state", source=State.NEGOTIATING, target=State.MATCHING)
    def resume_matching(self) -> None:
        """Return the seeker to matching after a negotiation that did not close."""


class Validation(TimeStampedMixin, FSMLoggableMixin):
    class State(models.TextChoices):
        PREPARING = "preparing", "Preparing"
        PRESENTED = "presented", "Presented"
        ACCEPTED = "accepted", "Accepted"

    REQUIRED_DOCUMENT_CODES: tuple[str, ...] = (
        "owner_id",
        "deed",
        "sale_authorization",
        "domain_report",
    )

    opportunity = models.ForeignKey(
        ProviderOpportunity,
        on_delete=models.CASCADE,
        related_name="validations",
    )
    state = FSMField(
        max_length=20,
        choices=State.choices,
        default=State.PREPARING,
        protected=False,
    )
    presented_at = models.DateTimeField(null=True, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "validation"
        verbose_name_plural = "validations"

    def __str__(self) -> str:
        return f"Validation for {self.opportunity}"

    @classmethod
    def required_document_choices(cls, include_optional: bool = True) -> list[tuple[str, str]]:
        """Return the configured required documents with human labels."""

        label_map = dict(ValidationDocument.DocumentType.choices)
        choices = [(code, label_map.get(code, code.replace("_", " ").title())) for code in cls.REQUIRED_DOCUMENT_CODES]
        if include_optional:
            choices.append(
                (
                    ValidationDocument.DocumentType.OTHER,
                    label_map.get(ValidationDocument.DocumentType.OTHER, "Other"),
                )
            )
        return choices

    def _documents_by_type(self) -> dict[str, ValidationDocument]:
        docs = {}
        for document in self.documents.all():
            docs.setdefault(document.document_type, document)
        return docs

    def required_documents_status(self) -> list[dict[str, object]]:
        """Summarize required document readiness for UI consumption."""

        label_map = dict(ValidationDocument.DocumentType.choices)
        docs = self._documents_by_type()
        summary: list[dict[str, object]] = []
        for code in self.REQUIRED_DOCUMENT_CODES:
            document = docs.get(code)
            summary.append(
                {
                    "code": code,
                    "label": label_map.get(code, code.replace("_", " ").title()),
                    "document": document,
                    "status": document.status if document else "missing",
                }
            )
        return summary

    def additional_documents(self) -> list["ValidationDocument"]:
        return [doc for doc in self.documents.all() if doc.document_type not in self.REQUIRED_DOCUMENT_CODES]

    def missing_required_documents(self) -> list[str]:
        uploaded = set(self.documents.values_list("document_type", flat=True))
        return [code for code in self.REQUIRED_DOCUMENT_CODES if code not in uploaded]

    def ensure_required_documents_uploaded(self) -> None:
        missing = self.missing_required_documents()
        if not missing:
            return
        label_map = dict(ValidationDocument.DocumentType.choices)
        missing_labels = [label_map.get(code, code.replace("_", " ").title()) for code in missing]
        raise ValidationError(
            {
                "documents": (
                    "Upload the required documents before presenting: "
                    + ", ".join(missing_labels)
                )
            }
        )

    def ensure_documents_ready_for_acceptance(self) -> None:
        self.ensure_required_documents_uploaded()
        pending = self.documents.filter(
            document_type__in=self.REQUIRED_DOCUMENT_CODES,
            status=ValidationDocument.Status.PENDING,
        )
        if pending.exists():
            raise ValidationError("Review all required documents before accepting the validation.")
        rejected = self.documents.filter(
            document_type__in=self.REQUIRED_DOCUMENT_CODES,
            status=ValidationDocument.Status.REJECTED,
        )
        if rejected.exists():
            raise ValidationError("Resolve rejected documents before accepting the validation.")

    def can_present(self) -> bool:
        if self.state != self.State.PREPARING:
            return False
        try:
            self.ensure_required_documents_uploaded()
        except ValidationError:
            return False
        return True

    def can_accept(self) -> bool:
        if self.state != self.State.PRESENTED:
            return False
        try:
            self.ensure_documents_ready_for_acceptance()
        except ValidationError:
            return False
        return True

    def can_reset(self) -> bool:
        return self.state == self.State.PRESENTED

    @transition(field="state", source=State.PREPARING, target=State.PRESENTED)
    def present(self, reviewer: Agent) -> None:  # noqa: ARG002 - retained for API compatibility
        self.presented_at = timezone.now()

    @transition(field="state", source=State.PRESENTED, target=State.PREPARING)
    def reset(self, notes: str | None = None) -> None:
        self.validated_at = None
        if notes is not None:
            self.notes = notes

    @transition(field="state", source=State.PRESENTED, target=State.ACCEPTED)
    def accept(self) -> None:
        self.validated_at = timezone.now()


class ValidationDocument(TimeStampedMixin):
    class DocumentType(models.TextChoices):
        OWNER_ID = "owner_id", "DNI PROPIETARIO"
        DEED = "deed", "ESCRITURA"
        SALE_AUTHORIZATION = "sale_authorization", "AUTORIZACIÓN DE VENTA"
        DOMAIN_REPORT = "domain_report", "INFORME DE DOMINIO"
        OTHER = "other", "OTRO DOCUMENTO"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    validation = models.ForeignKey(
        Validation,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(
        max_length=50,
        choices=DocumentType.choices,
        default=DocumentType.OTHER,
    )
    name = models.CharField(max_length=255)
    document = models.FileField(upload_to="validation_documents/%Y/%m/")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewer_comment = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_validation_documents",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_validation_documents",
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "validation document"
        verbose_name_plural = "validation documents"

    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"

    def _ensure_pending(self):
        if self.status != self.Status.PENDING:
            raise ValidationError("Document has already been reviewed.")

    def accept(self, *, reviewer, comment: str | None = None):
        self._ensure_pending()
        self.status = self.Status.ACCEPTED
        self.reviewer_comment = comment or ""
        self.decided_by = reviewer
        self.decided_at = timezone.now()

    def reject(self, *, reviewer, comment: str | None = None):
        self._ensure_pending()
        self.status = self.Status.REJECTED
        self.reviewer_comment = comment or ""
        self.decided_by = reviewer
        self.decided_at = timezone.now()


class MarketingPackageQuerySet(models.QuerySet):
    def active(self):
        return self.filter(state=self.model.State.AVAILABLE)


class MarketingPackage(TimeStampedMixin, FSMLoggableMixin):
    class State(models.TextChoices):
        PREPARING = "preparing", "Preparing"
        AVAILABLE = "available", "Available"
        PAUSED = "paused", "Paused"

    opportunity = models.ForeignKey(
        ProviderOpportunity,
        on_delete=models.CASCADE,
        related_name="marketing_packages",
    )
    state = FSMField(
        max_length=20,
        choices=State.choices,
        default=State.PREPARING,
        protected=False,
    )
    headline = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='marketing_packages',
    )
    features = models.JSONField(blank=True, default=list, help_text="Key property highlights or amenities.")
    media_assets = models.JSONField(blank=True, default=list, help_text="List of image or video asset URLs.")

    objects = MarketingPackageQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "marketing package"
        verbose_name_plural = "marketing packages"

    def __str__(self) -> str:
        base = self.headline or f"Marketing package for {self.opportunity}"
        return base

    @transition(field="state", source=State.PREPARING, target=State.AVAILABLE)
    def activate(self) -> "MarketingPackage":
        self.state = MarketingPackage.State.AVAILABLE
        self.save(update_fields=["state", "updated_at"])
        return self

    @transition(field="state", source=State.AVAILABLE, target=State.PAUSED)
    def reserve(self) -> "MarketingPackage":
        if not self.opportunity.validations.filter(state=Validation.State.ACCEPTED).exists():
            raise ValidationError("Cannot reserve marketing package before validation is accepted.")
        self.state = MarketingPackage.State.PAUSED
        self.save(update_fields=["state", "updated_at"])
        return self

    @transition(field="state", source=State.PAUSED, target=State.AVAILABLE)
    def release(self) -> "MarketingPackage":
        has_active_operation = self.opportunity.operations.filter(
            state__in=[Operation.State.OFFERED, Operation.State.REINFORCED]
        ).exists()
        if has_active_operation:
            raise ValidationError(
                "Cannot publish the marketing package while there is an active operation."
            )
        self.state = MarketingPackage.State.AVAILABLE
        self.save(update_fields=["state", "updated_at"])
        return self


class Operation(TimeStampedMixin, FSMLoggableMixin):
    class State(models.TextChoices):
        OFFERED = "offered", "Offered"
        REINFORCED = "reinforced", "Reinforced"
        CLOSED = "closed", "Closed"
        LOST = "lost", "Lost"

    provider_opportunity = models.ForeignKey(
        ProviderOpportunity,
        on_delete=models.CASCADE,
        related_name="operations",
    )
    seeker_opportunity = models.ForeignKey(
        SeekerOpportunity,
        on_delete=models.CASCADE,
        related_name="operations",
    )
    state = FSMField(
        max_length=20,
        choices=State.choices,
        default=State.OFFERED,
        protected=False,
    )
    offered_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Amount proposed in this negotiation step.",
    )
    reserve_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Remaining reserved funds after this step.",
    )
    reinforcement_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Additional funds available for reinforcement, if applicable.",
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='operations',
    )
    occurred_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    lost_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "operation"
        verbose_name_plural = "operations"
        constraints = [
            models.UniqueConstraint(
                fields=["provider_opportunity", "seeker_opportunity"],
                condition=models.Q(state__in=["offered", "reinforced"]),
                name="opportunities_unique_active_operation",
            )
        ]

    def __str__(self) -> str:
        return f"Operation {self.get_state_display()} for {self.provider_opportunity}"

    @transition(field="state", source=State.OFFERED, target=State.REINFORCED)
    def reinforce(self) -> None:
        self.occurred_at = timezone.now()

    @transition(field="state", source=State.REINFORCED, target=State.CLOSED)
    def close(self) -> None:
        self.occurred_at = timezone.now()
        # Ensure the state is persisted as CLOSED before dependent transitions need it.
        self.state = Operation.State.CLOSED
        self.save(update_fields=["state", "occurred_at", "updated_at"])
        self.provider_opportunity.close_opportunity()
        self.provider_opportunity.save(update_fields=["state", "updated_at"])
        if self.seeker_opportunity.state == SeekerOpportunity.State.NEGOTIATING:
            self.seeker_opportunity.close()
            self.seeker_opportunity.save(update_fields=["state", "updated_at"])

    @transition(field="state", source=[State.OFFERED, State.REINFORCED], target=State.LOST)
    def lose(self, reason: str | None = None) -> None:
        self.occurred_at = timezone.now()
        if reason:
            self.lost_reason = reason


__all__ = [
    "MarketingPackage",
    "Operation",
    "ProviderOpportunity",
    "SeekerOpportunity",
    "Validation",
    "ValidationDocument",
]
