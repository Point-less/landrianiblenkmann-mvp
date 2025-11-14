"""Forms supporting intention workflows."""

from __future__ import annotations

from django import forms

from intentions.models import SaleProviderIntention, SaleSeekerIntention


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


class SaleProviderIntentionForm(HTML5WidgetMixin, forms.ModelForm):
    class Meta:
        model = SaleProviderIntention
        fields = ["owner", "agent", "property", "documentation_notes"]


class DeliverValuationForm(HTML5WidgetMixin, forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2)
    currency = forms.ModelChoiceField(queryset=None)
    notes = forms.CharField(required=False, widget=forms.Textarea)

    def __init__(self, *args, currency_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = currency_queryset if currency_queryset is not None else []
        self.fields["currency"].queryset = queryset


class ProviderContractForm(HTML5WidgetMixin, forms.Form):
    signed_on = forms.DateField(required=False, help_text="Defaults to today when omitted.")


class ProviderPromotionForm(HTML5WidgetMixin, forms.Form):
    opportunity_notes = forms.CharField(required=False, widget=forms.Textarea)
    headline = forms.CharField(required=False)
    description = forms.CharField(required=False, widget=forms.Textarea)
    price = forms.DecimalField(required=False, max_digits=12, decimal_places=2)
    currency = forms.ModelChoiceField(required=False, queryset=None)

    def __init__(self, *args, currency_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = currency_queryset if currency_queryset is not None else []
        self.fields["currency"].queryset = queryset


class ProviderWithdrawForm(HTML5WidgetMixin, forms.Form):
    reason = forms.ChoiceField(choices=SaleProviderIntention.WithdrawReason.choices)
    notes = forms.CharField(required=False, widget=forms.Textarea)


class SaleSeekerIntentionForm(HTML5WidgetMixin, forms.ModelForm):
    class Meta:
        model = SaleSeekerIntention
        fields = [
            "contact",
            "agent",
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


class SeekerMandateForm(HTML5WidgetMixin, forms.Form):
    signed_on = forms.DateField(required=False)


class SeekerAbandonForm(HTML5WidgetMixin, forms.Form):
    reason = forms.CharField(required=False, widget=forms.Textarea)


__all__ = [
    "SaleProviderIntentionForm",
    "DeliverValuationForm",
    "ProviderContractForm",
    "ProviderPromotionForm",
    "ProviderWithdrawForm",
    "SaleSeekerIntentionForm",
    "SeekerMandateForm",
    "SeekerAbandonForm",
]
