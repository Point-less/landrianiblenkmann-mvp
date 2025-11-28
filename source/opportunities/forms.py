"""Forms for opportunity and operation workflows."""

from __future__ import annotations

from django import forms
from django.db import models

from core.models import Agent, Currency
from opportunities.models import (
    MarketingPackage,
    Operation,
    ProviderOpportunity,
    SeekerOpportunity,
    Validation,
    ValidationDocument,
    ValidationDocumentType,
)
from utils.services import S


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
        self.fields["provider_opportunity"].queryset = S.opportunities.AvailableProviderOpportunitiesForOperationsQuery(actor=actor)
        self.fields["seeker_opportunity"].queryset = S.opportunities.AvailableSeekerOpportunitiesForOperationsQuery(actor=actor)
        self.fields["currency"].queryset = Currency.objects.order_by("code")


class OperationLoseForm(HTML5FormMixin, forms.Form):
    lost_reason = forms.CharField(required=False, widget=forms.Textarea)


class ValidationDocumentUploadForm(HTML5FormMixin, forms.ModelForm):
    document_type = forms.ModelChoiceField(queryset=ValidationDocumentType.objects.none(), widget=forms.Select())

    class Meta:
        model = ValidationDocument
        fields = ["document_type", "observations", "document"]
        widgets = {
            "observations": forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, forced_document_type: str | None = None, validation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["observations"].required = False
        op_type = validation.opportunity.source_intention.operation_type if validation else None
        required_qs = validation.required_document_types() if validation else ValidationDocumentType.objects.filter(required=True)
        optional_qs = ValidationDocumentType.objects.filter(required=False)
        if op_type:
            optional_qs = optional_qs.filter(models.Q(operation_type__isnull=True) | models.Q(operation_type=op_type))
            required_qs = required_qs.filter(models.Q(operation_type__isnull=True) | models.Q(operation_type=op_type))
        allowed_qs = (required_qs | optional_qs).distinct()
        self.fields["document_type"].queryset = allowed_qs
        if forced_document_type:
            forced_obj = None
            if isinstance(forced_document_type, ValidationDocumentType):
                forced_obj = forced_document_type
            else:
                lookups = models.Q(code=forced_document_type)
                # Only attempt PK lookup when the value looks numeric to avoid ValueError.
                if str(forced_document_type).isdigit():
                    lookups |= models.Q(pk=forced_document_type)
                forced_obj = allowed_qs.filter(lookups).first()
            if forced_obj:
                self.fields["document_type"].initial = forced_obj
                self.fields["document_type"].widget = forms.HiddenInput()
                self.fields["document_type"].queryset = ValidationDocumentType.objects.filter(pk=forced_obj.pk)


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
