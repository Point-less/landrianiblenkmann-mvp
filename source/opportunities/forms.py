"""Forms for opportunity and operation workflows."""

from __future__ import annotations

from django import forms

from core.models import Agent, Currency
from opportunities.models import Operation, ProviderOpportunity, SeekerOpportunity, ValidationDocument


class HTML5FormMixin:
    def _apply_widgets(self):
        for field in self.fields.values():
            if isinstance(field, forms.DateField):
                field.widget = forms.DateInput(attrs={'type': 'date'})
            elif isinstance(field, forms.DecimalField):
                step = '1'
                if field.decimal_places:
                    step = '0.' + '0' * (field.decimal_places - 1) + '1'
                field.widget = forms.NumberInput(attrs={'step': step})
            elif isinstance(field, forms.IntegerField):
                field.widget = forms.NumberInput()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_widgets()


class ValidationPresentForm(HTML5FormMixin, forms.Form):
    reviewer = forms.ModelChoiceField(queryset=Agent.objects.all())


class ValidationRejectForm(HTML5FormMixin, forms.Form):
    notes = forms.CharField(required=False, widget=forms.Textarea)


class SeekerOpportunityCreateForm(HTML5FormMixin, forms.Form):
    notes = forms.CharField(required=False, widget=forms.Textarea)


class OperationForm(HTML5FormMixin, forms.ModelForm):
    class Meta:
        model = Operation
        fields = [
            "provider_opportunity",
            "seeker_opportunity",
            "offered_amount",
            "reserve_amount",
            "reinforcement_amount",
            "currency",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["provider_opportunity"].queryset = ProviderOpportunity.objects.order_by("-created_at")
        self.fields["seeker_opportunity"].queryset = SeekerOpportunity.objects.order_by("-created_at")
        self.fields["currency"].queryset = Currency.objects.order_by("code")


class OperationLoseForm(HTML5FormMixin, forms.Form):
    lost_reason = forms.CharField(required=False, widget=forms.Textarea)


class ValidationDocumentUploadForm(HTML5FormMixin, forms.ModelForm):
    class Meta:
        model = ValidationDocument
        fields = ["name", "document"]


class ValidationDocumentReviewForm(HTML5FormMixin, forms.Form):
    action = forms.ChoiceField(choices=[("accept", "Accept"), ("reject", "Reject")])
    comment = forms.CharField(required=False, widget=forms.Textarea)


__all__ = [
    "ValidationPresentForm",
    "ValidationRejectForm",
    "SeekerOpportunityCreateForm",
    "OperationForm",
    "OperationLoseForm",
    "ValidationDocumentUploadForm",
    "ValidationDocumentReviewForm",
]
