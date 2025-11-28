from __future__ import annotations

from builtins import property as builtin_property

from collections import Counter

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django_fsm import FSMField, transition

from core.models import Agent, Currency
from integrations.models import TokkobrokerProperty
from utils.mixins import FSMTrackingMixin, TimeStampedMixin

OPERATION_STATE_CHOICES = (
    ("offered", "Offered"),
    ("reinforced", "Reinforced"),
    ("closed", "Closed"),
    ("lost", "Lost"),
)


class OperationType(models.Model):
    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=100)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.label


class ProviderOpportunity(TimeStampedMixin, FSMTrackingMixin):
    class State(models.TextChoices):
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
        default=State.VALIDATING,
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

    @transition(field="state", source=State.VALIDATING, target=State.MARKETING)
    def start_marketing(self) -> None:
        """Begin marketing the opportunity."""

    @transition(field="state", source=State.MARKETING, target=State.CLOSED)
    def close_opportunity(self) -> None:
        """Close the opportunity once an operation is completed."""

        if not self.operations.filter(state=Operation.State.CLOSED).exists():
            raise ValidationError("Provider opportunity cannot be closed without a closed operation.")


class SeekerOpportunity(TimeStampedMixin, FSMTrackingMixin):
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


class ValidationDocumentType(models.Model):
    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=150)
    required = models.BooleanField(default=False)
    operation_type = models.ForeignKey(
        "OperationType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_types",
        help_text="Restrict this document requirement to a given operation type; leave blank to apply to all.",
    )

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.label


class Validation(TimeStampedMixin, FSMTrackingMixin):
    class State(models.TextChoices):
        PREPARING = "preparing", "Preparing"
        PRESENTED = "presented", "Presented"
        ACCEPTED = "accepted", "Accepted"

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

    def required_document_types(self) -> models.QuerySet["ValidationDocumentType"]:
        qs = ValidationDocumentType.objects.filter(required=True)
        op_type = self.opportunity.source_intention.operation_type
        return qs.filter(models.Q(operation_type__isnull=True) | models.Q(operation_type=op_type))

    @classmethod
    def required_document_choices(cls, include_optional: bool = True) -> list[tuple[str, str]]:
        qs = ValidationDocumentType.objects.filter(required=True)
        choices = [(dt.code, dt.label) for dt in qs]
        if include_optional:
            for dt in ValidationDocumentType.objects.filter(required=False):
                choices.append((dt.code, dt.label))
        return choices

    def _documents_by_type(self) -> dict[str, ValidationDocument]:
        docs = {}
        for document in self.documents.select_related("document_type"):
            docs.setdefault(document.document_type.code, document)
        return docs

    def document_status_summary(self) -> dict[str, int]:
        """Aggregate status counts for required documents plus additional count."""

        required_types = list(self.required_document_types())
        status_counts = Counter(item["status"] for item in self.required_documents_status())
        return {
            "required_total": len(required_types),
            "accepted": status_counts.get(ValidationDocument.Status.ACCEPTED, 0),
            "pending": status_counts.get(ValidationDocument.Status.PENDING, 0),
            "rejected": status_counts.get(ValidationDocument.Status.REJECTED, 0),
            "missing": status_counts.get("missing", 0),
            "additional": self.documents.exclude(document_type__in=required_types).count(),
        }

    def required_documents_status(self) -> list[dict[str, object]]:
        """Summarize required document readiness for UI consumption."""

        docs = self._documents_by_type()
        summary: list[dict[str, object]] = []
        for dtype in self.required_document_types():
            document = docs.get(dtype.code)
            summary.append(
                {
                    "code": dtype.code,
                    "label": dtype.label,
                    "document": document,
                    "status": document.status if document else "missing",
                }
            )
        return summary

    def additional_documents(self) -> list["ValidationDocument"]:
        return [doc for doc in self.documents.select_related("document_type") if not doc.document_type.required]

    def missing_required_documents(self) -> list[str]:
        uploaded = set(self.documents.values_list("document_type__code", flat=True))
        required_codes = set(self.required_document_types().values_list("code", flat=True))
        return [code for code in required_codes if code not in uploaded]

    def ensure_required_documents_uploaded(self) -> None:
        missing = self.missing_required_documents()
        if not missing:
            return
        label_map = dict(ValidationDocumentType.objects.filter(code__in=missing).values_list("code", "label"))
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
        required_codes = list(self.required_document_types().values_list("code", flat=True))
        pending = self.documents.filter(
            document_type__code__in=required_codes,
            status=ValidationDocument.Status.PENDING,
        )
        if pending.exists():
            raise ValidationError("Review all required documents before accepting the validation.")
        rejected = self.documents.filter(
            document_type__code__in=required_codes,
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

    def can_revoke(self) -> bool:
        return self.state == self.State.PRESENTED

    @transition(field="state", source=State.PREPARING, target=State.PRESENTED)
    def present(self, reviewer: Agent) -> None:  # noqa: ARG002 - retained for API compatibility
        self.presented_at = timezone.now()

    @transition(field="state", source=State.PRESENTED, target=State.PREPARING)
    def revoke(self, notes: str | None = None) -> None:
        self.validated_at = None
        if notes is not None:
            self.notes = notes

    @transition(field="state", source=State.PRESENTED, target=State.ACCEPTED)
    def accept(self) -> None:
        self.validated_at = timezone.now()


class ValidationDocument(TimeStampedMixin, FSMTrackingMixin):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    validation = models.ForeignKey(
        Validation,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.ForeignKey(
        ValidationDocumentType,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    observations = models.TextField(blank=True)
    document = models.FileField(upload_to="validation_documents/%Y/%m/")
    status = FSMField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        protected=False,
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
        return f"{self.document_type.label} ({self.get_status_display()})"

    @transition(field="status", source=Status.PENDING, target=Status.ACCEPTED)
    def accept(self, *, reviewer, comment: str | None = None):
        self.reviewer_comment = comment or ""
        self.decided_by = reviewer
        self.decided_at = timezone.now()

    @transition(field="status", source=Status.PENDING, target=Status.REJECTED)
    def reject(self, *, reviewer, comment: str | None = None):
        self.reviewer_comment = comment or ""
        self.decided_by = reviewer
        self.decided_at = timezone.now()


class MarketingPackageQuerySet(models.QuerySet):
    def active(self):
        return self.filter(state=self.model.State.PUBLISHED)


class MarketingPackage(TimeStampedMixin, FSMTrackingMixin):
    class State(models.TextChoices):
        PREPARING = "preparing", "Preparing"
        PUBLISHED = "published", "Published"
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

    @transition(field="state", source=State.PREPARING, target=State.PUBLISHED)
    def activate(self) -> "MarketingPackage":
        self.state = MarketingPackage.State.PUBLISHED
        self.save(update_fields=["state", "updated_at"])
        return self

    @transition(field="state", source=State.PUBLISHED, target=State.PAUSED)
    def pause(self) -> "MarketingPackage":
        if not self.opportunity.validations.filter(state=Validation.State.ACCEPTED).exists():
            raise ValidationError("Cannot reserve marketing package before validation is accepted.")
        self.state = MarketingPackage.State.PAUSED
        self.save(update_fields=["state", "updated_at"])
        return self

    @transition(field="state", source=State.PAUSED, target=State.PUBLISHED)
    def publish(self) -> "MarketingPackage":
        has_active_operation = self.opportunity.operations.filter(
            state__in=[Operation.State.OFFERED, Operation.State.REINFORCED]
        ).exists()
        if has_active_operation:
            raise ValidationError(
                "Cannot publish the marketing package while there is an active operation."
            )
        self.state = MarketingPackage.State.PUBLISHED
        self.save(update_fields=["state", "updated_at"])
        return self


class Operation(TimeStampedMixin, FSMTrackingMixin):
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
