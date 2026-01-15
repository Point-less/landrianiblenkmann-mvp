"""Forms supporting intention workflows."""

from __future__ import annotations

from django import forms
from django.conf import settings
from decimal import Decimal
from datetime import date

from intentions.models import ProviderIntention, SeekerIntention
from django.urls import reverse
from utils.services import S


class HTML5WidgetMixin:
    def _apply_html5_widgets(self):
        for name, field in self.fields.items():
            if isinstance(field, forms.DateField):
                field.widget = forms.DateInput(attrs={'type': 'date'})
            elif isinstance(field, forms.DateTimeField):
                field.widget = forms.DateTimeInput(attrs={'type': 'datetime-local'})
            elif isinstance(field, forms.DecimalField):
                step = '1'
                if field.decimal_places:
                    step = '0.' + '0' * (field.decimal_places - 1) + '1'
                field.widget = forms.NumberInput(attrs={'step': step})
            elif isinstance(field, forms.IntegerField):
                field.widget = forms.NumberInput()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_html5_widgets()


class ProviderIntentionForm(HTML5WidgetMixin, forms.ModelForm):
    class Meta:
        model = ProviderIntention
        fields = ["owner", "agent", "property", "operation_type", "notes"]

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        data = S.intentions.PrepareProviderIntentionChoicesService(actor=actor)
        self.fields["operation_type"].queryset = data["operation_type_qs"]
        self.fields["owner"].queryset = data["owner_qs"]
        self.fields["agent"].queryset = data["agent_qs"]
        if data.get("actor_agent"):
            self.fields["agent"].initial = data["actor_agent"]

    def clean_agent(self):
        agent = self.cleaned_data.get("agent")
        if agent is None:
            raise forms.ValidationError("You must select an agent.")
        if not self.fields["agent"].queryset.filter(pk=agent.pk).exists():
            raise forms.ValidationError("Selected agent is not available.")
        return agent


class DeliverValuationForm(HTML5WidgetMixin, forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2)
    currency = forms.ModelChoiceField(queryset=None)
    notes = forms.CharField(required=False, widget=forms.Textarea)
    valuation_date = forms.DateField(required=False, initial=date.today)
    test_value = forms.DecimalField(max_digits=12, decimal_places=2, label="Agent test value")
    close_value = forms.DecimalField(max_digits=12, decimal_places=2, label="Agent close value")

    def __init__(self, *args, currency_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = currency_queryset if currency_queryset is not None else []
        self.fields["currency"].queryset = queryset
class ProviderPromotionForm(HTML5WidgetMixin, forms.Form):
    listing_kind = forms.ChoiceField(
        choices=[
            ("exclusive", "Exclusive"),
            ("non_exclusive", "Non-exclusive"),
        ],
        label="Contract type",
    )
    contract_expires_on = forms.DateField(required=True, label="Contract end date")
    contract_effective_on = forms.DateField(required=True, label="Contract start date")
    valuation_test_value = forms.DecimalField(max_digits=12, decimal_places=2, label="Client test value")
    valuation_close_value = forms.DecimalField(max_digits=12, decimal_places=2, label="Client close value")
    gross_commission_pct = forms.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=0,
        max_value=100,
        label="Gross commission (%)",
        help_text="Percentage agreed with the client (e.g., 4 for 4%).",
    )
    tokkobroker_property = forms.ModelChoiceField(
        required=True,
        queryset=None,
        label="Tokkobroker property",
        help_text="Select the linked Tokkobroker listing to promote.",
    )
    notes = forms.CharField(required=False, widget=forms.Textarea, label="Notes")

    def __init__(self, *args, currency_queryset=None, tokkobroker_property_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        property_queryset = (
            tokkobroker_property_queryset if tokkobroker_property_queryset is not None else S.core.AvailableTokkobrokerPropertiesQuery()
        )
        self.fields["tokkobroker_property"].queryset = property_queryset
        self.fields["tokkobroker_property"].widget.attrs.update(
            {
                "class": "admin-autocomplete",
                "data-ajax--url": reverse("integration-tokko-properties-search"),
                "data-ajax--cache": "true",
                "data-placeholder": "Search Tokkobroker properties",
                "data-allow-clear": "true",
                "data-theme": "admin-autocomplete",
            }
        )
        # Pre-fill with default commission (%)
        default_pct = Decimal(getattr(settings, "DEFAULT_GROSS_COMMISSION_PCT", Decimal("0.04"))) * 100
        self.fields["gross_commission_pct"].initial = default_pct

    def clean_gross_commission_pct(self):
        value = self.cleaned_data.get("gross_commission_pct")
        if value is None:
            return value
        return Decimal(value) / Decimal("100")


class ProviderWithdrawForm(HTML5WidgetMixin, forms.Form):
    reason = forms.ChoiceField(choices=ProviderIntention.WithdrawReason.choices)
    notes = forms.CharField(required=False, widget=forms.Textarea)


class SeekerIntentionForm(HTML5WidgetMixin, forms.ModelForm):
    class Meta:
        model = SeekerIntention
        fields = [
            "contact",
            "agent",
            "operation_type",
            "budget_min",
            "budget_max",
            "currency",
            "desired_features",
            "notes",
        ]
        widgets = {
            "desired_features": forms.Textarea(attrs={'rows': 3, 'placeholder': 'JSON, e.g. {"bedrooms": 3}'}),
            "notes": forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        data = S.intentions.PrepareSeekerIntentionChoicesService(actor=actor)
        self.fields["operation_type"].queryset = data["operation_type_qs"]
        self.fields["contact"].queryset = data["contact_qs"]
        agent_qs = data["agent_qs"]
        self.fields["agent"].queryset = agent_qs
        actor_agent = data.get("actor_agent")
        if actor_agent:
            self.fields["agent"].initial = actor_agent

    def clean_agent(self):
        agent = self.cleaned_data.get("agent")
        if agent is None:
            raise forms.ValidationError("You must select an agent.")
        if not self.fields["agent"].queryset.filter(pk=agent.pk).exists():
            raise forms.ValidationError("Selected agent is not available.")
        return agent


class SeekerMandateForm(HTML5WidgetMixin, forms.Form):
    signed_on = forms.DateField(required=False)


class SeekerAbandonForm(HTML5WidgetMixin, forms.Form):
    reason = forms.CharField(required=False, widget=forms.Textarea)


__all__ = [
    "ProviderIntentionForm",
    "DeliverValuationForm",
    "ProviderPromotionForm",
    "ProviderWithdrawForm",
    "SeekerIntentionForm",
    "SeekerMandateForm",
    "SeekerAbandonForm",
]
