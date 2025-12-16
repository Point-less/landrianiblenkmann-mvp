from __future__ import annotations

from builtins import property as builtin_property

from collections import Counter
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django_fsm import FSMField, transition

from core.models import Currency
from integrations.models import TokkobrokerProperty
from utils.mixins import FSMTrackingMixin, FSMTransitionMixin, TimeStampedMixin

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
        "intentions.ProviderIntention",
        on_delete=models.PROTECT,
        related_name="provider_opportunity",
    )
    tokkobroker_property = models.OneToOneField(
        TokkobrokerProperty,
        on_delete=models.PROTECT,
        related_name="provider_opportunity",
    )
    contract_expires_on = models.DateField(
        null=True,
        blank=True,
        help_text="Contract end date.",
    )
    contract_effective_on = models.DateField(
        null=True,
        blank=True,
        help_text="Contract effective/start date.",
    )
    listing_kind = models.CharField(
        max_length=20,
        choices=ListingKind.choices,
        default=ListingKind.EXCLUSIVE,
    )
    valuation_test_value = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    valuation_close_value = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    gross_commission_pct = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Negotiated gross commission expressed as 0-1 (e.g., 0.05 for 5%).",
        default=getattr(settings, "DEFAULT_GROSS_COMMISSION_PCT", Decimal("0.04")),
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

        if not self.operation_agreements.filter(operation__state=Operation.State.CLOSED).exists():
            raise ValidationError("Provider opportunity cannot be closed without a closed operation.")


class SeekerOpportunity(TimeStampedMixin, FSMTrackingMixin):
    class State(models.TextChoices):
        MATCHING = "matching", "Matching"
        NEGOTIATING = "negotiating", "Negotiating"
        CLOSED = "closed", "Closed"
        LOST = "lost", "Lost"

    source_intention = models.OneToOneField(
        "intentions.SeekerIntention",
        on_delete=models.PROTECT,
        related_name="seeker_opportunity",
    )
    gross_commission_pct = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Negotiated gross commission expressed as 0-1 (e.g., 0.03 for 3%).",
        default=getattr(settings, "DEFAULT_GROSS_COMMISSION_PCT", Decimal("0.04")),
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
    accepted_formats = models.JSONField(
        default=list,
        blank=True,
        help_text="Allowed file extensions (e.g., ['.pdf', '.jpg']); leave empty to use system defaults.",
    )
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
        APPROVED = "approved", "Approved"

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

    def _documents_by_type(self) -> dict[str, "ValidationDocument"]:
        """Return the latest document per type (newest wins)."""

        docs: dict[str, ValidationDocument] = {}
        for document in self.documents.select_related("document_type").order_by("-created_at", "-id"):
            docs.setdefault(document.document_type.code, document)
        return docs

    def document_status_summary(self) -> dict[str, int]:
        """Aggregate status counts for required documents plus additional count."""

        required_types = list(self.required_document_types())
        status_counts = Counter(item["status"] for item in self.required_documents_status())
        additional_count = self.additional_attachments.count()
        return {
            "required_total": len(required_types),
            "accepted": status_counts.get(ValidationDocument.Status.ACCEPTED, 0),
            "pending": status_counts.get(ValidationDocument.Status.PENDING, 0),
            "rejected": status_counts.get(ValidationDocument.Status.REJECTED, 0),
            "missing": status_counts.get("missing", 0),
            "additional": additional_count,
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

    def custom_documents(self) -> list["ValidationAdditionalDocument"]:
        return list(self.additional_attachments.all())

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

    @property
    def ready_for_approval(self) -> bool:
        try:
            self.ensure_documents_ready_for_acceptance()
            return True
        except ValidationError:
            return False

    def can_revoke(self) -> bool:
        return self.state == self.State.PRESENTED

    @transition(field="state", source=State.PREPARING, target=State.PRESENTED)
    def present(self) -> None:
        self.presented_at = timezone.now()

    @transition(field="state", source=State.PRESENTED, target=State.PREPARING)
    def revoke(self, notes: str | None = None) -> None:
        self.validated_at = None
        if notes is not None:
            self.notes = notes

    @transition(field="state", source=State.PRESENTED, target=State.APPROVED)
    def approve(self) -> None:
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

    @property
    def filename(self) -> str:
        return Path(self.document.name or "").name

    @transition(field="status", source=[Status.PENDING, Status.REJECTED], target=Status.ACCEPTED)
    def accept(self, *, reviewer, comment: str | None = None):
        self.reviewer_comment = comment or ""
        self.decided_by = reviewer
        self.decided_at = timezone.now()

    @transition(field="status", source=Status.PENDING, target=Status.REJECTED)
    def reject(self, *, reviewer, comment: str | None = None):
        self.reviewer_comment = comment or ""
        self.decided_by = reviewer
        self.decided_at = timezone.now()


class ValidationAdditionalDocument(TimeStampedMixin):
    validation = models.ForeignKey(
        Validation,
        on_delete=models.CASCADE,
        related_name="additional_attachments",
    )
    observations = models.TextField(blank=True)
    document = models.FileField(upload_to="validation_additional_documents/%Y/%m/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_additional_validation_documents",
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "validation additional document"
        verbose_name_plural = "validation additional documents"

    def __str__(self) -> str:
        return f"Custom document for {self.validation}"

    @property
    def filename(self) -> str:
        return Path(self.document.name or "").name


class OperationAgreement(TimeStampedMixin, FSMTrackingMixin):
    """
    Models the agreement between provider and seeker agents before creating an operation.

    States:
    1. PENDING: Agreement created, awaiting review
    2. AGREED: Both parties have agreed to the terms
    3. SIGNED: Agreement signed with documentation uploaded, operation auto-created
    4. CANCELLED: Agreement cancelled/not met (from PENDING or AGREED)
    """
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        AGREED = "agreed", "Agreed"
        SIGNED = "signed", "Signed"
        CANCELLED = "cancelled", "Cancelled"

    provider_opportunity = models.ForeignKey(
        ProviderOpportunity,
        on_delete=models.PROTECT,
        related_name="operation_agreements",
    )
    seeker_opportunity = models.ForeignKey(
        SeekerOpportunity,
        on_delete=models.PROTECT,
        related_name="operation_agreements",
    )
    state = FSMField(
        max_length=20,
        choices=State.choices,
        default=State.PENDING,
        protected=False,
    )

    notes = models.TextField(blank=True)
    initial_offered_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
        help_text="Initial offer proposed with this agreement (currency of seeker).",
    )
    agreed_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True, help_text="Reason for cancellation")

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "operation agreement"
        verbose_name_plural = "operation agreements"
        constraints = [
            models.UniqueConstraint(
                fields=["provider_opportunity", "seeker_opportunity"],
                condition=models.Q(state__in=["pending", "agreed"]),
                name="unique_active_operation_agreement",
            )
        ]

    def __str__(self) -> str:
        return f"Agreement {self.get_state_display()} between {self.provider_opportunity} and {self.seeker_opportunity}"

    def validate_operation_types_match(self) -> None:
        """Ensure both opportunities have the same operation type."""
        p_type = self.provider_opportunity.source_intention.operation_type_id
        s_type = self.seeker_opportunity.source_intention.operation_type_id

        if not p_type or not s_type:
            raise ValidationError("Both intentions must specify an operation type before creating an agreement.")

        if p_type != s_type:
            raise ValidationError({
                "operation_type": "Provider and seeker operation types must match."
            })

    def validate_opportunity_states(self) -> None:
        """Ensure opportunities are in valid states for agreement creation."""
        if self.provider_opportunity.state != ProviderOpportunity.State.MARKETING:
            raise ValidationError({
                "provider_opportunity": "Provider opportunity must be in MARKETING state."
            })

        if self.seeker_opportunity.state not in [SeekerOpportunity.State.MATCHING, SeekerOpportunity.State.NEGOTIATING]:
            raise ValidationError({
                "seeker_opportunity": "Seeker opportunity must be in MATCHING or NEGOTIATING state."
            })

    @transition(field="state", source=State.PENDING, target=State.AGREED)
    def agree(self) -> None:
        """Transition from PENDING to AGREED state."""
        self.validate_opportunity_states()
        self.agreed_at = timezone.now()

    @transition(field="state", source=State.AGREED, target=State.SIGNED)
    def sign(self) -> None:
        """
        Transition from AGREED to SIGNED state.

        Note: The operation creation happens in the service layer after this transition.
        The signed document is stored on the created Operation.
        """
        self.signed_at = timezone.now()

    @transition(field="state", source=State.AGREED, target=State.PENDING)
    def revoke(self) -> None:
        """
        Transition from AGREED back to PENDING state.
        Allows renegotiation if needed.
        """
        self.agreed_at = None

    @transition(field="state", source=[State.PENDING, State.AGREED], target=State.CANCELLED)
    def cancel(self, reason: str | None = None) -> None:
        """
        Cancel the agreement from PENDING or AGREED state.

        This transition is used when the agreement is not met or falls through.
        Can be called from PENDING (before agreement) or AGREED (after agreement but before signing).
        """
        self.cancelled_at = timezone.now()
        if reason:
            self.cancellation_reason = reason


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
        if not self.opportunity.validations.filter(state=Validation.State.APPROVED).exists():
            raise ValidationError("Cannot reserve marketing package before validation is accepted.")
        self.state = MarketingPackage.State.PAUSED
        self.save(update_fields=["state", "updated_at"])
        return self

    @transition(field="state", source=State.PAUSED, target=State.PUBLISHED)
    def publish(self) -> "MarketingPackage":
        has_active_operation = self.opportunity.operation_agreements.filter(
            operation__state__in=[Operation.State.OFFERED, Operation.State.REINFORCED]
        ).exists()
        if has_active_operation:
            raise ValidationError(
                "Cannot publish the marketing package while there is an active operation."
            )
        self.state = MarketingPackage.State.PUBLISHED
        self.save(update_fields=["state", "updated_at"])
        return self


class OperationManager(models.Manager):
    """Manager enforcing model-level invariants on creation."""

    def create(self, **kwargs):
        obj = self.model(**kwargs)
        obj.full_clean()
        obj.save(force_insert=True)
        return obj


class Operation(TimeStampedMixin, FSMTrackingMixin):
    class State(models.TextChoices):
        OFFERED = "offered", "Offered"
        REINFORCED = "reinforced", "Reinforced"
        CLOSED = "closed", "Closed"
        LOST = "lost", "Lost"

    agreement = models.OneToOneField(
        "OperationAgreement",
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        related_name="operation",
        help_text="Link to the signed agreement that created this operation.",
    )
    state = FSMField(
        max_length=20,
        choices=State.choices,
        default=State.OFFERED,
        protected=False,
    )
    initial_offered_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Initial offered amount at operation creation.",
    )
    offered_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Current offered amount (set when reinforced).",
    )
    reserve_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Remaining reserved funds after this step.",
    )
    reserve_deadline = models.DateField(
        help_text="Deadline for the reserve amount.",
    )
    reinforcement_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Additional funds available when reinforced.",
    )
    signed_document = models.FileField(
        upload_to="operations/%Y/%m/",
        null=True,
        blank=True,
        help_text="Signed agreement documentation.",
    )
    declared_deed_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Declared deed value captured at reinforcement/closing.",
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='operations',
    )
    occurred_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    lost_reason = models.TextField(blank=True)

    objects = OperationManager()

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "operation"
        verbose_name_plural = "operations"

    def __str__(self) -> str:
        return f"Operation {self.get_state_display()} for {self.agreement.provider_opportunity}"

    def clean(self):
        errors = {}
        if self.currency_id is None:
            errors["currency"] = "Currency is required for the operation."
        if self.initial_offered_amount is None:
            errors["initial_offered_amount"] = "Initial offered amount is required."

        agreement = getattr(self, "agreement", None)
        if agreement is not None and agreement.provider_opportunity_id:
            provider = agreement.provider_opportunity
            if not provider.validations.filter(state=Validation.State.APPROVED).exists():
                errors["agreement"] = "Provider validation must be approved before creating an operation."

        if errors:
            raise ValidationError(errors)

        super().clean()

    @property
    def provider_opportunity(self):
        return self.agreement.provider_opportunity

    @property
    def seeker_opportunity(self):
        return self.agreement.seeker_opportunity

    @transition(field="state", source=State.OFFERED, target=State.REINFORCED)
    def reinforce(self) -> None:
        self.occurred_at = timezone.now()

    @transition(field="state", source=State.REINFORCED, target=State.CLOSED)
    def close(self) -> None:
        self.occurred_at = timezone.now()

    @transition(field="state", source=[State.OFFERED, State.REINFORCED], target=State.LOST)
    def lose(self, reason: str | None = None) -> None:
        self.occurred_at = timezone.now()
        if reason:
            self.lost_reason = reason


__all__ = [
    "MarketingPackage",
    "Operation",
    "OperationAgreement",
    "ProviderOpportunity",
    "SeekerOpportunity",
    "Validation",
    "ValidationDocument",
    "ValidationAdditionalDocument",
]
