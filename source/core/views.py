from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import HttpResponseRedirect
import uuid

from core.forms import (
    AgentEditForm,
    AgentForm,
    ConfirmationForm,
    ContactEditForm,
    ContactForm,
    PropertyEditForm,
    PropertyForm,
)
from core.models import Agent, Contact, Property
from utils.services import S
from utils.authorization import (
    AGENT_VIEW,
    AGENT_CREATE,
    AGENT_UPDATE,
    CONTACT_VIEW,
    CONTACT_CREATE,
    CONTACT_UPDATE,
    PROPERTY_VIEW,
    PROPERTY_CREATE,
    PROPERTY_UPDATE,
    PROVIDER_INTENTION_VIEW,
    PROVIDER_INTENTION_CREATE,
    PROVIDER_INTENTION_VALUATE,
    PROVIDER_INTENTION_WITHDRAW,
    PROVIDER_INTENTION_PROMOTE,
    SEEKER_INTENTION_VIEW,
    SEEKER_INTENTION_CREATE,
    SEEKER_INTENTION_ABANDON,
    PROVIDER_OPPORTUNITY_VIEW,
    PROVIDER_OPPORTUNITY_PUBLISH,
    SEEKER_OPPORTUNITY_VIEW,
    SEEKER_OPPORTUNITY_CREATE,
    OPERATION_VIEW,
    OPERATION_REINFORCE,
    OPERATION_CLOSE,
    OPERATION_LOSE,
    REPORT_VIEW,
    AGREEMENT_CREATE,
    AGREEMENT_AGREE,
    AGREEMENT_SIGN,
    AGREEMENT_REVOKE,
    AGREEMENT_CANCEL,
    INTEGRATION_VIEW,
    INTEGRATION_MANAGE,
    check,
)
from intentions.forms import (
    DeliverValuationForm,
    ProviderPromotionForm,
    ProviderWithdrawForm,
    ProviderIntentionForm,
    SeekerIntentionForm,
    SeekerAbandonForm,
)
from intentions.models import ProviderIntention, SeekerIntention
from opportunities.forms import (
    MarketingPackageForm,
    OperationLoseForm,
    OperationReinforceForm,
    SeekerOpportunityCreateForm,
    OperationAgreementCreateForm,
    SignOperationAgreementForm,
    CancelOperationAgreementForm,
    ValidationDocumentReviewForm,
    ValidationDocumentUploadForm,
    ValidationPresentForm,
    ValidationRejectForm,
    ValidationAdditionalDocumentUploadForm,
)
from opportunities.models import MarketingPackage, Operation, OperationAgreement, ProviderOpportunity, Validation, ValidationDocument
from opportunities.services import (  # noqa: F401  # retained for registry discovery
    MarketingPackageActivateService,
    MarketingPackageCreateService,
    MarketingPackageReleaseService,
    MarketingPackageUpdateService,
    MarketingPackagePauseService,
    CreateOperationService,
    CreateSeekerOpportunityService,
    OperationCloseService,
    OperationLoseService,
    OperationReinforceService,
    CreateOperationAgreementService,
    AgreeOperationAgreementService,
    SignOperationAgreementService,
    RevokeOperationAgreementService,
    CancelOperationAgreementService,
    AvailableProviderOpportunitiesForOperationsQuery,
    AvailableSeekerOpportunitiesForOperationsQuery,
    DashboardProviderOpportunitiesQuery,
    DashboardSeekerOpportunitiesQuery,
    DashboardOperationsQuery,
    DashboardProviderValidationsQuery,
    DashboardMarketingPackagesQuery,
    DashboardMarketingOpportunitiesWithoutPackagesQuery,
    ReviewValidationDocumentService,
    ValidationAcceptService,
    ValidationPresentService,
    ValidationRejectService,
    CreateValidationDocumentService,
    CreateAdditionalValidationDocumentService,
)
from integrations.tasks import sync_tokkobroker_properties_task, sync_tokkobroker_registry
from .tasks import log_message


async def health_check(request):
    return JsonResponse({'status': 'ok'})


async def trigger_log(request):
    message = request.GET.get('message', 'Health check ping received')
    queued = log_message.send(message)
    return JsonResponse({'status': 'queued', 'message_id': queued.message_id})


class PermissionedViewMixin:
    required_action = None

    def dispatch(self, request, *args, **kwargs):
        if self.required_action is not None:
            check(request.user, self.required_action)
        return super().dispatch(request, *args, **kwargs)


class DashboardSectionView(PermissionedViewMixin, LoginRequiredMixin, TemplateView):
    login_url = '/admin/login/'
    SECTION_ACTION_MAP = {
        'agents': AGENT_VIEW,
        'contacts': CONTACT_VIEW,
        'properties': PROPERTY_VIEW,
        'provider-intentions': PROVIDER_INTENTION_VIEW,
        'provider-valuations': PROVIDER_INTENTION_VIEW,
        'provider-opportunities': PROVIDER_OPPORTUNITY_VIEW,
        'provider-validations': PROVIDER_OPPORTUNITY_VIEW,
        'marketing-packages': PROVIDER_OPPORTUNITY_VIEW,
        'seeker-intentions': SEEKER_INTENTION_VIEW,
        'seeker-opportunities': SEEKER_OPPORTUNITY_VIEW,
        'operations': OPERATION_VIEW,
        'operation-agreements': OPERATION_VIEW,
        'reports-operations': REPORT_VIEW,
        'integration-tokkobroker': INTEGRATION_VIEW,
        'integration-zonaprop': INTEGRATION_VIEW,
        'integration-meta': INTEGRATION_VIEW,
    }
    NAV_GROUPS = [
        (
            'Core',
            [
                ('agents', 'Agents'),
                ('contacts', 'Contacts'),
                ('properties', 'Properties'),
            ],
        ),
        (
            'Providers',
            [
                ('provider-intentions', 'Provider Intentions'),
                ('provider-valuations', 'Valuations'),
                ('provider-opportunities', 'Provider Opportunities'),
                ('marketing-packages', 'Marketing Packages'),
                ('provider-validations', 'Documental Validations'),
            ],
        ),
        (
            'Seekers',
            [
                ('seeker-intentions', 'Seeker Intentions'),
                ('seeker-opportunities', 'Seeker Opportunities'),
            ],
        ),
        (
            'Operations',
            [
                ('operation-agreements', 'Operation Agreements'),
                ('operations', 'Operations'),
            ],
        ),
        (
            'Integrations',
            [
                ('integration-tokkobroker', 'Tokkobroker'),
                ('integration-zonaprop', 'Zonaprop'),
                ('integration-meta', 'Meta'),
            ],
        ),
        (
            'Reports',
            [
                ('reports-operations', 'Financial & Tax Report'),
            ],
        ),
    ]

    template_map = {
        'agents': 'workflow/sections/agents.html',
        'contacts': 'workflow/sections/contacts.html',
        'properties': 'workflow/sections/properties.html',
        'provider-intentions': 'workflow/sections/provider_intentions.html',
        'provider-valuations': 'workflow/sections/provider_valuations.html',
        'provider-opportunities': 'workflow/sections/provider_opportunities.html',
        'provider-validations': 'workflow/sections/provider_validations.html',
        'marketing-packages': 'workflow/sections/marketing_packages.html',
        'seeker-intentions': 'workflow/sections/seeker_intentions.html',
        'seeker-opportunities': 'workflow/sections/seeker_opportunities.html',
        'operations': 'workflow/sections/operations.html',
        'operation-agreements': 'workflow/sections/operation_agreements.html',
        'reports-operations': 'workflow/sections/reports_operations.html',
        'integration-tokkobroker': 'workflow/sections/integrations.html',
        'integration-zonaprop': 'workflow/sections/integration_placeholder.html',
        'integration-meta': 'workflow/sections/integration_placeholder.html',
    }

    NEW_ROUTE_NAMES = {
        'agents': 'agent-create',
        'contacts': 'contact-create',
        'properties': 'property-create',
        'provider-intentions': 'provider-intention-create',
        'seeker-intentions': 'seeker-intention-create',
        'operation-agreements': 'agreement-create',
    }

    ALL_SECTIONS = [slug for _, items in NAV_GROUPS for slug, _ in items]
    default_section = ALL_SECTIONS[0]

    def dispatch(self, request, *args, **kwargs):
        self.section = kwargs.get('section') or self.default_section
        if self.section not in self.template_map:
            raise Http404("Unknown dashboard section")
        # Resolve first accessible section if current one is not allowed
        required = self.SECTION_ACTION_MAP.get(self.section)
        try:
            if required:
                check(request.user, required)
        except PermissionDenied:
            fallback = self._first_accessible_section(request.user)
            if fallback:
                return redirect('workflow-dashboard-section', section=fallback)
            raise
        self.template_name = self.template_map[self.section]
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_section'] = self.section
        context['nav_groups'] = self._nav_for_user(self.request.user)
        context['current_url'] = self.request.get_full_path()
        context['page_new_url'] = self._resolve_new_url()
        context.update(getattr(self, f"_context_{self.section.replace('-', '_')}")())
        return context

    def _first_accessible_section(self, user):
        for slug in self.ALL_SECTIONS:
            required = self.SECTION_ACTION_MAP.get(slug)
            try:
                if required:
                    check(user, required)
                return slug
            except PermissionDenied:
                continue
        return None

    def _nav_for_user(self, user):
        nav = []
        for group_name, items in self.NAV_GROUPS:
            allowed_items = []
            for slug, label in items:
                required = self.SECTION_ACTION_MAP.get(slug)
                try:
                    if required:
                        check(user, required)
                    allowed_items.append((slug, label))
                except PermissionDenied:
                    continue
            if allowed_items:
                nav.append((group_name, allowed_items))
        return nav or self.NAV_GROUPS

    def _resolve_new_url(self):
        route_name = self.NEW_ROUTE_NAMES.get(self.section)
        if not route_name:
            return None
        return reverse(route_name)

    def _context_agents(self):
        return {
            'agents': S.core.AgentsQuery(actor=self.request.user),
        }

    def _context_contacts(self):
        return {
            'contacts': S.core.ContactsQuery(actor=self.request.user),
        }

    def _context_properties(self):
        return {
            'properties': S.core.PropertiesQuery(actor=self.request.user),
        }

    def _context_provider_intentions(self):
        return {
            'provider_intentions': S.core.ProviderIntentionsQuery(actor=self.request.user),
        }

    def _context_provider_valuations(self):
        return {
            'provider_valuations': S.core.ProviderValuationsQuery(actor=self.request.user),
        }

    def _context_provider_opportunities(self):
        scoped = S.opportunities.ProviderOpportunitiesForActorQuery(actor=self.request.user)
        provider_opportunities = scoped.select_related('source_intention__property', 'source_intention__owner').prefetch_related('state_transitions', 'validations').order_by('-created_at')
        return {
            'provider_opportunities': provider_opportunities,
        }

    def _context_provider_validations(self):
        return {
            'provider_validations': S.opportunities.DashboardProviderValidationsQuery(actor=self.request.user),
        }

    def _context_marketing_packages(self):
        return {
            'marketing_packages': S.opportunities.DashboardMarketingPackagesQuery(actor=self.request.user),
            'archived_marketing_packages': S.opportunities.DashboardArchivedMarketingPackagesQuery(actor=self.request.user),
            'marketing_opportunities_without_packages': S.opportunities.DashboardMarketingOpportunitiesWithoutPackagesQuery(actor=self.request.user),
        }

    def _context_seeker_intentions(self):
        return {
            'seeker_intentions': S.core.SeekerIntentionsQuery(actor=self.request.user),
        }

    def _context_seeker_opportunities(self):
        scoped = S.opportunities.SeekerOpportunitiesForActorQuery(actor=self.request.user)
        seeker_opportunities = scoped.select_related('source_intention__contact', 'source_intention__agent').prefetch_related('state_transitions').order_by('-created_at')
        return {
            'seeker_opportunities': seeker_opportunities,
        }

    def _context_operations(self):
        return {
            'operations': S.opportunities.DashboardOperationsQuery(actor=self.request.user),
        }

    def _context_operation_agreements(self):
        scoped = S.opportunities.OperationAgreementsForActorQuery(actor=self.request.user)
        return {
            'operation_agreements': scoped.order_by('-created_at'),
        }

    def _context_reports_operations(self):
        return {"report_rows": S.reports.ClosedOperationsFinancialReportQuery(actor=self.request.user)}

    def _context_integration_tokkobroker(self):
        return {
            'integration_name': 'Tokkobroker',
            'tokko_properties': S.core.TokkobrokerPropertiesQuery(actor=self.request.user),
        }

    def _context_integration_zonaprop(self):
        return {
            'integration_name': 'Zonaprop',
            'status_message': 'This integration is in progress. You will be able to sync Zonaprop properties from here soon.',
        }

    def _context_integration_meta(self):
        return {
            'integration_name': 'Meta',
            'status_message': 'Meta Ads integration is under development. Check back soon to activate it.',
        }


class WorkflowFormView(PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
    success_url = reverse_lazy('workflow-dashboard')
    success_message = 'Action completed successfully.'
    login_url = '/admin/login/'

    def perform_action(self, form):
        """Subclasses override to run service logic; return HttpResponse to short-circuit."""
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Use permission-filtered nav for consistency with dashboard sections
        nav = DashboardSectionView()._nav_for_user(self.request.user)
        context.setdefault('nav_groups', nav)
        context.setdefault('active_section', None)
        context.setdefault('current_url', self.request.get_full_path())
        context.setdefault('page_new_url', None)
        context.setdefault('next_url', self.request.GET.get('next') or self.request.POST.get('next'))
        default_title = getattr(self, 'form_title', None) or self.__class__.__name__.replace('View', ' ').strip().replace('_', ' ')
        context.setdefault('form_title', default_title)
        context.setdefault('form_description', getattr(self, 'form_description', None))
        context.setdefault('submit_label', getattr(self, 'submit_label', 'Submit'))
        context.setdefault('idempotency_token', self._issue_idempotency_token())
        return context

    def form_valid(self, form):
        try:
            first_use = self._consume_idempotency_token()
        except IdempotencyError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        if not first_use:
            return HttpResponseRedirect(self.get_success_url())
        try:
            response = self.perform_action(form)
        except ValidationError as exc:
            self._attach_form_errors(form, exc)
            return self.form_invalid(form)

        if response is not None:
            return response
        return super().form_valid(form)

    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        return super().get_success_url()

    def _attach_form_errors(self, form, exc: ValidationError):
        error_dict = getattr(exc, "error_dict", None)
        if error_dict:
            for field_name, errors in error_dict.items():
                target_field = field_name if field_name in form.fields else None
                for error in errors:
                    form.add_error(target_field, error)
            return

        for message in exc.messages:
            form.add_error(None, message)

    def _issue_idempotency_token(self) -> str:
        token = uuid.uuid4().hex
        issued = self.request.session.get('_form_tokens_issued', [])
        issued.append(token)
        issued = issued[-50:]
        self.request.session['_form_tokens_issued'] = issued
        self.request.session.modified = True
        return token

    def _consume_idempotency_token(self) -> bool:
        token = self.request.POST.get('_idempotency_token')
        if not token:
            raise IdempotencyError("Form submission token missing.")
        issued = set(self.request.session.get('_form_tokens_issued', []))
        if token not in issued:
            raise IdempotencyError("Form submission token is invalid or expired. Please reload the form.")
        used = self.request.session.get('_form_tokens_used', [])
        if token in used:
            return False
        used.append(token)
        used = used[-50:]
        self.request.session['_form_tokens_used'] = used
        self.request.session.modified = True
        return True


class IdempotencyError(Exception):
    pass


class AgentCreateView(WorkflowFormView):
    form_class = AgentForm
    success_message = 'Agent registered successfully.'
    form_title = 'Add agent'
    submit_label = 'Create agent'
    required_action = AGENT_CREATE

    def perform_action(self, form):
        S.core.CreateAgentService(**form.cleaned_data)


class ContactCreateView(WorkflowFormView):
    form_class = ContactForm
    success_message = 'Contact registered successfully.'
    form_title = 'Add contact'
    submit_label = 'Create contact'
    required_action = CONTACT_CREATE

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actor"] = self.request.user
        return kwargs

    def perform_action(self, form):
        agent = form.cleaned_data.pop('agent')
        contact = S.core.CreateContactService(**form.cleaned_data)
        S.core.LinkContactAgentService(contact=contact, agent=agent)


class PropertyCreateView(WorkflowFormView):
    form_class = PropertyForm
    success_message = 'Property registered successfully.'
    form_title = 'Add property'
    submit_label = 'Create property'
    required_action = PROPERTY_CREATE

    def perform_action(self, form):
        S.core.CreatePropertyService(**form.cleaned_data)


class ModelUpdateView(WorkflowFormView):
    model = None
    form_class = None
    pk_url_kwarg = 'pk'
    _object: Any | None = None

    def get_object(self):
        if self._object is None:
            self._object = get_object_or_404(self.model, pk=self.kwargs[self.pk_url_kwarg])
        return self._object

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_object()
        return kwargs

    def perform_action(self, form):
        form.save()


class AgentUpdateView(ModelUpdateView):
    model = Agent
    form_class = AgentEditForm
    pk_url_kwarg = 'agent_id'
    success_message = 'Agent updated successfully.'
    form_title = 'Edit agent'
    submit_label = 'Save changes'
    required_action = AGENT_UPDATE


class ContactUpdateView(ModelUpdateView):
    model = Contact
    form_class = ContactEditForm
    pk_url_kwarg = 'contact_id'
    success_message = 'Contact updated successfully.'
    form_title = 'Edit contact'
    submit_label = 'Save changes'
    required_action = CONTACT_UPDATE


class PropertyUpdateView(ModelUpdateView):
    model = Property
    form_class = PropertyEditForm
    pk_url_kwarg = 'property_id'
    success_message = 'Property updated successfully.'
    form_title = 'Edit property'
    submit_label = 'Save changes'
    required_action = PROPERTY_UPDATE


class ProviderIntentionMixin:
    pk_url_kwarg = 'intention_id'

    def get_intention(self):
        return get_object_or_404(ProviderIntention, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['intention'] = self.get_intention()
        return context


class SeekerIntentionMixin:
    pk_url_kwarg = 'intention_id'

    def get_intention(self):
        return get_object_or_404(SeekerIntention, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['intention'] = self.get_intention()
        return context


class ProviderIntentionCreateView(WorkflowFormView):
    form_class = ProviderIntentionForm
    success_message = 'Provider intention created.'
    form_title = 'New provider intention'
    form_description = 'Capture a seller lead before promoting to opportunity.'
    submit_label = 'Create intention'
    required_action = PROVIDER_INTENTION_CREATE

    def perform_action(self, form):
        S.intentions.CreateProviderIntentionService(**form.cleaned_data)


class DeliverValuationView(ProviderIntentionMixin, WorkflowFormView):
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
        S.intentions.DeliverValuationService(intention=self.get_intention(), **form.cleaned_data)

class ProviderPromotionView(ProviderIntentionMixin, WorkflowFormView):
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
        S.intentions.PromoteProviderIntentionService(
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


class ProviderWithdrawView(ProviderIntentionMixin, WorkflowFormView):
    form_class = ProviderWithdrawForm
    success_message = 'Provider intention withdrawn.'
    form_title = 'Withdraw provider intention'
    submit_label = 'Withdraw'
    required_action = PROVIDER_INTENTION_WITHDRAW

    def perform_action(self, form):
        S.intentions.WithdrawProviderIntentionService(intention=self.get_intention(), **form.cleaned_data)


class SeekerIntentionCreateView(WorkflowFormView):
    form_class = SeekerIntentionForm
    success_message = 'Seeker intention registered.'
    form_title = 'New seeker intention'
    submit_label = 'Create intention'
    required_action = SEEKER_INTENTION_CREATE

    def perform_action(self, form):
        S.intentions.CreateSeekerIntentionService(**form.cleaned_data)


class SeekerOpportunityCreateView(SeekerIntentionMixin, WorkflowFormView):
    form_class = SeekerOpportunityCreateForm
    success_message = 'Seeker opportunity created.'
    form_title = 'Create seeker opportunity'
    submit_label = 'Create opportunity'
    required_action = SEEKER_OPPORTUNITY_CREATE

    def perform_action(self, form):
        S.opportunities.CreateSeekerOpportunityService(intention=self.get_intention(), **form.cleaned_data)


class SeekerAbandonView(SeekerIntentionMixin, WorkflowFormView):
    form_class = SeekerAbandonForm
    success_message = 'Seeker intention abandoned.'
    form_title = 'Abandon seeker intention'
    submit_label = 'Abandon'
    required_action = SEEKER_INTENTION_ABANDON

    def perform_action(self, form):
        S.intentions.AbandonSeekerIntentionService(intention=self.get_intention(), **form.cleaned_data)


class ProviderOpportunityMixin:
    pk_url_kwarg = 'opportunity_id'

    def get_opportunity(self):
        return get_object_or_404(ProviderOpportunity, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['opportunity'] = self.get_opportunity()
        return context


class MarketingOpportunityMixin(ProviderOpportunityMixin):
    def get_opportunity(self):
        opportunity = super().get_opportunity()
        if opportunity.state != ProviderOpportunity.State.MARKETING:
            raise Http404("Opportunity is not in marketing stage")
        return opportunity


class MarketingPackageMixin:
    pk_url_kwarg = 'package_id'

    def get_package(self):
        return get_object_or_404(MarketingPackage, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['package'] = self.get_package()
        return context


class ValidationMixin:
    pk_url_kwarg = 'validation_id'

    def get_validation(self):
        return get_object_or_404(Validation, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['validation'] = self.get_validation()
        return context


class ValidationDetailView(ValidationMixin, TemplateView):
    template_name = 'workflow/validation_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        validation = context['validation']
        context['required_documents'] = validation.required_documents_status()
        context['custom_documents'] = validation.custom_documents()
        context['summary'] = validation.document_status_summary()
        context.setdefault('current_url', self.request.get_full_path())
        context.setdefault('nav_groups', DashboardSectionView.NAV_GROUPS)
        context.setdefault('active_section', 'provider-validations')
        context.setdefault('page_new_url', None)
        next_url = self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            context['back_url'] = next_url
        else:
            context['back_url'] = reverse('workflow-dashboard-section', kwargs={'section': 'provider-validations'})
        return context


class ValidationDocumentMixin:
    pk_url_kwarg = 'document_id'

    def get_document(self):
        return get_object_or_404(ValidationDocument, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['document'] = self.get_document()
        return context


class ValidationPresentView(ValidationMixin, WorkflowFormView):
    form_class = ValidationPresentForm
    success_message = 'Validation presented.'
    form_title = 'Present validation'
    submit_label = 'Present'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def perform_action(self, form):
        S.opportunities.ValidationPresentService(validation=self.get_validation())


class ValidationRejectView(ValidationMixin, WorkflowFormView):
    form_class = ValidationRejectForm
    success_message = 'Validation sent back to preparation.'
    form_title = 'Revoke validation'
    form_description = 'Send the validation back to preparing and optionally add notes.'
    submit_label = 'Revoke'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def perform_action(self, form):
        S.opportunities.ValidationRejectService(validation=self.get_validation(), notes=form.cleaned_data.get('notes'))


class ValidationAcceptView(ValidationMixin, WorkflowFormView):
    form_class = ConfirmationForm
    success_message = 'Validation accepted and opportunity published.'
    form_title = 'Accept validation'
    submit_label = 'Accept'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def perform_action(self, form):
        S.opportunities.ValidationAcceptService(validation=self.get_validation())


class ValidationDocumentUploadView(ValidationMixin, WorkflowFormView):
    form_class = ValidationDocumentUploadForm
    success_message = 'Validation document uploaded.'
    form_title = 'Upload document'
    submit_label = 'Upload'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def get_initial(self):
        initial = super().get_initial()
        requested_type = self.request.GET.get('document_type')
        if requested_type:
            doc_type = S.opportunities.ValidationDocumentTypesQuery().filter(code=requested_type).first()
            if doc_type:
                initial['document_type'] = doc_type
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        doc_type = self.request.GET.get('document_type') or self.request.POST.get('document_type')
        kwargs['forced_document_type'] = doc_type
        kwargs['validation'] = self.get_validation()
        return kwargs

    def perform_action(self, form):
        S.opportunities.CreateValidationDocumentService(
            validation=self.get_validation(),
            document_type=form.cleaned_data['document_type'],
            observations=form.cleaned_data.get('observations') or None,
            document=form.cleaned_data['document'],
            uploaded_by=self.request.user if self.request.user.is_authenticated else None,
        )


class ValidationAdditionalDocumentUploadView(ValidationMixin, WorkflowFormView):
    form_class = ValidationAdditionalDocumentUploadForm
    success_message = 'Custom document uploaded.'
    form_title = 'Upload custom document'
    submit_label = 'Upload'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def perform_action(self, form):
        S.opportunities.CreateAdditionalValidationDocumentService(
            validation=self.get_validation(),
            observations=form.cleaned_data.get('observations') or None,
            document=form.cleaned_data['document'],
            uploaded_by=self.request.user if self.request.user.is_authenticated else None,
        )


class ValidationDocumentReviewView(ValidationDocumentMixin, WorkflowFormView):
    form_class = ValidationDocumentReviewForm
    success_message = 'Validation document reviewed.'
    form_title = 'Review document'
    submit_label = 'Submit review'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def perform_action(self, form):
        S.opportunities.ReviewValidationDocumentService(
            document=self.get_document(),
            action=form.cleaned_data['action'],
            reviewer=self.request.user,
            comment=form.cleaned_data.get('comment'),
        )


class MarketingPackageCreateView(MarketingOpportunityMixin, WorkflowFormView):
    form_class = MarketingPackageForm
    success_message = 'Marketing package created.'
    success_url = reverse_lazy('workflow-dashboard-section', kwargs={'section': 'marketing-packages'})
    form_title = 'Create marketing package'
    submit_label = 'Create package'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def perform_action(self, form):
        S.opportunities.MarketingPackageCreateService(opportunity=self.get_opportunity(), **form.cleaned_data)


class MarketingPackageUpdateView(MarketingPackageMixin, WorkflowFormView):
    form_class = MarketingPackageForm
    success_message = 'Marketing package updated.'
    form_title = 'Update marketing package'
    submit_label = 'Save changes'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def get_initial(self):
        package = self.get_package()
        initial = super().get_initial()
        for field in self.form_class.Meta.fields:
            initial[field] = getattr(package, field)
        return initial

    def perform_action(self, form):
        S.opportunities.MarketingPackageUpdateService(package=self.get_package(), **form.cleaned_data)

    def get_success_url(self):
        # Stay on the same package after saving edits
        return self.request.get_full_path()


class MarketingPackageActionView(MarketingPackageMixin, WorkflowFormView):
    form_class = ConfirmationForm
    service_name = None
    service_app = "opportunities"
    success_url = reverse_lazy('workflow-dashboard-section', kwargs={'section': 'marketing-packages'})
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def get_service(self):
        if not self.service_name:
            raise RuntimeError('service_name not configured')
        try:
            namespace = getattr(S, self.service_app)
            return getattr(namespace, self.service_name)
        except AttributeError as exc:  # pragma: no cover - defensive guard for misconfiguration
            raise RuntimeError(f"Service {self.service_app}.{self.service_name} not found") from exc

    def perform_action(self, form):
        service = self.get_service()
        service(package=self.get_package())


class MarketingPackageActivateView(MarketingPackageActionView):
    success_message = 'Marketing package activated.'
    form_title = 'Publish package'
    submit_label = 'Publish'
    service_name = "MarketingPackageActivateService"


class MarketingPackageReleaseView(MarketingPackageActionView):
    success_message = 'Marketing package resumed.'
    form_title = 'Publish package'
    submit_label = 'Publish'
    service_name = "MarketingPackageReleaseService"


class MarketingPackagePauseView(MarketingPackageActionView):
    success_message = 'Marketing package paused.'
    form_title = 'Pause package'
    submit_label = 'Pause'
    service_name = "MarketingPackagePauseService"





class OperationMixin:
    pk_url_kwarg = 'operation_id'

    def get_operation(self):
        return get_object_or_404(Operation, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['operation'] = self.get_operation()
        return context


class OperationReinforceView(OperationMixin, WorkflowFormView):
    form_class = OperationReinforceForm
    success_message = 'Operation reinforced.'
    form_title = 'Reinforce operation'
    submit_label = 'Reinforce'
    required_action = OPERATION_REINFORCE

    def perform_action(self, form):
        S.opportunities.OperationReinforceService(operation=self.get_operation(), **form.cleaned_data)


class OperationCloseView(OperationMixin, WorkflowFormView):
    form_class = ConfirmationForm
    success_message = 'Operation closed.'
    form_title = 'Close operation'
    submit_label = 'Close'
    required_action = OPERATION_CLOSE

    def perform_action(self, form):
        S.opportunities.OperationCloseService(operation=self.get_operation())


class OperationLoseView(OperationMixin, WorkflowFormView):
    form_class = OperationLoseForm
    success_message = 'Operation marked as lost.'
    form_title = 'Mark operation as lost'
    submit_label = 'Mark lost'
    required_action = OPERATION_LOSE

    def perform_action(self, form):
        S.opportunities.OperationLoseService(operation=self.get_operation(), **form.cleaned_data)


class TokkoSyncRunView(PermissionedViewMixin, LoginRequiredMixin, View):
    login_url = '/admin/login/'
    required_action = INTEGRATION_MANAGE

    def post(self, request):
        processed = sync_tokkobroker_registry()
        messages.success(request, f'Synced {processed} Tokkobroker properties.')
        return self._redirect_back(request)

    def get(self, request):  # pragma: no cover - defensive; redirect to avoid GET usage
        return self._redirect_back(request)

    def _redirect_back(self, request):
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('workflow-dashboard-section', section='integrations')


class TokkoSyncEnqueueView(PermissionedViewMixin, LoginRequiredMixin, View):
    login_url = '/admin/login/'
    required_action = INTEGRATION_MANAGE

    def post(self, request):
        message = sync_tokkobroker_properties_task.send()
        messages.info(request, f'Tokkobroker sync enqueued (message ID: {message.message_id}).')
        return self._redirect_back(request)

    def get(self, request):  # pragma: no cover
        return self._redirect_back(request)

    def _redirect_back(self, request):
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('workflow-dashboard-section', section='integrations')


class TokkoClearView(PermissionedViewMixin, LoginRequiredMixin, View):
    login_url = '/admin/login/'
    required_action = INTEGRATION_MANAGE

    def post(self, request):
        deleted = S.integrations.ClearTokkobrokerRegistryService()
        messages.warning(request, f'Cleared {deleted} Tokkobroker properties.')
        return self._redirect_back(request)

    def get(self, request):  # pragma: no cover
        return self._redirect_back(request)

    def _redirect_back(self, request):
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('workflow-dashboard-section', section='integrations')


class ObjectTransitionHistoryView(PermissionedViewMixin, LoginRequiredMixin, TemplateView):
    template_name = 'workflow/transition_history.html'
    login_url = '/admin/login/'
    required_action = REPORT_VIEW
    OBJECT_SECTION_MAP = {
        'core.agent': 'agents',
        'core.contact': 'contacts',
        'core.property': 'properties',
        'intentions.providerintention': 'provider-intentions',
        'intentions.seekerintention': 'seeker-intentions',
        'opportunities.provideropportunity': 'provider-opportunities',
        'opportunities.validation': 'provider-validations',
        'opportunities.seekeropportunity': 'seeker-opportunities',
        'opportunities.operation': 'operations',
    }

    def get_object(self):
        app_label = self.kwargs['app_label']
        model = self.kwargs['model']
        object_id = self.kwargs['object_id']
        try:
            obj = S.core.ObjectByNaturalKeyQuery(app_label=app_label, model=model, pk=object_id)
        except Exception as exc:  # pragma: no cover - defensive
            raise Http404("Unknown object type") from exc
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        transitions = S.core.FSMTransitionsForObjectQuery(obj=obj)
        context.update(
            object=obj,
            transitions=transitions,
        )
        context.setdefault('nav_groups', DashboardSectionView.NAV_GROUPS)
        context.setdefault('active_section', None)
        context.setdefault('current_url', self.request.get_full_path())
        context['back_url'] = self._resolve_back_url(obj)
        return context

    def _resolve_back_url(self, obj):
        next_url = self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        slug = self.OBJECT_SECTION_MAP.get(obj._meta.label_lower)
        if slug:
            return reverse('workflow-dashboard-section', kwargs={'section': slug})
        return reverse('workflow-dashboard')


class OperationAgreementMixin:
    pk_url_kwarg = 'agreement_id'

    def get_agreement(self):
        return get_object_or_404(OperationAgreement, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agreement'] = self.get_agreement()
        return context


class AgreeOperationAgreementView(OperationAgreementMixin, WorkflowFormView):
    form_class = ConfirmationForm
    success_message = 'Agreement confirmed.'
    form_title = 'Confirm Agreement'
    submit_label = 'Agree'
    success_url = reverse_lazy('workflow-dashboard-section', kwargs={'section': 'operation-agreements'})
    required_action = AGREEMENT_AGREE

    def perform_action(self, form):
        S.opportunities.AgreeOperationAgreementService(agreement=self.get_agreement())


class RevokeOperationAgreementView(OperationAgreementMixin, WorkflowFormView):
    form_class = ConfirmationForm
    success_message = 'Agreement revoked.'
    form_title = 'Revoke Agreement'
    submit_label = 'Revoke'
    success_url = reverse_lazy('workflow-dashboard-section', kwargs={'section': 'operation-agreements'})
    required_action = AGREEMENT_REVOKE

    def perform_action(self, form):
        S.opportunities.RevokeOperationAgreementService(agreement=self.get_agreement())


class CancelOperationAgreementView(OperationAgreementMixin, WorkflowFormView):
    form_class = CancelOperationAgreementForm
    success_message = 'Agreement cancelled.'
    form_title = 'Cancel Agreement'
    submit_label = 'Cancel Agreement'
    success_url = reverse_lazy('workflow-dashboard-section', kwargs={'section': 'operation-agreements'})
    required_action = AGREEMENT_CANCEL

    def perform_action(self, form):
        S.opportunities.CancelOperationAgreementService(
            agreement=self.get_agreement(),
            reason=form.cleaned_data['reason']
        )


class SignOperationAgreementView(OperationAgreementMixin, WorkflowFormView):
    form_class = SignOperationAgreementForm
    success_message = 'Agreement signed and Operation created.'
    form_title = 'Sign Agreement'
    submit_label = 'Sign & Create Operation'
    success_url = reverse_lazy('workflow-dashboard-section', kwargs={'section': 'operation-agreements'})
    required_action = AGREEMENT_SIGN

    def perform_action(self, form):
        S.opportunities.SignOperationAgreementService(
            agreement=self.get_agreement(),
            **form.cleaned_data
        )


class OperationAgreementCreateView(WorkflowFormView):
    form_class = OperationAgreementCreateForm
    success_message = 'Operation agreement created.'
    form_title = 'Create Operation Agreement'
    form_description = 'Start a negotiation between a provider and seeker.'
    submit_label = 'Create Agreement'
    success_url = reverse_lazy('workflow-dashboard-section', kwargs={'section': 'operation-agreements'})
    required_action = AGREEMENT_CREATE

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actor"] = self.request.user
        return kwargs

    def perform_action(self, form):
        S.opportunities.CreateOperationAgreementService(**form.cleaned_data)
