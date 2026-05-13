from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.contrib.auth.views import PasswordResetConfirmView
from django.db.models.signals import post_save

def notify_hr_password_reset(sender, request, user, **kwargs):
    from accounts.models import User
    from django.core.mail import send_mail
    from django.conf import settings
    hr_users = User.objects.filter(role='hr', is_active=True)
    for hr in hr_users:
        send_mail(
            subject='Password Reset Notification',
            message=f'{user.first_name} {user.last_name} ({user.email}) has reset their password.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[hr.email],
        )