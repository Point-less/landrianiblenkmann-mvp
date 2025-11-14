from django.urls import path

from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='workflow-dashboard', permanent=False)),
    path('dashboard/', views.DashboardSectionView.as_view(), name='workflow-dashboard'),
    path('dashboard/<str:section>/', views.DashboardSectionView.as_view(), name='workflow-dashboard-section'),
    path('health/', views.health_check, name='health-check'),
    path('trigger-log/', views.trigger_log, name='trigger-log'),
    path('agents/new/', views.AgentCreateView.as_view(), name='agent-create'),
    path('agents/<int:agent_id>/edit/', views.AgentUpdateView.as_view(), name='agent-edit'),
    path('contacts/new/', views.ContactCreateView.as_view(), name='contact-create'),
    path('contacts/<int:contact_id>/edit/', views.ContactUpdateView.as_view(), name='contact-edit'),
    path('properties/new/', views.PropertyCreateView.as_view(), name='property-create'),
    path('properties/<int:property_id>/edit/', views.PropertyUpdateView.as_view(), name='property-edit'),
    path('intentions/provider/new/', views.ProviderIntentionCreateView.as_view(), name='provider-intention-create'),
    path('intentions/provider/<int:intention_id>/deliver-valuation/', views.DeliverValuationView.as_view(), name='provider-deliver-valuation'),
    path('intentions/provider/<int:intention_id>/start-contract/', views.ProviderContractView.as_view(), name='provider-start-contract'),
    path('intentions/provider/<int:intention_id>/promote/', views.ProviderPromotionView.as_view(), name='provider-promote'),
    path('intentions/provider/<int:intention_id>/withdraw/', views.ProviderWithdrawView.as_view(), name='provider-withdraw'),
    path('intentions/seeker/new/', views.SeekerIntentionCreateView.as_view(), name='seeker-intention-create'),
    path('intentions/seeker/<int:intention_id>/activate/', views.SeekerActivateView.as_view(), name='seeker-activate'),
    path('intentions/seeker/<int:intention_id>/mandate/', views.SeekerMandateView.as_view(), name='seeker-mandate'),
    path('intentions/seeker/<int:intention_id>/abandon/', views.SeekerAbandonView.as_view(), name='seeker-abandon'),
    path('intentions/seeker/<int:intention_id>/create-opportunity/', views.SeekerOpportunityCreateView.as_view(), name='seeker-create-opportunity'),
    path('opportunities/provider/<int:opportunity_id>/validate/', views.OpportunityValidateView.as_view(), name='provider-opportunity-validate'),
    path('validations/<int:validation_id>/present/', views.ValidationPresentView.as_view(), name='validation-present'),
    path('validations/<int:validation_id>/reject/', views.ValidationRejectView.as_view(), name='validation-reject'),
    path('validations/<int:validation_id>/accept/', views.ValidationAcceptView.as_view(), name='validation-accept'),
    path('validations/<int:validation_id>/documents/upload/', views.ValidationDocumentUploadView.as_view(), name='validation-document-upload'),
    path('validation-documents/<int:document_id>/review/', views.ValidationDocumentReviewView.as_view(), name='validation-document-review'),
    path('operations/new/', views.OperationCreateView.as_view(), name='operation-create'),
    path('operations/<int:operation_id>/reinforce/', views.OperationReinforceView.as_view(), name='operation-reinforce'),
    path('operations/<int:operation_id>/close/', views.OperationCloseView.as_view(), name='operation-close'),
    path('operations/<int:operation_id>/lose/', views.OperationLoseView.as_view(), name='operation-lose'),
    path('integrations/tokko/sync-now/', views.TokkoSyncRunView.as_view(), name='integration-tokko-sync-now'),
    path('integrations/tokko/enqueue/', views.TokkoSyncEnqueueView.as_view(), name='integration-tokko-sync-enqueue'),
    path('integrations/tokko/clear/', views.TokkoClearView.as_view(), name='integration-tokko-clear'),
    path(
        'transitions/<str:app_label>/<str:model>/<int:object_id>/',
        views.ObjectTransitionHistoryView.as_view(),
        name='transition-history',
    ),
]
