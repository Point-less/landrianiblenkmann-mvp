"""URL routes for provider opportunities, validations, marketing publications, and operations."""

from django.urls import path

from opportunities import views as opp_views

urlpatterns = [
    # Provider opportunities & validations
    path('validations/<int:validation_id>/', opp_views.ValidationDetailView.as_view(), name='validation-detail'),
    path('validations/<int:validation_id>/present/', opp_views.ValidationPresentView.as_view(), name='validation-present'),
    path('validations/<int:validation_id>/reject/', opp_views.ValidationRejectView.as_view(), name='validation-reject'),
    path('validations/<int:validation_id>/accept/', opp_views.ValidationAcceptView.as_view(), name='validation-accept'),
    path('validations/<int:validation_id>/documents/upload/', opp_views.ValidationDocumentUploadView.as_view(), name='validation-document-upload'),
    path('validations/<int:validation_id>/documents/upload-additional/', opp_views.ValidationAdditionalDocumentUploadView.as_view(), name='validation-additional-document-upload'),
    path('validation-documents/<int:document_id>/review/', opp_views.ValidationDocumentReviewView.as_view(), name='validation-document-review'),
    # Marketing publications
    path('provider/<int:opportunity_id>/marketing-publications/new/', opp_views.MarketingPublicationCreateView.as_view(), name='marketing-publication-create'),
    path('provider/<int:opportunity_id>/marketing-publications/', opp_views.MarketingPublicationDetailView.as_view(), name='marketing-publication-detail'),
    path('marketing-publications/<int:package_id>/edit/', opp_views.MarketingPublicationUpdateView.as_view(), name='marketing-publication-edit'),
    path('marketing-publications/<int:package_id>/activate/', opp_views.MarketingPublicationActivateView.as_view(), name='marketing-publication-activate'),
    path('marketing-publications/<int:package_id>/pause/', opp_views.MarketingPublicationPauseView.as_view(), name='marketing-publication-pause'),
    path('marketing-publications/<int:package_id>/release/', opp_views.MarketingPublicationReleaseView.as_view(), name='marketing-publication-release'),
    # Operations

    path('operations/<int:operation_id>/reinforce/', opp_views.OperationReinforceView.as_view(), name='operation-reinforce'),
    path('operations/<int:operation_id>/close/', opp_views.OperationCloseView.as_view(), name='operation-close'),
    path('operations/<int:operation_id>/lose/', opp_views.OperationLoseView.as_view(), name='operation-lose'),
    # Operation Agreements
    path('operation-agreements/new/', opp_views.OperationAgreementCreateView.as_view(), name='agreement-create'),
    path('operation-agreements/<int:agreement_id>/agree/', opp_views.AgreeOperationAgreementView.as_view(), name='agreement-agree'),
    path('operation-agreements/<int:agreement_id>/sign/', opp_views.SignOperationAgreementView.as_view(), name='agreement-sign'),
    path('operation-agreements/<int:agreement_id>/revoke/', opp_views.RevokeOperationAgreementView.as_view(), name='agreement-revoke'),
    path('operation-agreements/<int:agreement_id>/cancel/', opp_views.CancelOperationAgreementView.as_view(), name='agreement-cancel'),
]
