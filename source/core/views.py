from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
from django.utils.http import url_has_allowed_host_and_scheme

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
from intentions.forms import (
    DeliverValuationForm,
    ProviderPromotionForm,
    ProviderWithdrawForm,
    SaleProviderIntentionForm,
    SaleSeekerIntentionForm,
    SeekerAbandonForm,
)
from intentions.models import SaleProviderIntention, SaleSeekerIntention
from intentions.services import (
    CreateSaleProviderIntentionService,
    CreateSaleSeekerIntentionService,
    DeliverSaleValuationService,
    AbandonSaleSeekerIntentionService,
    PromoteSaleProviderIntentionService,
    WithdrawSaleProviderIntentionService,
)
from opportunities.forms import (
    MarketingPackageForm,
    OperationForm,
    OperationLoseForm,
    OperationReinforceForm,
    SeekerOpportunityCreateForm,
    ValidationDocumentReviewForm,
    ValidationDocumentUploadForm,
    ValidationPresentForm,
    ValidationRejectForm,
    ValidationAdditionalDocumentUploadForm,
)
from opportunities.models import (
    MarketingPackage,
    Operation,
    ProviderOpportunity,
    SeekerOpportunity,
    Validation,
    ValidationDocument,
    ValidationDocumentType,
)
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
from integrations.models import TokkobrokerProperty
from integrations.tasks import sync_tokkobroker_properties_task, sync_tokkobroker_registry
from utils.models import FSMStateTransition
from .tasks import log_message


async def health_check(request):
    return JsonResponse({'status': 'ok'})


async def trigger_log(request):
    message = request.GET.get('message', 'Health check ping received')
    queued = log_message.send(message)
    return JsonResponse({'status': 'queued', 'message_id': queued.message_id})


class DashboardSectionView(LoginRequiredMixin, TemplateView):
    login_url = '/admin/login/'
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
        'provider-opportunities': 'workflow/sections/provider_opportunities.html',
        'provider-validations': 'workflow/sections/provider_validations.html',
        'marketing-packages': 'workflow/sections/marketing_packages.html',
        'seeker-intentions': 'workflow/sections/seeker_intentions.html',
        'seeker-opportunities': 'workflow/sections/seeker_opportunities.html',
        'operations': 'workflow/sections/operations.html',
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
        'operations': 'operation-create',
    }

    ALL_SECTIONS = [slug for _, items in NAV_GROUPS for slug, _ in items]
    default_section = ALL_SECTIONS[0]

    def dispatch(self, request, *args, **kwargs):
        self.section = kwargs.get('section') or self.default_section
        if self.section not in self.template_map:
            raise Http404("Unknown dashboard section")
        self.template_name = self.template_map[self.section]
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_section'] = self.section
        context['nav_groups'] = self.NAV_GROUPS
        context['current_url'] = self.request.get_full_path()
        context['page_new_url'] = self._resolve_new_url()
        context.update(getattr(self, f'_context_{self.section.replace('-', '_')}')())
        return context

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

    def _context_provider_opportunities(self):
        return {
            'provider_opportunities': S.opportunities.DashboardProviderOpportunitiesQuery(actor=self.request.user),
        }

    def _context_provider_validations(self):
        return {
            'provider_validations': S.opportunities.DashboardProviderValidationsQuery(actor=self.request.user),
        }

    def _context_marketing_packages(self):
        return {
            'marketing_packages': S.opportunities.DashboardMarketingPackagesQuery(actor=self.request.user),
            'marketing_opportunities_without_packages': S.opportunities.DashboardMarketingOpportunitiesWithoutPackagesQuery(actor=self.request.user),
        }

    def _context_seeker_intentions(self):
        return {
            'seeker_intentions': S.core.SeekerIntentionsQuery(actor=self.request.user),
        }

    def _context_seeker_opportunities(self):
        return {
            'seeker_opportunities': S.opportunities.DashboardSeekerOpportunitiesQuery(actor=self.request.user),
        }

    def _context_operations(self):
        return {
            'operations': S.opportunities.DashboardOperationsQuery(actor=self.request.user),
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
            'status_message': 'Estamos preparando esta integración. Pronto podrás sincronizar propiedades de Zonaprop desde aquí.',
        }

    def _context_integration_meta(self):
        return {
            'integration_name': 'Meta',
            'status_message': 'Integración con Meta Ads en desarrollo. Volvé pronto para activarla.',
        }


class WorkflowFormView(LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
    success_url = reverse_lazy('workflow-dashboard')
    success_message = 'Action completed successfully.'
    login_url = '/admin/login/'

    def perform_action(self, form):
        """Subclasses override to run service logic; return HttpResponse to short-circuit."""
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('nav_groups', DashboardSectionView.NAV_GROUPS)
        context.setdefault('active_section', None)
        context.setdefault('current_url', self.request.get_full_path())
        context.setdefault('page_new_url', None)
        context.setdefault('next_url', self.request.GET.get('next') or self.request.POST.get('next'))
        default_title = getattr(self, 'form_title', None) or self.__class__.__name__.replace('View', ' ').strip().replace('_', ' ')
        context.setdefault('form_title', default_title)
        context.setdefault('form_description', getattr(self, 'form_description', None))
        context.setdefault('submit_label', getattr(self, 'submit_label', 'Submit'))
        return context

    def form_valid(self, form):
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
        if hasattr(exc, 'error_dict'):
            for field_name, errors in exc.message_dict.items():
                target_field = field_name if field_name in form.fields else None
                for error in errors:
                    form.add_error(target_field, error)
        elif hasattr(exc, 'messages'):
            for message in exc.messages:
                form.add_error(None, message)
        else:
            form.add_error(None, str(exc))


class AgentCreateView(WorkflowFormView):
    form_class = AgentForm
    success_message = 'Agent registered successfully.'
    form_title = 'Add agent'
    submit_label = 'Create agent'

    def perform_action(self, form):
        S.core.CreateAgentService(**form.cleaned_data)


class ContactCreateView(WorkflowFormView):
    form_class = ContactForm
    success_message = 'Contact registered successfully.'
    form_title = 'Add contact'
    submit_label = 'Create contact'

    def perform_action(self, form):
        agent = form.cleaned_data.pop('agent')
        contact = S.core.CreateContactService(**form.cleaned_data)
        S.core.LinkContactAgentService(contact=contact, agent=agent)


class PropertyCreateView(WorkflowFormView):
    form_class = PropertyForm
    success_message = 'Property registered successfully.'
    form_title = 'Add property'
    submit_label = 'Create property'

    def perform_action(self, form):
        S.core.CreatePropertyService(**form.cleaned_data)


class ModelUpdateView(WorkflowFormView):
    model = None
    form_class = None
    pk_url_kwarg = 'pk'

    def get_object(self):
        if not hasattr(self, '_object'):
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


class ContactUpdateView(ModelUpdateView):
    model = Contact
    form_class = ContactEditForm
    pk_url_kwarg = 'contact_id'
    success_message = 'Contact updated successfully.'
    form_title = 'Edit contact'
    submit_label = 'Save changes'


class PropertyUpdateView(ModelUpdateView):
    model = Property
    form_class = PropertyEditForm
    pk_url_kwarg = 'property_id'
    success_message = 'Property updated successfully.'
    form_title = 'Edit property'
    submit_label = 'Save changes'


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


class ProviderIntentionCreateView(WorkflowFormView):
    form_class = SaleProviderIntentionForm
    success_message = 'Provider intention created.'
    form_title = 'New provider intention'
    form_description = 'Capture a seller lead before promoting to opportunity.'
    submit_label = 'Create intention'

    def perform_action(self, form):
        S.intentions.CreateSaleProviderIntentionService(**form.cleaned_data)


class DeliverValuationView(ProviderIntentionMixin, WorkflowFormView):
    form_class = DeliverValuationForm
    success_message = 'Valuation delivered.'
    form_title = 'Deliver valuation'
    form_description = 'Provide the valuation amount and currency to advance the seller.'
    submit_label = 'Deliver valuation'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['currency_queryset'] = S.core.CurrenciesQuery(actor=self.request.user)
        return kwargs

    def perform_action(self, form):
        S.intentions.DeliverSaleValuationService(intention=self.get_intention(), **form.cleaned_data)

class ProviderPromotionView(ProviderIntentionMixin, WorkflowFormView):
    form_class = ProviderPromotionForm
    success_message = 'Provider intention promoted to opportunity.'
    form_title = 'Promote to opportunity'
    form_description = 'Create a provider opportunity and initial marketing package.'
    submit_label = 'Promote'

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


class ProviderWithdrawView(ProviderIntentionMixin, WorkflowFormView):
    form_class = ProviderWithdrawForm
    success_message = 'Provider intention withdrawn.'
    form_title = 'Withdraw provider intention'
    submit_label = 'Withdraw'

    def perform_action(self, form):
        S.intentions.WithdrawSaleProviderIntentionService(intention=self.get_intention(), **form.cleaned_data)


class SeekerIntentionCreateView(WorkflowFormView):
    form_class = SaleSeekerIntentionForm
    success_message = 'Seeker intention registered.'
    form_title = 'New seeker intention'
    submit_label = 'Create intention'

    def perform_action(self, form):
        S.intentions.CreateSaleSeekerIntentionService(**form.cleaned_data)


class SeekerOpportunityCreateView(SeekerIntentionMixin, WorkflowFormView):
    form_class = SeekerOpportunityCreateForm
    success_message = 'Seeker opportunity created.'
    form_title = 'Create seeker opportunity'
    submit_label = 'Create opportunity'

    def perform_action(self, form):
        S.opportunities.CreateSeekerOpportunityService(intention=self.get_intention(), **form.cleaned_data)


class SeekerAbandonView(SeekerIntentionMixin, WorkflowFormView):
    form_class = SeekerAbandonForm
    success_message = 'Seeker intention abandoned.'
    form_title = 'Abandon seeker intention'
    submit_label = 'Abandon'

    def perform_action(self, form):
        S.intentions.AbandonSaleSeekerIntentionService(intention=self.get_intention(), **form.cleaned_data)


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

    def perform_action(self, form):
        S.opportunities.ValidationPresentService(validation=self.get_validation())


class ValidationRejectView(ValidationMixin, WorkflowFormView):
    form_class = ValidationRejectForm
    success_message = 'Validation sent back to preparation.'
    form_title = 'Revoke validation'
    form_description = 'Send the validation back to preparing and optionally add notes.'
    submit_label = 'Revoke'

    def perform_action(self, form):
        S.opportunities.ValidationRejectService(validation=self.get_validation(), notes=form.cleaned_data.get('notes'))


class ValidationAcceptView(ValidationMixin, WorkflowFormView):
    form_class = ConfirmationForm
    success_message = 'Validation accepted and opportunity published.'
    form_title = 'Accept validation'
    submit_label = 'Accept'

    def perform_action(self, form):
        S.opportunities.ValidationAcceptService(validation=self.get_validation())


class ValidationDocumentUploadView(ValidationMixin, WorkflowFormView):
    form_class = ValidationDocumentUploadForm
    success_message = 'Validation document uploaded.'
    form_title = 'Upload document'
    submit_label = 'Upload'

    def get_initial(self):
        initial = super().get_initial()
        requested_type = self.request.GET.get('document_type')
        if requested_type:
            doc_type = ValidationDocumentType.objects.filter(code=requested_type).first()
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

    def perform_action(self, form):
        S.opportunities.MarketingPackageCreateService(opportunity=self.get_opportunity(), **form.cleaned_data)


class MarketingPackageUpdateView(MarketingPackageMixin, WorkflowFormView):
    form_class = MarketingPackageForm
    success_message = 'Marketing package updated.'
    success_url = reverse_lazy('workflow-dashboard-section', kwargs={'section': 'marketing-packages'})
    form_title = 'Update marketing package'
    submit_label = 'Save changes'

    def get_initial(self):
        package = self.get_package()
        initial = super().get_initial()
        for field in self.form_class.Meta.fields:
            initial[field] = getattr(package, field)
        return initial

    def perform_action(self, form):
        S.opportunities.MarketingPackageUpdateService(package=self.get_package(), **form.cleaned_data)


class MarketingPackageActionView(MarketingPackageMixin, WorkflowFormView):
    form_class = ConfirmationForm
    service_class = None
    success_url = reverse_lazy('workflow-dashboard-section', kwargs={'section': 'marketing-packages'})

    def perform_action(self, form):
        if not self.service_class:
            raise RuntimeError('service_class not configured')
        self.service_class.call(package=self.get_package())


class MarketingPackageActivateView(MarketingPackageActionView):
    success_message = 'Marketing package activated.'
    form_title = 'Publish package'
    submit_label = 'Publish'
    service_class = MarketingPackageActivateService


class MarketingPackageReleaseView(MarketingPackageActionView):
    success_message = 'Marketing package resumed.'
    form_title = 'Publish package'
    submit_label = 'Publish'
    service_class = MarketingPackageReleaseService


class MarketingPackagePauseView(MarketingPackageActionView):
    success_message = 'Marketing package paused.'
    form_title = 'Pause package'
    submit_label = 'Pause'
    service_class = MarketingPackagePauseService


class OperationCreateView(WorkflowFormView):
    form_class = OperationForm
    success_message = 'Operation created.'
    form_title = 'Create operation'
    form_description = 'Link a provider and seeker opportunity to start negotiation.'
    submit_label = 'Create operation'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actor"] = self.request.user
        return kwargs

    def perform_action(self, form):
        S.opportunities.CreateOperationService(**form.cleaned_data)


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

    def perform_action(self, form):
        S.opportunities.OperationReinforceService(operation=self.get_operation(), **form.cleaned_data)


class OperationCloseView(OperationMixin, WorkflowFormView):
    form_class = ConfirmationForm
    success_message = 'Operation closed.'
    form_title = 'Close operation'
    submit_label = 'Close'

    def perform_action(self, form):
        S.opportunities.OperationCloseService(operation=self.get_operation())


class OperationLoseView(OperationMixin, WorkflowFormView):
    form_class = OperationLoseForm
    success_message = 'Operation marked as lost.'
    form_title = 'Mark operation as lost'
    submit_label = 'Mark lost'

    def perform_action(self, form):
        S.opportunities.OperationLoseService(operation=self.get_operation(), **form.cleaned_data)


class TokkoSyncRunView(LoginRequiredMixin, View):
    login_url = '/admin/login/'

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


class TokkoSyncEnqueueView(LoginRequiredMixin, View):
    login_url = '/admin/login/'

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


class TokkoClearView(LoginRequiredMixin, View):
    login_url = '/admin/login/'

    def post(self, request):
        deleted, _ = TokkobrokerProperty.objects.all().delete()
        messages.warning(request, f'Cleared {deleted} Tokkobroker properties.')
        return self._redirect_back(request)

    def get(self, request):  # pragma: no cover
        return self._redirect_back(request)

    def _redirect_back(self, request):
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('workflow-dashboard-section', section='integrations')


class ObjectTransitionHistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'workflow/transition_history.html'
    login_url = '/admin/login/'
    OBJECT_SECTION_MAP = {
        'core.agent': 'agents',
        'core.contact': 'contacts',
        'core.property': 'properties',
        'intentions.saleproviderintention': 'provider-intentions',
        'intentions.saleseekerintention': 'seeker-intentions',
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
            content_type = ContentType.objects.get(app_label=app_label, model=model)
        except ContentType.DoesNotExist as exc:  # pragma: no cover - defensive
            raise Http404("Unknown object type") from exc
        model_class = content_type.model_class()
        if model_class is None:
            raise Http404("Model unavailable")
        return get_object_or_404(model_class, pk=object_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        transitions = FSMStateTransition.objects.filter(
            content_type=ContentType.objects.get_for_model(obj, for_concrete_model=False),
            object_id=obj.pk,
        ).order_by('occurred_at')
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
