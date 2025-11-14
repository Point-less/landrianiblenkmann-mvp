from __future__ import annotations

from builtins import property as builtin_property

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django_fsm import FSMField, transition

from core.models import Agent, Currency
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

    title = models.CharField(max_length=255)
    source_intention = models.OneToOneField(
        "intentions.SaleProviderIntention",
        on_delete=models.PROTECT,
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
        return self.title

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

    title = models.CharField(max_length=255)
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
        return self.title

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


class Validation(TimeStampedMixin, FSMLoggableMixin):
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
]
