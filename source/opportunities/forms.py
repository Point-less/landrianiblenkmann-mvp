"""Forms for opportunity and operation workflows."""

from __future__ import annotations

from django import forms

from core.models import Agent, Currency
from opportunities.models import (
    MarketingPackage,
    Operation,
    ProviderOpportunity,
    SeekerOpportunity,
    Validation,
    ValidationDocument,
)
from opportunities.services import (
    AvailableProviderOpportunitiesForOperationsQuery,
    AvailableSeekerOpportunitiesForOperationsQuery,
)


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

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["provider_opportunity"].queryset = (
            AvailableProviderOpportunitiesForOperationsQuery.call(actor=actor)
        )
        self.fields["seeker_opportunity"].queryset = (
            AvailableSeekerOpportunitiesForOperationsQuery.call(actor=actor)
        )
        self.fields["currency"].queryset = Currency.objects.order_by("code")


class OperationLoseForm(HTML5FormMixin, forms.Form):
    lost_reason = forms.CharField(required=False, widget=forms.Textarea)


class ValidationDocumentUploadForm(HTML5FormMixin, forms.ModelForm):
    document_type = forms.ChoiceField(choices=[], widget=forms.Select())

    class Meta:
        model = ValidationDocument
        fields = ["document_type", "name", "document"]

    def __init__(self, *args, forced_document_type: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = Validation.required_document_choices(include_optional=True)
        self.fields["document_type"].choices = choices
        self.fields["name"].required = False
        if forced_document_type:
            self.fields["document_type"].initial = forced_document_type
            self.fields["document_type"].widget = forms.HiddenInput()
            self.fields["document_type"].choices = [(forced_document_type, forced_document_type)]


class ValidationDocumentReviewForm(HTML5FormMixin, forms.Form):
    action = forms.ChoiceField(choices=[("accept", "Accept"), ("reject", "Reject")])
    comment = forms.CharField(required=False, widget=forms.Textarea)


class MarketingPackageForm(HTML5FormMixin, forms.ModelForm):
    features = forms.JSONField(required=False, widget=forms.Textarea(attrs={'rows': 3}), help_text="JSON list or object.")
    media_assets = forms.JSONField(required=False, widget=forms.Textarea(attrs={'rows': 3}), help_text="JSON list of asset URLs.")

    class Meta:
        model = MarketingPackage
        fields = [
            "headline",
            "description",
            "price",
            "currency",
            "features",
            "media_assets",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["currency"].queryset = Currency.objects.order_by("code")


__all__ = [
    "ValidationPresentForm",
    "ValidationRejectForm",
    "SeekerOpportunityCreateForm",
    "OperationForm",
    "OperationLoseForm",
    "ValidationDocumentUploadForm",
    "ValidationDocumentReviewForm",
    "MarketingPackageForm",
]
