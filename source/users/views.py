"""User authentication views - login with password and passwordless options."""

from urllib.parse import urlencode

from django.contrib.auth import views as auth_views
from django.core.mail import send_mail
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView
from django import forms
from django.contrib import messages
import sesame.utils
from sesame import settings as sesame_settings

from users.models import User
from utils.services import S


class EmailForm(forms.Form):
    """Form for requesting a magic link via email."""
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter your email'})
    )


class CustomLoginView(auth_views.LoginView):
    """Custom login view with both password and passwordless options."""
    template_name = 'users/login.html'
    redirect_authenticated_user = True
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['show_passwordless'] = True
        return context


class RequestMagicLinkView(FormView):
    """View to request a magic link for passwordless login."""
    template_name = 'users/request_magic_link.html'
    form_class = EmailForm
    success_url = reverse_lazy('login')
    
    def form_valid(self, form):
        email = form.cleaned_data['email']
        
        try:
            user = S.users.ActiveUserByEmailQuery(email=email)
            
            # Generate magic link using sesame
            token = sesame.utils.get_token(user)
            token_param = sesame_settings.TOKEN_NAME
            query_string = urlencode({token_param: token})
            magic_link = self.request.build_absolute_uri(
                f"{reverse('sesame-login')}?{query_string}"
            )
            
            # Send email (will be printed to console in development)
            send_mail(
                subject='Your Login Link',
                message=f'Click here to log in: {magic_link}\n\nThis link will expire in 5 minutes and can only be used once.',
                from_email='noreply@example.com',
                recipient_list=[email],
                fail_silently=False,
            )
            
            messages.success(
                self.request,
                'A magic link has been sent to your email. Please check your console (development mode).'
            )
        except User.DoesNotExist:
            # Don't reveal if the user exists or not for security
            messages.success(
                self.request,
                'If an account with that email exists, a login link has been sent.'
            )
        
        return super().form_valid(form)


class LogoutView(auth_views.LogoutView):
    """Logout view redirects to the login screen."""
    next_page = reverse_lazy('login')


