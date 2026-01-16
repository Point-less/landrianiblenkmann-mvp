from __future__ import annotations

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django_fsm import FSMField, transition

from core.models import Agent, Contact, Currency, Property
from opportunities.models import ProviderOpportunity, SeekerOpportunity
from utils.mixins import FSMTrackingMixin, TimeStampedMixin

def _default_feature_map() -> dict:
    return {}


class ProviderIntention(TimeStampedMixin, FSMTrackingMixin):
    """Represents a property owner’s desire to work with the agency prior to a contract."""

    class State(models.TextChoices):
        ASSESSING = "assessing", "Assessing"
        VALUATED = "valuated", "Valuated"
        CONVERTED = "converted", "Converted"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class WithdrawReason(models.TextChoices):
        LACK_OF_COMMITMENT = "lack_commitment", "Not truly committed"
        CANNOT_SELL = "cannot_sell", "Unable to sell (documentation/legal)"

    owner = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="provider_intentions",
    )
    agent = models.ForeignKey(
        Agent,
        on_delete=models.PROTECT,
        related_name="provider_intentions",
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="provider_intentions",
    )
    operation_type = models.ForeignKey(
        "opportunities.OperationType",
        on_delete=models.PROTECT,
        related_name="provider_intentions",
    )
    state = FSMField(
        max_length=32,
        choices=State.choices,
        default=State.ASSESSING,
        protected=False,
    )
    contract_signed_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    valuation = models.ForeignKey(
        "Valuation",
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
        verbose_name = "provider intention"
        verbose_name_plural = "provider intentions"

    def __str__(self) -> str:
        return f"Intention for {self.property} by {self.owner}"

    def clean(self):
        super().clean()
        if self.state == self.State.WITHDRAWN and not self.withdraw_reason:
            raise ValidationError({"withdraw_reason": "Please capture a withdraw reason."})

    @transition(field="state", source=State.ASSESSING, target=State.VALUATED)
    def deliver_valuation(
        self,
        *,
        currency: Currency,
        test_value,
        close_value,
        valuation_date=None,
        notes: str | None = None,
    ) -> None:
        if currency is None:
            raise ValidationError("Currency is required for a valuation.")
        valuation = Valuation.objects.create(
            provider_intention=self,
            agent=self.agent,
            currency=currency,
            delivered_at=timezone.now(),
            valuation_date=valuation_date or timezone.now().date(),
            test_value=test_value,
            close_value=close_value,
            notes=notes or "",
        )
        self.valuation = valuation

    @transition(field="state", source=State.VALUATED, target=State.CONVERTED)
    def mark_converted(self, *, opportunity: "ProviderOpportunity", signed_on=None) -> None:
        if opportunity is None:
            raise ValidationError("An opportunity instance is required when converting an intention.")
        # Preserve contract signature date for auditability even without an intermediate state.
        if not self.contract_signed_on:
            self.contract_signed_on = signed_on or timezone.now().date()
        self.converted_at = timezone.now()

    def can_withdraw(self) -> bool:
        return self.state not in {self.State.CONVERTED, self.State.WITHDRAWN}

    @transition(field="state", source="*", target=State.WITHDRAWN, conditions=[can_withdraw])
    def withdraw(self, *, reason: "ProviderIntention.WithdrawReason", notes: str | None = None) -> None:
        if self.state == self.State.CONVERTED:
            raise ValidationError("Converted intentions cannot be withdrawn.")
        if reason not in self.WithdrawReason.values:
            raise ValidationError({"withdraw_reason": "Invalid withdraw reason."})
        self.withdraw_reason = reason
        if notes:
            self.notes = (self.notes or "") + f"\nWithdrawn: {notes}"

    def is_promotable(self) -> bool:
        if self.state != self.State.VALUATED:
            return False
        return not _has_provider_opportunity(self)


class SeekerIntention(TimeStampedMixin, FSMTrackingMixin):
    """Captures buyer-side interest prior to signing a representation agreement."""

    class State(models.TextChoices):
        QUALIFYING = "qualifying", "Qualifying"
        CONVERTED = "converted", "Converted"
        ABANDONED = "abandoned", "Abandoned"

    contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="seeker_intentions",
    )
    agent = models.ForeignKey(
        Agent,
        on_delete=models.PROTECT,
        related_name="seeker_intentions",
    )
    operation_type = models.ForeignKey(
        "opportunities.OperationType",
        on_delete=models.PROTECT,
        related_name="seeker_intentions",
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

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "seeker intention"
        verbose_name_plural = "seeker intentions"

    def __str__(self) -> str:
        return f"Seeker intent for {self.contact}"

    def clean(self):
        super().clean()
        if self.budget_min and self.budget_max and self.budget_min > self.budget_max:
            raise ValidationError({"budget_max": "Max budget cannot be lower than min budget."})
        if _has_seeker_opportunity(self) and self.state != self.State.CONVERTED:
            raise ValidationError({
                "seeker_opportunity": "Converted intentions should own a seeker opportunity only once converted.",
            })

    @transition(field="state", source=State.QUALIFYING, target=State.CONVERTED)
    def mark_converted(self, *, opportunity: "SeekerOpportunity") -> None:
        if opportunity is None:
            raise ValidationError("An opportunity is required when converting a seeker intention.")

    @transition(field="state", source=State.QUALIFYING, target=State.ABANDONED)
    def abandon(self, reason: str | None = None) -> None:
        if reason:
            self.notes = (self.notes or "") + f"\nAbandoned: {reason}"

    def can_create_opportunity(self) -> bool:
        return self.state == self.State.QUALIFYING


class Valuation(TimeStampedMixin):
    provider_intention = models.ForeignKey(
        ProviderIntention,
        on_delete=models.CASCADE,
        related_name="valuations",
    )
    agent = models.ForeignKey(
        Agent,
        on_delete=models.PROTECT,
        related_name="valuations",
    )
    test_value = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    close_value = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="valuations",
    )
    delivered_at = models.DateTimeField(default=timezone.now)
    valuation_date = models.DateField(null=True, blank=True, help_text="Date the valuation was issued.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-delivered_at", "-created_at")
        verbose_name = "valuation"
        verbose_name_plural = "valuations"

    def __str__(self) -> str:
        return f"Valuation {self.test_value}/{self.close_value} {self.currency} for {self.provider_intention}"


__all__ = [
    "ProviderIntention",
    "SeekerIntention",
    "Valuation",
]
def _has_provider_opportunity(intention) -> bool:
    try:
        intention.provider_opportunity  # type: ignore[attr-defined]
    except ObjectDoesNotExist:
        return False
    return True


def _has_seeker_opportunity(intention) -> bool:
    try:
        intention.seeker_opportunity  # type: ignore[attr-defined]
    except ObjectDoesNotExist:
        return False
    return True
