from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

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
    license_id = models.CharField(max_length=100, blank=True)
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
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.CAPTURING,
    )
    probability = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Likelihood (0-100) of closing the opportunity.",
    )
    expected_close_date = models.DateField(null=True, blank=True)
    budget_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    source = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "opportunity"
        verbose_name_plural = "opportunities"

    def __str__(self) -> str:
        return self.title


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
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.VALUATING,
    )
    assigned_to = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acquisition_assignments",
    )
    scheduled_at = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "acquisition attempt"
        verbose_name_plural = "acquisition attempts"

    def __str__(self) -> str:
        return f"Acquisition attempt for {self.opportunity}"


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
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.PREPARING,
    )
    presented_at = models.DateTimeField(null=True, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validation_reviews",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "validation"
        verbose_name_plural = "validations"

    def __str__(self) -> str:
        return f"Validation for {self.opportunity}"







class MarketingPackageQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class MarketingPackage(ImmutableRevisionMixin, TimeStampedMixin):
    class EffortType(models.TextChoices):
        GENERAL = "general", "General"
        DIGITAL = "digital", "Digital"
        EVENTS = "events", "Events"
        PRINT = "print", "Print"
        OTHER = "other", "Other"

    class State(models.TextChoices):
        PREPARING = "preparing", "Preparing"
        AVAILABLE = "available", "Available"
        PAUSED = "paused", "Paused"

    REVISION_SCOPE = ("opportunity",)
    IMMUTABLE_ALLOW_UPDATES = frozenset({"is_active", "updated_at"})

    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="marketing_packages",
    )
    version = models.PositiveIntegerField(default=1, editable=False)
    is_active = models.BooleanField(default=True)
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.PREPARING,
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
    effort_type = models.CharField(
        max_length=20,
        choices=EffortType.choices,
        default=EffortType.GENERAL,
    )
    campaign_start = models.DateField(null=True, blank=True)
    campaign_end = models.DateField(null=True, blank=True)
    marketing_notes = models.TextField(blank=True)

    objects = MarketingPackageQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        unique_together = ("opportunity", "version")
        verbose_name = "marketing package"
        verbose_name_plural = "marketing packages"

    def __str__(self) -> str:
        suffix = f" v{self.version}" if self.version else ""
        base = self.headline or f"Marketing package for {self.opportunity}"
        return f"{base}{suffix}"


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
    state = models.CharField(max_length=20, choices=State.choices, default=State.OFFERED)
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
