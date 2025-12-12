"""Forms for core domain objects."""

from __future__ import annotations

from django import forms
from decimal import Decimal

from core.models import Agent, Contact, Property


class TypedFormMixin:
    """Apply semantic HTML5 widgets based on field types."""

    def _setup_field_widgets(self):
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
            elif isinstance(field, forms.EmailField):
                field.widget = forms.EmailInput()
            elif isinstance(field, forms.CharField) and 'phone' in name:
                field.widget = forms.TextInput(attrs={'type': 'tel'})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_field_widgets()


class AgentForm(TypedFormMixin, forms.ModelForm):
    commission_split = forms.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=0,
        max_value=100,
        label="Agent split percentage",
        help_text="Percentage of commission allocated to the agent (e.g., 50 for 50%).",
    )

    class Meta:
        model = Agent
        fields = ["first_name", "last_name", "email", "phone_number", "commission_split"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Represent commission split as percentage for the form.
        if self.instance and self.instance.pk and "commission_split" in self.fields:
            if self.instance.commission_split is not None:
                self.initial["commission_split"] = self.instance.commission_split * 100

    def clean_commission_split(self):
        value = self.cleaned_data.get("commission_split")
        if value is None:
            return value
        return Decimal(value) / Decimal("100")


class AgentEditForm(AgentForm):
    pass

class ContactForm(TypedFormMixin, forms.ModelForm):
    agent = forms.ModelChoiceField(queryset=Agent.objects.all())

    class Meta:
        model = Contact
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "full_address",
            "tax_id",
            "tax_condition",
            "notes",
        ]

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        if actor and not getattr(actor, "is_superuser", False):
            from utils.authorization import get_role_profile

            actor_agent = get_role_profile(actor, "agent")
            if actor_agent:
                self.fields["agent"].queryset = Agent.objects.filter(pk=actor_agent.pk)
                self.fields["agent"].initial = actor_agent


class PropertyForm(TypedFormMixin, forms.ModelForm):
    class Meta:
        model = Property
        fields = ["name", "full_address"]


class ContactEditForm(TypedFormMixin, forms.ModelForm):
    class Meta:
        model = Contact
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "full_address",
            "tax_id",
            "tax_condition",
            "notes",
        ]


class PropertyEditForm(TypedFormMixin, forms.ModelForm):
    class Meta:
        model = Property
        fields = ["name", "full_address"]


class ConfirmationForm(forms.Form):
    """Simple empty form used for confirmation-only actions."""


__all__ = [
    "AgentForm",
    "AgentEditForm",
    "ContactForm",
    "ContactEditForm",
    "PropertyForm",
    "PropertyEditForm",
    "ConfirmationForm",
]
