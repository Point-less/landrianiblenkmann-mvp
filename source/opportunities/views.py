from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic.edit import FormView

from core.mixins import PermissionedViewMixin
from core.forms import ConfirmationForm
from opportunities.forms import (
    MarketingPackageForm,
    OperationLoseForm,
    OperationReinforceForm,
    OperationAgreementCreateForm,
    SignOperationAgreementForm,
    CancelOperationAgreementForm,
    ValidationDocumentReviewForm,
    ValidationDocumentUploadForm,
    ValidationPresentForm,
    ValidationRejectForm,
    ValidationAdditionalDocumentUploadForm,
)
from opportunities.models import (
    MarketingPackage,
    MarketingPublication,
    Operation,
    OperationAgreement,
    ProviderOpportunity,
    Validation,
    ValidationDocument,
)
from utils.services import S
from utils.authorization import (
    PROVIDER_OPPORTUNITY_PUBLISH,
    OPERATION_REINFORCE,
    OPERATION_CLOSE,
    OPERATION_LOSE,
    AGREEMENT_CREATE,
    AGREEMENT_AGREE,
    AGREEMENT_SIGN,
    AGREEMENT_REVOKE,
    AGREEMENT_CANCEL,
    PROVIDER_OPPORTUNITY_VIEW,
)


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
            raise ValidationError("Opportunity is not in marketing stage")
        return opportunity


class MarketingPackageMixin:
    pk_url_kwarg = 'package_id'

    def get_package(self):
        return get_object_or_404(MarketingPackage, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['package'] = self.get_package()
        return context


class MarketingPackageHistoryView(ProviderOpportunityMixin, PermissionedViewMixin, LoginRequiredMixin, FormView):
    """Detail page for an opportunity's marketing packages and their revisions."""

    template_name = "workflow/marketing_package_history.html"
    form_class = ConfirmationForm  # unused; FormView for convenience of template context
    required_action = PROVIDER_OPPORTUNITY_VIEW

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        opportunity = context["opportunity"]
        packages = S.opportunities.MarketingPackagesWithRevisionsForOpportunityQuery(
            actor=self.request.user,
            opportunity=opportunity,
        )
        publication = opportunity.marketing_publication
        current_package = publication.package
        revisions = packages.exclude(pk=current_package.pk)

        context["publication"] = publication
        context["current_package"] = current_package
        context["revisions"] = revisions
        context["current_url"] = self.request.get_full_path()
        return context

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'marketing-packages'})


class ValidationMixin:
    pk_url_kwarg = 'validation_id'

    def get_validation(self):
        return get_object_or_404(Validation, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['validation'] = self.get_validation()
        return context


class ValidationDetailView(ValidationMixin, LoginRequiredMixin, PermissionedViewMixin, FormView):
    template_name = 'workflow/validation_detail.html'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH
    form_class = ValidationPresentForm  # dummy

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        validation = context['validation']
        context['required_documents'] = validation.required_documents_status()
        context['custom_documents'] = validation.custom_documents()
        context['summary'] = validation.document_status_summary()
        return context


class ValidationPresentView(ValidationMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
    form_class = ValidationPresentForm
    success_message = 'Validation presented.'
    form_title = 'Present validation'
    submit_label = 'Present'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def perform_action(self, form):
        S.opportunities.ValidationPresentService(validation=self.get_validation())

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'provider-validations'})


class ValidationRejectView(ValidationMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
    form_class = ValidationRejectForm
    success_message = 'Validation sent back to preparation.'
    form_title = 'Revoke validation'
    form_description = 'Send the validation back to preparing and optionally add notes.'
    submit_label = 'Revoke'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def perform_action(self, form):
        S.opportunities.ValidationRejectService(validation=self.get_validation(), notes=form.cleaned_data.get('notes'))

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'provider-validations'})


class ValidationAcceptView(ValidationMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
    form_class = ConfirmationForm
    success_message = 'Validation accepted and opportunity published.'
    form_title = 'Accept validation'
    submit_label = 'Accept'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def perform_action(self, form):
        S.opportunities.ValidationAcceptService(validation=self.get_validation())

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'provider-validations'})


class ValidationDocumentUploadView(ValidationMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
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

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'provider-validations'})


class ValidationAdditionalDocumentUploadView(ValidationMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
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

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'provider-validations'})


class ValidationDocumentReviewView(PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
    pk_url_kwarg = 'document_id'
    form_class = ValidationDocumentReviewForm
    success_message = 'Validation document reviewed.'
    form_title = 'Review document'
    submit_label = 'Submit review'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def get_document(self):
        return get_object_or_404(ValidationDocument, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['document'] = self.get_document()
        return context

    def perform_action(self, form):
        S.opportunities.ReviewValidationDocumentService(
            document=self.get_document(),
            action=form.cleaned_data['action'],
            reviewer=self.request.user,
            comment=form.cleaned_data.get('comment'),
        )

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'provider-validations'})


class MarketingPackageCreateView(MarketingOpportunityMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
    form_class = MarketingPackageForm
    success_message = 'Marketing package created.'
    success_url = reverse_lazy('workflow-dashboard-section', kwargs={'section': 'marketing-packages'})
    form_title = 'Create marketing package'
    submit_label = 'Create package'
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def perform_action(self, form):
        S.opportunities.MarketingPackageCreateService(opportunity=self.get_opportunity(), **form.cleaned_data)

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)


class MarketingPackageUpdateView(MarketingPackageMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
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

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        # Stay on the same package after saving edits
        return self.request.get_full_path()


class MarketingPackageActionView(MarketingPackageMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
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

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)


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


class OperationReinforceView(OperationMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
    form_class = OperationReinforceForm
    success_message = 'Operation reinforced.'
    form_title = 'Reinforce operation'
    submit_label = 'Reinforce'
    required_action = OPERATION_REINFORCE

    def perform_action(self, form):
        S.opportunities.OperationReinforceService(operation=self.get_operation(), **form.cleaned_data)

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'operations'})


class OperationCloseView(OperationMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
    form_class = ConfirmationForm
    success_message = 'Operation closed.'
    form_title = 'Close operation'
    submit_label = 'Close'
    required_action = OPERATION_CLOSE

    def perform_action(self, form):
        S.opportunities.OperationCloseService(operation=self.get_operation())

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'operations'})


class OperationLoseView(OperationMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'workflow/form.html'
    form_class = OperationLoseForm
    success_message = 'Operation marked as lost.'
    form_title = 'Mark operation as lost'
    submit_label = 'Mark lost'
    required_action = OPERATION_LOSE

    def perform_action(self, form):
        S.opportunities.OperationLoseService(operation=self.get_operation(), **form.cleaned_data)

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('workflow-dashboard-section', kwargs={'section': 'operations'})


class OperationAgreementMixin:
    pk_url_kwarg = 'agreement_id'

    def get_agreement(self):
        return get_object_or_404(OperationAgreement, pk=self.kwargs[self.pk_url_kwarg])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agreement'] = self.get_agreement()
        return context


class OperationAgreementCreateView(PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
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
        S.opportunities.CreateOperationAgreementService(**form.cleaned_data, actor=self.request.user)

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)


class AgreeOperationAgreementView(OperationAgreementMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    form_class = ConfirmationForm
    success_message = 'Agreement confirmed.'
    form_title = 'Confirm Agreement'
    submit_label = 'Agree'
    success_url = reverse_lazy('workflow-dashboard-section', kwargs={'section': 'operation-agreements'})
    required_action = AGREEMENT_AGREE

    def perform_action(self, form):
        S.opportunities.AgreeOperationAgreementService(agreement=self.get_agreement())

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)


class RevokeOperationAgreementView(OperationAgreementMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
    form_class = ConfirmationForm
    success_message = 'Agreement revoked.'
    form_title = 'Revoke Agreement'
    submit_label = 'Revoke'
    success_url = reverse_lazy('workflow-dashboard-section', kwargs={'section': 'operation-agreements'})
    required_action = AGREEMENT_REVOKE

    def perform_action(self, form):
        S.opportunities.RevokeOperationAgreementService(agreement=self.get_agreement())

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)


class CancelOperationAgreementView(OperationAgreementMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
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

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)


class SignOperationAgreementView(OperationAgreementMixin, PermissionedViewMixin, LoginRequiredMixin, SuccessMessageMixin, FormView):
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

    def form_valid(self, form):
        try:
            self.perform_action(form)
        except ValidationError:
            return self.form_invalid(form)
        return super().form_valid(form)


__all__ = [
    "ValidationDetailView",
    "ValidationPresentView",
    "ValidationRejectView",
    "ValidationAcceptView",
    "ValidationDocumentUploadView",
    "ValidationAdditionalDocumentUploadView",
    "ValidationDocumentReviewView",
    "MarketingPackageCreateView",
    "MarketingPackageUpdateView",
    "MarketingPackageActivateView",
    "MarketingPackageReleaseView",
    "MarketingPackagePauseView",
    "OperationReinforceView",
    "OperationCloseView",
    "OperationLoseView",
    "OperationAgreementCreateView",
    "AgreeOperationAgreementView",
    "SignOperationAgreementView",
    "RevokeOperationAgreementView",
    "CancelOperationAgreementView",
]
