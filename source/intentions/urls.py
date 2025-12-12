"""URL routes for provider/seeker intentions."""

from django.urls import path

from core import views as workflow_views

urlpatterns = [
    path('provider/new/', workflow_views.ProviderIntentionCreateView.as_view(), name='provider-intention-create'),
    path('provider/<int:intention_id>/deliver-valuation/', workflow_views.DeliverValuationView.as_view(), name='provider-deliver-valuation'),
    path('provider/<int:intention_id>/promote/', workflow_views.ProviderPromotionView.as_view(), name='provider-promote'),
    path('provider/<int:intention_id>/withdraw/', workflow_views.ProviderWithdrawView.as_view(), name='provider-withdraw'),
    path('seeker/new/', workflow_views.SeekerIntentionCreateView.as_view(), name='seeker-intention-create'),
    path('seeker/<int:intention_id>/create-opportunity/', workflow_views.SeekerOpportunityCreateView.as_view(), name='seeker-create-opportunity'),
    path('seeker/<int:intention_id>/abandon/', workflow_views.SeekerAbandonView.as_view(), name='seeker-abandon'),
]
