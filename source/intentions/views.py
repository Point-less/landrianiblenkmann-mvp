from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic.edit import FormView

from core.mixins import PermissionedViewMixin
from intentions.forms import (
    DeliverValuationForm,
    ProviderPromotionForm,
    ProviderWithdrawForm,
    SaleProviderIntentionForm,
    SaleSeekerIntentionForm,
    SeekerAbandonForm,
)
from opportunities.forms import SeekerOpportunityCreateForm
from intentions.models import SaleProviderIntention, SaleSeekerIntention
from utils.services import S
from utils.authorization import (
    PROVIDER_INTENTION_CREATE,
    PROVIDER_INTENTION_VALUATE,
    PROVIDER_INTENTION_WITHDRAW,
    PROVIDER_INTENTION_PROMOTE,
    SEEKER_INTENTION_CREATE,
    SEEKER_INTENTION_ABANDON,
    SEEKER_OPPORTUNITY_CREATE,
)


class ProviderIntentionMixin:
    pk_url_kwarg = 'intention_id'

    def get_intention(self):
        return get_object_or_404(SaleProviderIntention, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['intention'] = self.get_intention()
        return context


class SeekerIntentionMixin:
    pk_url_kwarg = 'intention_id'

    def get_intention(self):
        return get_object_or_404(SaleSeekerIntention, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['intention'] = self.get_intention()
        return context


class ProviderIntentionCreateView(PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    form_class = SaleProviderIntentionForm
    success_message = 'Provider intention created.'
    form_title = 'New provider intention'
    form_description = 'Capture a seller lead before promoting to opportunity.'
    submit_label = 'Create intention'
    required_action = PROVIDER_INTENTION_CREATE

    def perform_action(self, form):
        S.intentions.CreateSaleProviderIntentionService(**form.cleaned_data)

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError as exc:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'provider-intentions'})


class DeliverValuationView(ProviderIntentionMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    form_class = DeliverValuationForm
    success_message = 'Valuation delivered.'
    form_title = 'Deliver valuation'
    form_description = 'Provide the valuation amount and currency to advance the seller.'
    submit_label = 'Deliver valuation'
    required_action = PROVIDER_INTENTION_VALUATE

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['currency_queryset'] = S.core.CurrenciesQuery(actor=self.request.user)
        return kwargs

    def perform_action(self, form):
        S.intentions.DeliverSaleValuationService(intention=self.get_intention(), **form.cleaned_data)

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'provider-intentions'})


class ProviderPromotionView(ProviderIntentionMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    form_class = ProviderPromotionForm
    success_message = 'Provider intention promoted to opportunity.'
    form_title = 'Promote to opportunity'
    form_description = 'Create a provider opportunity and initial marketing package.'
    submit_label = 'Promote'
    required_action = PROVIDER_INTENTION_PROMOTE

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tokkobroker_property_queryset'] = S.core.AvailableTokkobrokerPropertiesQuery(actor=self.request.user)
        valuation = self.get_intention().valuation
        if valuation:
            kwargs.setdefault('initial', {})
            kwargs['initial'].update(
                valuation_test_value=valuation.test_value,
                valuation_close_value=valuation.close_value,
            )
        return kwargs

    def perform_action(self, form):
        data = form.cleaned_data
        S.intentions.PromoteSaleProviderIntentionService(
            intention=self.get_intention(),
            notes=data.get('notes') or None,
            marketing_package_data=None,
            tokkobroker_property=data.get('tokkobroker_property'),
            gross_commission_pct=data.get('gross_commission_pct'),
            listing_kind=data.get('listing_kind'),
            contract_expires_on=data.get('contract_expires_on'),
            contract_effective_on=data.get('contract_effective_on'),
            valuation_test_value=data.get('valuation_test_value'),
            valuation_close_value=data.get('valuation_close_value'),
        )

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError as exc:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'provider-opportunities'})


class ProviderWithdrawView(ProviderIntentionMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    form_class = ProviderWithdrawForm
    success_message = 'Provider intention withdrawn.'
    form_title = 'Withdraw provider intention'
    submit_label = 'Withdraw'
    required_action = PROVIDER_INTENTION_WITHDRAW

    def perform_action(self, form):
        S.intentions.WithdrawSaleProviderIntentionService(intention=self.get_intention(), **form.cleaned_data)

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'provider-intentions'})


class SeekerIntentionCreateView(PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    form_class = SaleSeekerIntentionForm
    success_message = 'Seeker intention registered.'
    form_title = 'New seeker intention'
    submit_label = 'Create intention'
    required_action = SEEKER_INTENTION_CREATE

    def perform_action(self, form):
        S.intentions.CreateSaleSeekerIntentionService(**form.cleaned_data)

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'seeker-intentions'})


class SeekerOpportunityCreateView(SeekerIntentionMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    form_class = SeekerOpportunityCreateForm
    success_message = 'Seeker opportunity created.'
    form_title = 'Create seeker opportunity'
    submit_label = 'Create opportunity'
    required_action = SEEKER_OPPORTUNITY_CREATE

    def perform_action(self, form):
        S.opportunities.CreateSeekerOpportunityService(intention=self.get_intention(), **form.cleaned_data)

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'seeker-opportunities'})


class SeekerAbandonView(SeekerIntentionMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    form_class = SeekerAbandonForm
    success_message = 'Seeker intention abandoned.'
    form_title = 'Abandon seeker intention'
    submit_label = 'Abandon'
    required_action = SEEKER_INTENTION_ABANDON

    def perform_action(self, form):
        S.intentions.AbandonSaleSeekerIntentionService(intention=self.get_intention(), **form.cleaned_data)

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'seeker-intentions'})


__all__ = [
    "ProviderIntentionCreateView",
    "DeliverValuationView",
    "ProviderPromotionView",
    "ProviderWithdrawView",
    "SeekerIntentionCreateView",
    "SeekerOpportunityCreateView",
    "SeekerAbandonView",
]
