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

from core.forms import AgentForm, ConfirmationForm, ContactForm, PropertyForm
from core.models import Agent, Contact, Property
from core.services import (
    CreateAgentService,
    CreateContactService,
    CreatePropertyService,
    LinkContactAgentService,
)
from intentions.forms import (
    DeliverValuationForm,
    ProviderContractForm,
    ProviderPromotionForm,
    ProviderWithdrawForm,
    SaleProviderIntentionForm,
    SaleSeekerIntentionForm,
    SeekerAbandonForm,
    SeekerMandateForm,
)
from intentions.models import SaleProviderIntention, SaleSeekerIntention
from intentions.services import (
    AbandonSaleSeekerIntentionService,
    ActivateSaleSeekerIntentionService,
    CreateSaleProviderIntentionService,
    CreateSaleSeekerIntentionService,
    DeliverSaleValuationService,
    MandateSaleSeekerIntentionService,
    PromoteSaleProviderIntentionService,
    StartSaleProviderContractNegotiationService,
    WithdrawSaleProviderIntentionService,
)
from opportunities.forms import (
    OperationForm,
    OperationLoseForm,
    SeekerOpportunityCreateForm,
    ValidationDocumentReviewForm,
    ValidationDocumentUploadForm,
    ValidationPresentForm,
    ValidationRejectForm,
)
from opportunities.models import (
    Operation,
    ProviderOpportunity,
    SeekerOpportunity,
    Validation,
    ValidationDocument,
)
from opportunities.services import (
    CreateOperationService,
    CreateSeekerOpportunityService,
    OperationCloseService,
    OperationLoseService,
    OperationReinforceService,
    OpportunityValidateService,
    ReviewValidationDocumentService,
    ValidationAcceptService,
    ValidationPresentService,
    ValidationRejectService,
    CreateValidationDocumentService,
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


class WorkflowDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'workflow/dashboard.html'
    login_url = '/admin/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            agents=Agent.objects.order_by('-created_at')[:10],
            contacts=Contact.objects.select_related().order_by('-created_at')[:10],
            properties=Property.objects.order_by('-created_at')[:10],
            provider_intentions=(
                SaleProviderIntention.objects.select_related('owner', 'agent', 'property')
                .prefetch_related('state_transitions')
                .order_by('-created_at')
            ),
            seeker_intentions=(
                SaleSeekerIntention.objects.select_related('contact', 'agent')
                .prefetch_related('state_transitions')
                .order_by('-created_at')
            ),
            provider_opportunities=(
                ProviderOpportunity.objects.select_related('source_intention')
                .prefetch_related('validations__documents', 'state_transitions')
                .order_by('-created_at')
            ),
            seeker_opportunities=(
                SeekerOpportunity.objects.select_related('source_intention')
                .prefetch_related('state_transitions')
                .order_by('-created_at')
            ),
            operations=(
                Operation.objects.select_related('provider_opportunity', 'seeker_opportunity')
                .prefetch_related('state_transitions')
                .order_by('-created_at')
            ),
            tokko_properties=TokkobrokerProperty.objects.order_by('-created_at')[:10],
        )
        return context


class WorkflowFormView(LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
    success_url = reverse_lazy('workflow-dashboard')
    success_message = 'Action completed successfully.'
    login_url = '/admin/login/'

    def perform_action(self, form):
        """Subclasses override to run service logic; return HttpResponse to short-circuit."""
        return None

    def form_valid(self, form):
        try:
            response = self.perform_action(form)
        except ValidationError as exc:
            self._attach_form_errors(form, exc)
            return self.form_invalid(form)

        if response is not None:
            return response
        return super().form_valid(form)

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

    def perform_action(self, form):
        CreateAgentService.call(**form.cleaned_data)


class ContactCreateView(WorkflowFormView):
    form_class = ContactForm
    success_message = 'Contact registered successfully.'

    def perform_action(self, form):
        agent = form.cleaned_data.pop('agent')
        contact = CreateContactService.call(**form.cleaned_data)
        LinkContactAgentService.call(contact=contact, agent=agent)


class PropertyCreateView(WorkflowFormView):
    form_class = PropertyForm
    success_message = 'Property registered successfully.'

    def perform_action(self, form):
        CreatePropertyService.call(**form.cleaned_data)


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

    def perform_action(self, form):
        CreateSaleProviderIntentionService.call(**form.cleaned_data)


class DeliverValuationView(ProviderIntentionMixin, WorkflowFormView):
    form_class = DeliverValuationForm
    success_message = 'Valuation delivered.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        from core.models import Currency

        kwargs['currency_queryset'] = Currency.objects.order_by('code')
        return kwargs

    def perform_action(self, form):
        DeliverSaleValuationService.call(intention=self.get_intention(), **form.cleaned_data)


class ProviderContractView(ProviderIntentionMixin, WorkflowFormView):
    form_class = ProviderContractForm
    success_message = 'Contract negotiation started.'

    def perform_action(self, form):
        StartSaleProviderContractNegotiationService.call(intention=self.get_intention(), **form.cleaned_data)


class ProviderPromotionView(ProviderIntentionMixin, WorkflowFormView):
    form_class = ProviderPromotionForm
    success_message = 'Provider intention promoted to opportunity.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        from core.models import Currency

        kwargs['currency_queryset'] = Currency.objects.order_by('code')
        return kwargs

    def perform_action(self, form):
        data = form.cleaned_data
        marketing_payload = {
            key: value
            for key, value in {
                'headline': data.get('headline'),
                'description': data.get('description'),
                'price': data.get('price'),
                'currency': data.get('currency'),
            }.items()
            if value not in (None, '')
        }
        PromoteSaleProviderIntentionService.call(
            intention=self.get_intention(),
            opportunity_notes=data.get('opportunity_notes') or None,
            marketing_package_data=marketing_payload or None,
        )


class ProviderWithdrawView(ProviderIntentionMixin, WorkflowFormView):
    form_class = ProviderWithdrawForm
    success_message = 'Provider intention withdrawn.'

    def perform_action(self, form):
        WithdrawSaleProviderIntentionService.call(intention=self.get_intention(), **form.cleaned_data)


class SeekerIntentionCreateView(WorkflowFormView):
    form_class = SaleSeekerIntentionForm
    success_message = 'Seeker intention registered.'

    def perform_action(self, form):
        CreateSaleSeekerIntentionService.call(**form.cleaned_data)


class SeekerActivateView(SeekerIntentionMixin, WorkflowFormView):
    form_class = ConfirmationForm
    success_message = 'Seeker search activated.'

    def perform_action(self, form):
        ActivateSaleSeekerIntentionService.call(intention=self.get_intention())


class SeekerMandateView(SeekerIntentionMixin, WorkflowFormView):
    form_class = SeekerMandateForm
    success_message = 'Seeker mandate captured.'

    def perform_action(self, form):
        MandateSaleSeekerIntentionService.call(intention=self.get_intention(), **form.cleaned_data)


class SeekerAbandonView(SeekerIntentionMixin, WorkflowFormView):
    form_class = SeekerAbandonForm
    success_message = 'Seeker intention abandoned.'

    def perform_action(self, form):
        AbandonSaleSeekerIntentionService.call(intention=self.get_intention(), **form.cleaned_data)


class SeekerOpportunityCreateView(SeekerIntentionMixin, WorkflowFormView):
    form_class = SeekerOpportunityCreateForm
    success_message = 'Seeker opportunity created.'

    def perform_action(self, form):
        CreateSeekerOpportunityService.call(intention=self.get_intention(), **form.cleaned_data)


class ProviderOpportunityMixin:
    pk_url_kwarg = 'opportunity_id'

    def get_opportunity(self):
        return get_object_or_404(ProviderOpportunity, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['opportunity'] = self.get_opportunity()
        return context


class ValidationMixin:
    pk_url_kwarg = 'validation_id'

    def get_validation(self):
        return get_object_or_404(Validation, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['validation'] = self.get_validation()
        return context


class ValidationDocumentMixin:
    pk_url_kwarg = 'document_id'

    def get_document(self):
        return get_object_or_404(ValidationDocument, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['document'] = self.get_document()
        return context


class OpportunityValidateView(ProviderOpportunityMixin, WorkflowFormView):
    form_class = ConfirmationForm
    success_message = 'Opportunity moved into validation.'

    def perform_action(self, form):
        OpportunityValidateService.call(opportunity=self.get_opportunity())


class ValidationPresentView(ValidationMixin, WorkflowFormView):
    form_class = ValidationPresentForm
    success_message = 'Validation presented.'

    def perform_action(self, form):
        ValidationPresentService.call(validation=self.get_validation(), reviewer=form.cleaned_data['reviewer'])


class ValidationRejectView(ValidationMixin, WorkflowFormView):
    form_class = ValidationRejectForm
    success_message = 'Validation sent back to preparation.'

    def perform_action(self, form):
        ValidationRejectService.call(validation=self.get_validation(), notes=form.cleaned_data.get('notes'))


class ValidationAcceptView(ValidationMixin, WorkflowFormView):
    form_class = ConfirmationForm
    success_message = 'Validation accepted and opportunity published.'

    def perform_action(self, form):
        ValidationAcceptService.call(validation=self.get_validation())


class ValidationDocumentUploadView(ValidationMixin, WorkflowFormView):
    form_class = ValidationDocumentUploadForm
    success_message = 'Validation document uploaded.'

    def get_success_url(self):
        return reverse('workflow-dashboard') + '#providers-section'

    def perform_action(self, form):
        CreateValidationDocumentService.call(
            validation=self.get_validation(),
            name=form.cleaned_data['name'],
            document=form.cleaned_data['document'],
            uploaded_by=self.request.user if self.request.user.is_authenticated else None,
        )


class ValidationDocumentReviewView(ValidationDocumentMixin, WorkflowFormView):
    form_class = ValidationDocumentReviewForm
    success_message = 'Validation document reviewed.'

    def get_success_url(self):
        return reverse('workflow-dashboard') + '#providers-section'

    def perform_action(self, form):
        ReviewValidationDocumentService.call(
            document=self.get_document(),
            action=form.cleaned_data['action'],
            reviewer=self.request.user,
            comment=form.cleaned_data.get('comment'),
        )


class OperationCreateView(WorkflowFormView):
    form_class = OperationForm
    success_message = 'Operation created.'

    def perform_action(self, form):
        CreateOperationService.call(**form.cleaned_data)


class OperationMixin:
    pk_url_kwarg = 'operation_id'

    def get_operation(self):
        return get_object_or_404(Operation, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['operation'] = self.get_operation()
        return context


class OperationReinforceView(OperationMixin, WorkflowFormView):
    form_class = ConfirmationForm
    success_message = 'Operation reinforced.'

    def perform_action(self, form):
        OperationReinforceService.call(operation=self.get_operation())


class OperationCloseView(OperationMixin, WorkflowFormView):
    form_class = ConfirmationForm
    success_message = 'Operation closed.'

    def perform_action(self, form):
        OperationCloseService.call(operation=self.get_operation())


class OperationLoseView(OperationMixin, WorkflowFormView):
    form_class = OperationLoseForm
    success_message = 'Operation marked as lost.'

    def perform_action(self, form):
        OperationLoseService.call(operation=self.get_operation(), **form.cleaned_data)


class TokkoSyncRunView(LoginRequiredMixin, View):
    login_url = '/admin/login/'

    def post(self, request):
        processed = sync_tokkobroker_registry()
        messages.success(request, f'Synced {processed} Tokkobroker properties.')
        return redirect('workflow-dashboard')

    def get(self, request):  # pragma: no cover - defensive; redirect to avoid GET usage
        return redirect('workflow-dashboard')


class TokkoSyncEnqueueView(LoginRequiredMixin, View):
    login_url = '/admin/login/'

    def post(self, request):
        message = sync_tokkobroker_properties_task.send()
        messages.info(request, f'Tokkobroker sync enqueued (message ID: {message.message_id}).')
        return redirect('workflow-dashboard')

    def get(self, request):  # pragma: no cover
        return redirect('workflow-dashboard')


class TokkoClearView(LoginRequiredMixin, View):
    login_url = '/admin/login/'

    def post(self, request):
        deleted, _ = TokkobrokerProperty.objects.all().delete()
        messages.warning(request, f'Cleared {deleted} Tokkobroker properties.')
        return redirect('workflow-dashboard')

    def get(self, request):  # pragma: no cover
        return redirect('workflow-dashboard')


class ObjectTransitionHistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'workflow/transition_history.html'
    login_url = '/admin/login/'

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
        ).order_by('-occurred_at')
        context.update(
            object=obj,
            transitions=transitions,
        )
        return context
