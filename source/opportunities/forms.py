"""Forms for opportunity and operation workflows."""

from __future__ import annotations

from django import forms
from django.conf import settings
from decimal import Decimal

from opportunities.models import (
    MarketingPackage,
    OperationAgreement,
    ValidationAdditionalDocument,
    ValidationDocument,
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
    initial_offered_amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=True)

    class Meta:
        model = OperationAgreement
        fields = [
            "provider_opportunity",
            "seeker_opportunity",
            "initial_offered_amount",
        ]

    def __init__(self, *args, actor=None, choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        seeker_id = None
        if self.is_bound:
            try:
                seeker_id = int(self.data.get("seeker_opportunity"))
            except (TypeError, ValueError):
                seeker_id = None

        data = choices or S.opportunities.OperationAgreementChoicesQuery(actor=actor, seeker_id=seeker_id)
        self.fields["seeker_opportunity"].queryset = data["seeker_qs"]
        self.fields["provider_opportunity"].queryset = data["provider_qs"]


class CancelOperationAgreementForm(HTML5FormMixin, forms.Form):
    reason = forms.CharField(required=True, widget=forms.Textarea)


class SignOperationAgreementForm(HTML5FormMixin, forms.ModelForm):
    # Additional fields required for automatic Operation creation
    signed_document = forms.FileField(required=True)
    reserve_amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=True)
    reserve_deadline = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}))
    currency = forms.ModelChoiceField(queryset=None)

    class Meta:
        model = OperationAgreement
        fields = ["notes"]
        widgets = {
            "notes": forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, currency_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = currency_queryset if currency_queryset is not None else S.core.CurrenciesQuery()
        self.fields["currency"].queryset = qs

class ValidationDocumentUploadForm(HTML5FormMixin, forms.ModelForm):
    document_type = forms.ModelChoiceField(queryset=None, widget=forms.Select())

    class Meta:
        model = ValidationDocument
        fields = ["document_type", "observations", "document"]
        widgets = {
            "observations": forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, validation=None, document_types_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["observations"].required = False
        allowed_qs = document_types_queryset if document_types_queryset is not None else S.opportunities.AllowedValidationDocumentTypesQuery(validation=validation)
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

    def __init__(self, *args, currency_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = currency_queryset if currency_queryset is not None else S.core.CurrenciesQuery()
        self.fields["currency"].queryset = qs


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
