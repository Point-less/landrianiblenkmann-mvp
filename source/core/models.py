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





class ListingQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class Listing(TimeStampedModel):
    class EffortType(models.TextChoices):
        GENERAL = "general", "General"
        DIGITAL = "digital", "Digital"
        EVENTS = "events", "Events"
        PRINT = "print", "Print"
        OTHER = "other", "Other"

    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="listings",
    )
    version = models.PositiveIntegerField(default=1, editable=False)
    is_active = models.BooleanField(default=True)
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

    objects = ListingQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        unique_together = ("opportunity", "version")

    def __str__(self) -> str:
        suffix = f" v{self.version}" if self.version else ""
        base = self.headline or f"Marketing package for {self.opportunity}"
        return f"{base}{suffix}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if self.pk:
            if update_fields is None:
                raise ValueError('Listings are immutable; use Listing.create_revision to replace them.')
            allowed_updates = {'is_active', 'updated_at'}
            if not set(update_fields).issubset(allowed_updates):
                raise ValueError('Listings are immutable; use Listing.create_revision to replace them.')
        super().save(*args, **kwargs)

    @classmethod
    def editable_field_names(cls):
        excluded = {"id", "opportunity", "version", "is_active", "created_at", "updated_at"}
        return [
            field.name
            for field in cls._meta.get_fields()
            if isinstance(field, models.Field)
            and not field.auto_created
            and field.name not in excluded
        ]

    @classmethod
    def create_revision(cls, listing, **changes):
        from django.db import transaction
        from django.db.models import Max

        editable = cls.editable_field_names()
        base_payload = {name: getattr(listing, name) for name in editable}
        base_payload.update(changes)
        with transaction.atomic():
            listing.is_active = False
            listing.save(update_fields=["is_active", "updated_at"])
            max_version = (
                cls.objects.filter(opportunity=listing.opportunity)
                .aggregate(max_v=Max("version"))
                .get("max_v")
                or 0
            )
            new_listing = cls.objects.create(
                opportunity=listing.opportunity,
                version=max_version + 1,
                is_active=True,
                **base_payload,
            )
        return new_listing

    def clone(self, **overrides):
        return type(self).create_revision(self, **overrides)


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
