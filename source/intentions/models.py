from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django_fsm import FSMField, transition

from core.models import Agent, Contact, Currency, Property
from utils.mixins import FSMLoggableMixin, TimeStampedMixin

if TYPE_CHECKING:  # pragma: no cover - typing helper only
    from opportunities.models import Opportunity


def _default_feature_map() -> dict:
    return {}


class SaleProviderIntention(TimeStampedMixin, FSMLoggableMixin):
    """Represents a property owner’s desire to work with the agency prior to a contract."""

    class State(models.TextChoices):
        ASSESSING = "assessing", "Assessing"
        VALUATED = "valuated", "Valuated"
        CONTRACT_NEGOTIATION = "contract_negotiation", "Contract Negotiation"
        DOCS_APPROVED = "docs_approved", "Documents Approved"
        CONVERTED = "converted", "Converted"
        WITHDRAWN = "withdrawn", "Withdrawn"

    owner = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="sale_provider_intentions",
    )
    agent = models.ForeignKey(
        Agent,
        on_delete=models.PROTECT,
        related_name="sale_provider_intentions",
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="sale_provider_intentions",
    )
    state = FSMField(
        max_length=32,
        choices=State.choices,
        default=State.ASSESSING,
        protected=False,
    )
    contract_signed_on = models.DateField(null=True, blank=True)
    documentation_notes = models.TextField(blank=True)
    latest_valuation = models.ForeignKey(
        "SaleValuation",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    converted_opportunity = models.ForeignKey(
        "opportunities.Opportunity",
        on_delete=models.SET_NULL,
        related_name="source_sale_provider_intentions",
        null=True,
        blank=True,
    )
    converted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "sale provider intention"
        verbose_name_plural = "sale provider intentions"

    def __str__(self) -> str:
        return f"Sale intent for {self.property} by {self.owner}"

    def clean(self):
        super().clean()
        if self.converted_opportunity and self.state != self.State.CONVERTED:
            raise ValidationError({
                "converted_opportunity": "Converted opportunity should only exist once the intention is converted.",
            })

    @transition(field="state", source=State.ASSESSING, target=State.VALUATED)
    def deliver_valuation(self, *, amount, currency: Currency, notes: str | None = None) -> None:
        if amount is None or currency is None:
            raise ValidationError("Amount and currency are required for a valuation.")
        valuation = SaleValuation.objects.create(
            provider_intention=self,
            agent=self.agent,
            amount=amount,
            currency=currency,
            delivered_at=timezone.now(),
            notes=notes or "",
        )
        self.latest_valuation = valuation

    @transition(field="state", source=State.VALUATED, target=State.CONTRACT_NEGOTIATION)
    def start_contract_negotiation(self, signed_on=None) -> None:
        self.contract_signed_on = signed_on or timezone.now().date()

    @transition(field="state", source=State.CONTRACT_NEGOTIATION, target=State.DOCS_APPROVED)
    def approve_documents(self, notes: str | None = None) -> None:
        if notes:
            self.documentation_notes = notes
        if not self.documentation_notes:
            raise ValidationError("Provide documentation notes before approving.")

    @transition(field="state", source=State.DOCS_APPROVED, target=State.CONVERTED)
    def mark_converted(self, *, opportunity: "Opportunity") -> None:
        if opportunity is None:
            raise ValidationError("An opportunity instance is required when converting an intention.")
        self.converted_opportunity = opportunity
        self.converted_at = timezone.now()

    @transition(field="state", source="*", target=State.WITHDRAWN)
    def withdraw(self, reason: str | None = None) -> None:
        if self.state == self.State.CONVERTED:
            raise ValidationError("Converted intentions cannot be withdrawn.")
        if reason:
            self.documentation_notes = (self.documentation_notes or "") + f"\nWithdrawn: {reason}"

    def is_promotable(self) -> bool:
        return self.state == self.State.DOCS_APPROVED and self.converted_opportunity_id is None


class SaleSeekerIntention(TimeStampedMixin, FSMLoggableMixin):
    """Captures buyer-side interest prior to signing a representation agreement."""

    class State(models.TextChoices):
        QUALIFYING = "qualifying", "Qualifying"
        ACTIVE = "active", "Active Search"
        MANDATED = "mandated", "Mandated"
        CONVERTED = "converted", "Converted"
        FULFILLED = "fulfilled", "Fulfilled"
        ABANDONED = "abandoned", "Abandoned"

    contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="sale_seeker_intentions",
    )
    agent = models.ForeignKey(
        Agent,
        on_delete=models.PROTECT,
        related_name="sale_seeker_intentions",
    )
    state = FSMField(
        max_length=32,
        choices=State.choices,
        default=State.QUALIFYING,
        protected=False,
    )
    budget_min = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    budget_max = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    desired_features = models.JSONField(default=_default_feature_map, blank=True)
    notes = models.TextField(blank=True)
    search_activated_at = models.DateTimeField(null=True, blank=True)
    mandate_signed_on = models.DateField(null=True, blank=True)
    converted_opportunity = models.ForeignKey(
        "opportunities.Opportunity",
        on_delete=models.SET_NULL,
        related_name="source_sale_seeker_intentions",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "sale seeker intention"
        verbose_name_plural = "sale seeker intentions"

    def __str__(self) -> str:
        return f"Sale seeker intent for {self.contact}"

    def clean(self):
        super().clean()
        if self.budget_min and self.budget_max and self.budget_min > self.budget_max:
            raise ValidationError({"budget_max": "Max budget cannot be lower than min budget."})
        if self.converted_opportunity and self.state not in {self.State.CONVERTED, self.State.FULFILLED}:
            raise ValidationError({
                "converted_opportunity": "Converted opportunity should only exist for converted/fulfilled intentions.",
            })

    @transition(field="state", source=State.QUALIFYING, target=State.ACTIVE)
    def activate_search(self) -> None:
        if not self.budget_max or not self.currency:
            raise ValidationError("Budget range and currency required before activating search.")
        self.search_activated_at = timezone.now()

    @transition(field="state", source=State.ACTIVE, target=State.MANDATED)
    def sign_mandate(self, signed_on=None) -> None:
        self.mandate_signed_on = signed_on or timezone.now().date()

    @transition(field="state", source=State.MANDATED, target=State.CONVERTED)
    def mark_converted(self, *, opportunity: "Opportunity") -> None:
        if opportunity is None:
            raise ValidationError("An opportunity is required when converting a seeker intention.")
        self.converted_opportunity = opportunity

    @transition(field="state", source=State.CONVERTED, target=State.FULFILLED)
    def mark_fulfilled(self) -> None:
        if not self.converted_opportunity:
            raise ValidationError("Cannot mark fulfilled without a linked opportunity.")

    @transition(field="state", source=[State.QUALIFYING, State.ACTIVE], target=State.ABANDONED)
    def abandon(self, reason: str | None = None) -> None:
        if reason:
            self.notes = (self.notes or "") + f"\nAbandoned: {reason}"


class SaleValuation(TimeStampedMixin):
    provider_intention = models.ForeignKey(
        SaleProviderIntention,
        on_delete=models.CASCADE,
        related_name="valuations",
    )
    agent = models.ForeignKey(
        Agent,
        on_delete=models.PROTECT,
        related_name="sale_valuations",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="sale_valuations",
    )
    delivered_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-delivered_at", "-created_at")
        verbose_name = "sale valuation"
        verbose_name_plural = "sale valuations"

    def __str__(self) -> str:
        return f"Valuation {self.amount} {self.currency} for {self.provider_intention}"


__all__ = [
    "SaleProviderIntention",
    "SaleSeekerIntention",
    "SaleValuation",
]
