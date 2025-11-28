"""Users app URL routing - authentication and sesame magic link endpoints."""

from django.urls import path
from sesame.views import LoginView as SesameLoginView

from users import views

urlpatterns = [
    # Custom login page with both password and passwordless options
    path('login/', views.CustomLoginView.as_view(), name='login'),
    # Request magic link (passwordless)
    path('request-magic-link/', views.RequestMagicLinkView.as_view(), name='request-magic-link'),
    # Sesame magic link login endpoint
    path('sesame/login/', SesameLoginView.as_view(), name='sesame-login'),
    # Logout
    path('logout/', views.LogoutView.as_view(), name='logout'),
]
