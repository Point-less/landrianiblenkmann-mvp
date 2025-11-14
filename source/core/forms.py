"""Forms for core domain objects."""

from __future__ import annotations

from django import forms

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
    class Meta:
        model = Agent
        fields = ["first_name", "last_name", "email", "phone_number"]


class AgentEditForm(AgentForm):
    pass

class ContactForm(TypedFormMixin, forms.ModelForm):
    agent = forms.ModelChoiceField(queryset=Agent.objects.all())

    class Meta:
        model = Contact
        fields = ["first_name", "last_name", "email", "phone_number", "notes"]


class PropertyForm(TypedFormMixin, forms.ModelForm):
    class Meta:
        model = Property
        fields = ["name", "reference_code"]


class ContactEditForm(TypedFormMixin, forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["first_name", "last_name", "email", "phone_number", "notes"]


class PropertyEditForm(TypedFormMixin, forms.ModelForm):
    class Meta:
        model = Property
        fields = ["name", "reference_code"]


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
