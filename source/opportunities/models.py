from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django_fsm import FSMField, transition

from core.models import Currency
from utils.mixins import ImmutableRevisionMixin, TimeStampedMixin


class Contact(TimeStampedMixin):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("last_name", "first_name")
        verbose_name = "contact"
        verbose_name_plural = "contacts"

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Agent(TimeStampedMixin):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    contacts = models.ManyToManyField(
        Contact,
        through='ContactAgentRelationship',
        related_name='agents',
        blank=True,
    )

    class Meta:
        ordering = ("last_name", "first_name")
        verbose_name = "agent"
        verbose_name_plural = "agents"

    def __str__(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email or "Agent"


class ContactAgentRelationship(TimeStampedMixin):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        FORMER = "former", "Former"

    agent = models.ForeignKey(
        'Agent',
        on_delete=models.CASCADE,
        related_name='contact_links',
    )
    contact = models.ForeignKey(
        'Contact',
        on_delete=models.CASCADE,
        related_name='agent_links',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    relationship_notes = models.TextField(blank=True)
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        unique_together = (("agent", "contact"),)
        verbose_name = "contact agent relationship"
        verbose_name_plural = "contact agent relationships"

    def __str__(self) -> str:
        return f"{self.contact} <> {self.agent}"


class Property(TimeStampedMixin):
    name = models.CharField(max_length=255)
    reference_code = models.CharField(max_length=50, blank=True, unique=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "property"
        verbose_name_plural = "properties"

    def __str__(self) -> str:
        return self.name


class Opportunity(TimeStampedMixin):
    class State(models.TextChoices):
        CAPTURING = "capturing", "Capturing"
        VALIDATING = "validating", "Validating"
        MARKETING = "marketing", "Marketing"
        CLOSED = "closed", "Closed"

    title = models.CharField(max_length=255)
    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="opportunities",
    )
    agent = models.ForeignKey(
        Agent,
        on_delete=models.PROTECT,
        related_name="opportunities",
    )
    owner = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="owned_opportunities",
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
        verbose_name = "opportunity"
        verbose_name_plural = "opportunities"

    def __str__(self) -> str:
        return self.title

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
            raise ValidationError("Opportunity cannot be closed without a closed operation.")


class AcquisitionAttempt(TimeStampedMixin):
    class State(models.TextChoices):
        VALUATING = "valuating", "Valuating"
        NEGOTIATING = "negotiating", "Negotiating"
        CLOSED = "closed", "Closed"

    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="acquisition_attempts",
    )
    state = FSMField(
        max_length=20,
        choices=State.choices,
        default=State.VALUATING,
        protected=False,
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "acquisition attempt"
        verbose_name_plural = "acquisition attempts"

    def __str__(self) -> str:
        return f"Acquisition attempt for {self.opportunity}"

    @transition(field="state", source=State.VALUATING, target=State.NEGOTIATING)
    def start_negotiation(self) -> None:
        """Enter the negotiating phase for the attempt."""

    @transition(field="state", source=State.NEGOTIATING, target=State.CLOSED)
    def close_attempt(self, notes: str | None = None) -> None:
        """Close the acquisition attempt."""

        self.closed_at = timezone.now()
        if notes:
            self.notes = notes


class Appraisal(TimeStampedMixin):
    attempt = models.OneToOneField(
        AcquisitionAttempt,
        on_delete=models.CASCADE,
        related_name="appraisal",
    )
    amount = models.DecimalField(
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
        related_name='appraisals',
    )
    evaluated_at = models.DateField(null=True, blank=True)
    summary = models.TextField(blank=True)
    external_report_url = models.URLField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "appraisal"
        verbose_name_plural = "appraisals"

    def __str__(self) -> str:
        return f"Appraisal for {self.attempt.opportunity}"


class Validation(TimeStampedMixin):
    class State(models.TextChoices):
        PREPARING = "preparing", "Preparing"
        PRESENTED = "presented", "Presented"
        ACCEPTED = "accepted", "Accepted"

    opportunity = models.ForeignKey(
        Opportunity,
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

    @transition(field="state", source=State.PREPARING, target=State.PRESENTED)
    def present(self, reviewer: Agent) -> None:
        """Present documentation for review."""

        self.presented_at = timezone.now()
        self.reviewer = reviewer

    @transition(field="state", source=State.PRESENTED, target=State.PREPARING)
    def reset(self, notes: str | None = None) -> None:
        """Return validation to preparation with optional reviewer notes."""

        self.validated_at = None
        if notes is not None:
            self.notes = notes

    @transition(field="state", source=State.PRESENTED, target=State.ACCEPTED)
    def accept(self) -> None:
        """Accept validation and mark as completed."""

        self.validated_at = timezone.now()


class MarketingPackageQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class MarketingPackage(ImmutableRevisionMixin, TimeStampedMixin):
    class State(models.TextChoices):
        PREPARING = "preparing", "Preparing"
        AVAILABLE = "available", "Available"
        PAUSED = "paused", "Paused"

    REVISION_SCOPE = ("opportunity",)
    IMMUTABLE_ALLOW_UPDATES = frozenset({"updated_at"})

    opportunity = models.ForeignKey(
        Opportunity,
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
        suffix = f" v{self.version}" if self.version else ""
        base = self.headline or f"Marketing package for {self.opportunity}"
        return f"{base}{suffix}"

    @transition(field="state", source=State.PREPARING, target=State.AVAILABLE)
    def activate(self) -> "MarketingPackage":
        """Activate package, producing a new revision ready for marketing."""

        new_package = self.clone(state=MarketingPackage.State.AVAILABLE)
        return new_package

    @transition(field="state", source=State.AVAILABLE, target=State.PAUSED)
    def reserve(self) -> "MarketingPackage":
        """Reserve the active package if validation is accepted."""

        if not self.opportunity.validations.filter(state=Validation.State.ACCEPTED).exists():
            raise ValidationError("Cannot reserve marketing package before validation is accepted.")

        new_package = self.clone(state=MarketingPackage.State.PAUSED)
        return new_package

    @transition(field="state", source=State.PAUSED, target=State.AVAILABLE)
    def release(self) -> "MarketingPackage":
        """Reactivate a paused package."""

        new_package = self.clone(state=MarketingPackage.State.AVAILABLE)
        return new_package


class Operation(TimeStampedMixin):
    class State(models.TextChoices):
        OFFERED = "offered", "Offered"
        REINFORCED = "reinforced", "Reinforced"
        CLOSED = "closed", "Closed"

    opportunity = models.ForeignKey(
        Opportunity,
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

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "operation"
        verbose_name_plural = "operations"

    def __str__(self) -> str:
        return f"Operation {self.get_state_display()} for {self.opportunity}"

    @transition(field="state", source=State.OFFERED, target=State.REINFORCED)
    def reinforce(self) -> None:
        """Register an offer reinforcement."""

        self.occurred_at = timezone.now()

    @transition(field="state", source=State.REINFORCED, target=State.CLOSED)
    def close(self) -> None:
        """Record a closed negotiation stage."""

        self.occurred_at = timezone.now()
