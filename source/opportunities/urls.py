"""URL routes for provider opportunities, validations, marketing packages, and operations."""

from django.urls import path

from core import views as workflow_views

urlpatterns = [
    # Provider opportunities & validations
    path('provider/<int:opportunity_id>/validate/', workflow_views.OpportunityValidateView.as_view(), name='provider-opportunity-validate'),
    path('validations/<int:validation_id>/present/', workflow_views.ValidationPresentView.as_view(), name='validation-present'),
    path('validations/<int:validation_id>/reject/', workflow_views.ValidationRejectView.as_view(), name='validation-reject'),
    path('validations/<int:validation_id>/accept/', workflow_views.ValidationAcceptView.as_view(), name='validation-accept'),
    path('validations/<int:validation_id>/documents/upload/', workflow_views.ValidationDocumentUploadView.as_view(), name='validation-document-upload'),
    path('validation-documents/<int:document_id>/review/', workflow_views.ValidationDocumentReviewView.as_view(), name='validation-document-review'),
    # Marketing packages
    path('provider/<int:opportunity_id>/marketing-packages/new/', workflow_views.MarketingPackageCreateView.as_view(), name='marketing-package-create'),
    path('marketing-packages/<int:package_id>/edit/', workflow_views.MarketingPackageUpdateView.as_view(), name='marketing-package-edit'),
    path('marketing-packages/<int:package_id>/activate/', workflow_views.MarketingPackageActivateView.as_view(), name='marketing-package-activate'),
    path('marketing-packages/<int:package_id>/pause/', workflow_views.MarketingPackagePauseView.as_view(), name='marketing-package-pause'),
    path('marketing-packages/<int:package_id>/release/', workflow_views.MarketingPackageReleaseView.as_view(), name='marketing-package-release'),
    # Operations
    path('operations/new/', workflow_views.OperationCreateView.as_view(), name='operation-create'),
    path('operations/<int:operation_id>/reinforce/', workflow_views.OperationReinforceView.as_view(), name='operation-reinforce'),
    path('operations/<int:operation_id>/close/', workflow_views.OperationCloseView.as_view(), name='operation-close'),
    path('operations/<int:operation_id>/lose/', workflow_views.OperationLoseView.as_view(), name='operation-lose'),
]

