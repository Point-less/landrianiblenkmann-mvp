"""Forms for opportunity and operation workflows."""

from __future__ import annotations

from django import forms
from django.conf import settings
from decimal import Decimal
from django.db import models

from core.models import Agent, Currency
from opportunities.models import (
    MarketingPackage,
    Operation,
    OperationAgreement,
    ValidationAdditionalDocument,
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
    pass


class ValidationRejectForm(HTML5FormMixin, forms.Form):
    notes = forms.CharField(required=False, widget=forms.Textarea)


class SeekerOpportunityCreateForm(HTML5FormMixin, forms.Form):
    gross_commission_pct = forms.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=0,
        max_value=100,
        label="Gross commission (%)",
        help_text="Percentage agreed with the client (e.g., 3 for 3%).",
    )
    notes = forms.CharField(required=False, widget=forms.Textarea)

    def clean_gross_commission_pct(self):
        value = self.cleaned_data.get("gross_commission_pct")
        if value is None:
            return value
        return Decimal(value) / Decimal("100")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        default_pct = Decimal(getattr(settings, "DEFAULT_GROSS_COMMISSION_PCT", Decimal("0.04"))) * 100
        self.fields["gross_commission_pct"].initial = default_pct


class OperationLoseForm(HTML5FormMixin, forms.Form):
    lost_reason = forms.CharField(required=False, widget=forms.Textarea)


class OperationReinforceForm(HTML5FormMixin, forms.Form):
    offered_amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    reinforcement_amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    declared_deed_value = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=True)


class OperationAgreementCreateForm(HTML5FormMixin, forms.ModelForm):
    class Meta:
        model = OperationAgreement
        fields = [
            "provider_opportunity",
            "seeker_opportunity",
        ]

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["provider_opportunity"].queryset = S.opportunities.AvailableProviderOpportunitiesForOperationsQuery(actor=actor)
        self.fields["seeker_opportunity"].queryset = S.opportunities.AvailableSeekerOpportunitiesForOperationsQuery(actor=actor)


class CancelOperationAgreementForm(HTML5FormMixin, forms.Form):
    reason = forms.CharField(required=True, widget=forms.Textarea)


class SignOperationAgreementForm(HTML5FormMixin, forms.ModelForm):
    # Additional fields required for automatic Operation creation
    signed_document = forms.FileField(required=True)
    initial_offered_amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=True)
    reserve_amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=True)
    reserve_deadline = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}))
    currency = forms.ModelChoiceField(queryset=Currency.objects.all())

    class Meta:
        model = OperationAgreement
        fields = ["notes"]
        widgets = {
            "notes": forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["currency"].queryset = Currency.objects.order_by("code")

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
        if op_type:
            required_qs = required_qs.filter(models.Q(operation_type__isnull=True) | models.Q(operation_type=op_type))
        allowed_qs = required_qs.distinct()
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
                if not self.is_bound:
                    # Hide only on first render when the type was forced by the caller
                    self.fields["document_type"].widget = forms.HiddenInput()
                    self.fields["document_type"].queryset = ValidationDocumentType.objects.filter(pk=forced_obj.pk)
                else:
                    # On re-render (e.g., after validation errors) keep the selector visible to let users change it
                    self.fields["document_type"].queryset = allowed_qs


class ValidationDocumentReviewForm(HTML5FormMixin, forms.Form):
    action = forms.ChoiceField(choices=[("accept", "Accept"), ("reject", "Reject")])
    comment = forms.CharField(required=False, widget=forms.Textarea)


class ValidationAdditionalDocumentUploadForm(HTML5FormMixin, forms.ModelForm):
    class Meta:
        model = ValidationAdditionalDocument
        fields = ["observations", "document"]
        widgets = {
            "observations": forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["observations"].required = False


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
    "OperationLoseForm",
    "ValidationDocumentUploadForm",
    "ValidationDocumentReviewForm",
    "ValidationAdditionalDocumentUploadForm",
    "MarketingPackageForm",
    "CancelOperationAgreementForm",
    "SignOperationAgreementForm",
    "OperationAgreementCreateForm",
]
