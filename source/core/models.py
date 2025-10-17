from copy import deepcopy

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model adding created/updated auditing fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Contact(TimeStampedModel):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("last_name", "first_name")

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Agent(TimeStampedModel):
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

    def __str__(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email or "Agent"


class ContactAgentRelationship(TimeStampedModel):
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

    def __str__(self) -> str:
        return f"{self.contact} <> {self.agent}"


class Currency(TimeStampedModel):
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10, blank=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.code


class Property(TimeStampedModel):
    name = models.CharField(max_length=255)
    reference_code = models.CharField(max_length=50, blank=True, unique=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Opportunity(TimeStampedModel):
    class Stage(models.TextChoices):
        PROSPECTING = "prospecting", "Prospecting"
        APPRAISAL = "appraisal", "Appraisal"
        DOCUMENTATION = "documentation", "Documentation"
        LISTING = "listing", "Listing"
        CLOSED = "closed", "Closed"
        LOST = "lost", "Lost"

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
    stage = models.CharField(
        max_length=20,
        choices=Stage.choices,
        default=Stage.PROSPECTING,
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

    def __str__(self) -> str:
        return self.title


class Prospecting(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="prospecting_entries",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
    )
    scheduled_for = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prospecting_assignments",
    )
    summary = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Prospecting for {self.opportunity}"


class Appraisal(TimeStampedModel):
    prospecting = models.OneToOneField(
        Prospecting,
        on_delete=models.CASCADE,
        related_name="appraisal",
    )
    valuation_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    currency = models.ForeignKey(
        'Currency',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='appraisals',
    )
    valuation_date = models.DateField(null=True, blank=True)
    summary = models.TextField(blank=True)
    external_report_url = models.URLField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Appraisal for {self.prospecting.opportunity}"


class DocumentationValidation(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="documentation_attempts",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentation_reviews",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-requested_at",)

    def __str__(self) -> str:
        return f"Documentation validation for {self.opportunity}"



class Listing(TimeStampedModel):
    class EffortType(models.TextChoices):
        GENERAL = "general", "General"
        DIGITAL = "digital", "Digital"
        EVENTS = "events", "Events"
        PRINT = "print", "Print"
        OTHER = "other", "Other"

    TRACKED_FIELDS = (
        "headline",
        "description",
        "price",
        "currency_id",
        "features",
        "media_assets",
        "effort_type",
        "campaign_start",
        "campaign_end",
        "marketing_notes",
    )

    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="listings",
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
        'Currency',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='listings',
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

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.headline or f"Marketing package for {self.opportunity}"

    def save(self, *args, **kwargs):  # pragma: no cover - side effect heavy
        create_snapshot = kwargs.pop("create_snapshot", True)
        performance_metrics = kwargs.pop("performance_metrics", None)
        captured_by = kwargs.pop("captured_by", None)

        previous_state = None
        if create_snapshot and self.pk:
            previous = type(self).objects.get(pk=self.pk)
            previous_state = {field: getattr(previous, field) for field in self.TRACKED_FIELDS}

        super().save(*args, **kwargs)

        if not create_snapshot:
            return

        current_state = {field: getattr(self, field) for field in self.TRACKED_FIELDS}
        latest_snapshot = self.snapshots.order_by('-created_at').first()
        latest_state = None
        if latest_snapshot:
            latest_state = {
                "headline": latest_snapshot.headline,
                "description": latest_snapshot.description,
                "price": latest_snapshot.price,
                "currency_id": latest_snapshot.currency_id,
                "features": latest_snapshot.features,
                "media_assets": latest_snapshot.media_assets,
                "effort_type": latest_snapshot.effort_type,
                "campaign_start": latest_snapshot.campaign_start,
                "campaign_end": latest_snapshot.campaign_end,
                "marketing_notes": latest_snapshot.marketing_notes,
            }
        if previous_state is None and latest_state:
            previous_state = latest_state

        if previous_state == current_state:
            return

        self.create_snapshot(
            captured_by=captured_by,
            performance_metrics=performance_metrics or {},
        )

    def create_snapshot(self, *, captured_by=None, performance_metrics=None):
        self.snapshots.create(
            headline=self.headline,
            description=self.description,
            price=self.price,
            currency=self.currency,
            features=deepcopy(self.features),
            media_assets=deepcopy(self.media_assets),
            effort_type=self.effort_type,
            campaign_start=self.campaign_start,
            campaign_end=self.campaign_end,
            marketing_notes=self.marketing_notes,
            performance_metrics=performance_metrics or {},
            captured_by=captured_by,
        )


class ListingSnapshot(TimeStampedModel):
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="snapshots",
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
        'Currency',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='listing_snapshots',
    )
    features = models.JSONField(blank=True, default=list)
    media_assets = models.JSONField(blank=True, default=list)
    effort_type = models.CharField(
        max_length=20,
        choices=Listing.EffortType.choices,
        default=Listing.EffortType.GENERAL,
    )
    campaign_start = models.DateField(null=True, blank=True)
    campaign_end = models.DateField(null=True, blank=True)
    marketing_notes = models.TextField(blank=True)
    performance_metrics = models.JSONField(blank=True, default=dict, help_text="Arbitrary metrics captured for this marketing iteration.")
    captured_by = models.ForeignKey(
        'Agent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_snapshots',
    )

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        timestamp = self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "snapshot"
        return f"Snapshot {timestamp} for {self.listing}"


class OpportunityOperation(TimeStampedModel):
    class Event(models.TextChoices):
        OFFER_RECEIVED = "offer_received", "Offer received"
        OFFER_REINFORCEMENT = "offer_reinforcement", "Offer reinforcement"
        DEAL_CLOSED = "deal_closed", "Deal closed"
        NEGOTIATION_FAILED = "negotiation_failed", "Negotiation failed"

    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="operations",
    )
    event = models.CharField(max_length=40, choices=Event.choices)
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
        'Currency',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='opportunity_operations',
    )
    occurred_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.get_event_display()} for {self.opportunity}"
