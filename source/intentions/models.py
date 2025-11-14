from __future__ import annotations

from typing import Optional

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django_fsm import FSMField, transition

from core.models import Agent, Contact, Currency, Property
from utils.mixins import FSMLoggableMixin, TimeStampedMixin

def _default_feature_map() -> dict:
    return {}


class SaleProviderIntention(TimeStampedMixin, FSMLoggableMixin):
    """Represents a property owner’s desire to work with the agency prior to a contract."""

    class State(models.TextChoices):
        ASSESSING = "assessing", "Assessing"
        VALUATED = "valuated", "Valuated"
        CONTRACT_NEGOTIATION = "contract_negotiation", "Contract Negotiation"
        CONVERTED = "converted", "Converted"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class WithdrawReason(models.TextChoices):
        LACK_OF_COMMITMENT = "lack_commitment", "Not truly committed"
        CANNOT_SELL = "cannot_sell", "Unable to sell (documentation/legal)"

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
    valuation = models.ForeignKey(
        "SaleValuation",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    converted_at = models.DateTimeField(null=True, blank=True)
    withdraw_reason = models.CharField(
        max_length=32,
        choices=WithdrawReason.choices,
        blank=True,
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "sale provider intention"
        verbose_name_plural = "sale provider intentions"

    def __str__(self) -> str:
        return f"Sale intent for {self.property} by {self.owner}"

    def clean(self):
        super().clean()
        if self.state == self.State.WITHDRAWN and not self.withdraw_reason:
            raise ValidationError({"withdraw_reason": "Please capture a withdraw reason."})

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
        self.valuation = valuation

    @transition(field="state", source=State.VALUATED, target=State.CONTRACT_NEGOTIATION)
    def start_contract_negotiation(self, signed_on=None) -> None:
        self.contract_signed_on = signed_on or timezone.now().date()

    @transition(field="state", source=State.CONTRACT_NEGOTIATION, target=State.CONVERTED)
    def mark_converted(self, *, opportunity: "ProviderOpportunity") -> None:
        if opportunity is None:
            raise ValidationError("An opportunity instance is required when converting an intention.")
        self.converted_at = timezone.now()

    def can_withdraw(self) -> bool:
        return self.state not in {self.State.CONVERTED, self.State.WITHDRAWN}

    @transition(field="state", source="*", target=State.WITHDRAWN, conditions=[can_withdraw])
    def withdraw(self, *, reason: "SaleProviderIntention.WithdrawReason", notes: str | None = None) -> None:
        if self.state == self.State.CONVERTED:
            raise ValidationError("Converted intentions cannot be withdrawn.")
        if reason not in self.WithdrawReason.values:
            raise ValidationError({"withdraw_reason": "Invalid withdraw reason."})
        self.withdraw_reason = reason
        if notes:
            self.documentation_notes = (self.documentation_notes or "") + f"\nWithdrawn: {notes}"

    def is_promotable(self) -> bool:
        return self.state == self.State.CONTRACT_NEGOTIATION and not hasattr(self, "provider_opportunity")


class SaleSeekerIntention(TimeStampedMixin, FSMLoggableMixin):
    """Captures buyer-side interest prior to signing a representation agreement."""

    class State(models.TextChoices):
        QUALIFYING = "qualifying", "Qualifying"
        ACTIVE = "active", "Active Search"
        MANDATED = "mandated", "Mandated"
        CONVERTED = "converted", "Converted"
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
        if hasattr(self, "seeker_opportunity") and self.state != self.State.CONVERTED:
            raise ValidationError({
                "seeker_opportunity": "Converted intentions should own a seeker opportunity only once converted.",
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
    def mark_converted(self, *, opportunity: "SeekerOpportunity") -> None:
        if opportunity is None:
            raise ValidationError("An opportunity is required when converting a seeker intention.")

    @transition(field="state", source=[State.QUALIFYING, State.ACTIVE], target=State.ABANDONED)
    def abandon(self, reason: str | None = None) -> None:
        if reason:
            self.notes = (self.notes or "") + f"\nAbandoned: {reason}"

    def can_create_opportunity(self) -> bool:
        return self.state == self.State.MANDATED and not hasattr(self, "seeker_opportunity")


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
