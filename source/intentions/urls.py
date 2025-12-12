"""URL routes for provider/seeker intentions."""

from django.urls import path

from intentions import views as intention_views

urlpatterns = [
    path('provider/new/', intention_views.ProviderIntentionCreateView.as_view(), name='provider-intention-create'),
    path('provider/<int:intention_id>/deliver-valuation/', intention_views.DeliverValuationView.as_view(), name='provider-deliver-valuation'),
    path('provider/<int:intention_id>/promote/', intention_views.ProviderPromotionView.as_view(), name='provider-promote'),
    path('provider/<int:intention_id>/withdraw/', intention_views.ProviderWithdrawView.as_view(), name='provider-withdraw'),
    path('seeker/new/', intention_views.SeekerIntentionCreateView.as_view(), name='seeker-intention-create'),
    path('seeker/<int:intention_id>/create-opportunity/', intention_views.SeekerOpportunityCreateView.as_view(), name='seeker-create-opportunity'),
    path('seeker/<int:intention_id>/abandon/', intention_views.SeekerAbandonView.as_view(), name='seeker-abandon'),
]
