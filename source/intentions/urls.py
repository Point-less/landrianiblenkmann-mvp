"""URL routes for provider/seeker intentions."""

from django.urls import path

from core import views as workflow_views

urlpatterns = [
    path('intentions/provider/new/', workflow_views.ProviderIntentionCreateView.as_view(), name='provider-intention-create'),
    path('intentions/provider/<int:intention_id>/deliver-valuation/', workflow_views.DeliverValuationView.as_view(), name='provider-deliver-valuation'),
    path('intentions/provider/<int:intention_id>/start-contract/', workflow_views.ProviderContractView.as_view(), name='provider-start-contract'),
    path('intentions/provider/<int:intention_id>/promote/', workflow_views.ProviderPromotionView.as_view(), name='provider-promote'),
    path('intentions/provider/<int:intention_id>/withdraw/', workflow_views.ProviderWithdrawView.as_view(), name='provider-withdraw'),
    path('intentions/seeker/new/', workflow_views.SeekerIntentionCreateView.as_view(), name='seeker-intention-create'),
    path('intentions/seeker/<int:intention_id>/activate/', workflow_views.SeekerActivateView.as_view(), name='seeker-activate'),
    path('intentions/seeker/<int:intention_id>/mandate/', workflow_views.SeekerMandateView.as_view(), name='seeker-mandate'),
    path('intentions/seeker/<int:intention_id>/abandon/', workflow_views.SeekerAbandonView.as_view(), name='seeker-abandon'),
    path('intentions/seeker/<int:intention_id>/create-opportunity/', workflow_views.SeekerOpportunityCreateView.as_view(), name='seeker-create-opportunity'),
]

