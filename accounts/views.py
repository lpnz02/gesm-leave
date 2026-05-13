from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .forms import RegisterForm, LoginForm
from .models import User, Department
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from leaves.models import LeaveBalance


class Welcome(View):
    def get(self, request):
        return render(request, 'accounts/welcome.html')


class RegisterView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        form = RegisterForm()
        return render(request, 'accounts/register.html', {'form': form})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.is_approved = False
            user.is_email_verified = False
            user.save()

            # déclencher la logique département après save
            dept = form.cleaned_data.get('department')
            if dept and user.role == 'head_of_department':
                dept.head = user
                dept.save()
                for teacher in User.objects.filter(department=dept, role='teacher'):
                    teacher.superior = user
                    teacher.save()
            elif dept and user.role == 'teacher':
                if dept.head:
                    user.superior = dept.head
                    user.save()

            verification_link = f"http://127.0.0.1:8000/verify-email/{user.email_verification_token}/"
            send_mail(
                subject='Verify your email — GESM Leave Management',
                message=f'Hello {user.first_name},\n\nClick here to verify your email:\n{verification_link}\n\nGESM Leave Management',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
            return redirect('pending')
        return render(request, 'accounts/register.html', {'form': form})


class LoginView(View):
    def get(self, request):
        # si déjà connecté → rediriger vers dashboard
        if request.user.is_authenticated:
            return redirect('dashboard')
        form = LoginForm()
        return render(request, 'accounts/login.html', {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')  # ← dashboard, pas welcome
            else:
                messages.error(request, 'Invalid username or password.')
        return render(request, 'accounts/login.html', {'form': form})


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('login')


class PendingView(View):
    def get(self, request):
        return render(request, 'accounts/pending.html')


class VerifyEmailView(View):
    def get(self, request, token):
        try:
            user = User.objects.get(email_verification_token=token)
            if user.is_email_verified:
                messages.info(request, 'Email already verified.')
                return redirect('login')

            user.is_email_verified = True
            user.save()

            # notifier le HR — sans liens approve/reject, juste une info
            hr_users = User.objects.filter(role='hr', is_active=True)
            for hr in hr_users:
                send_mail(
                    subject='New account pending approval — GESM',
                    message=f'Hello,\n\n{user.first_name} {user.last_name} ({user.get_role_display() if hasattr(user, "get_role_display") else user.role}) has registered and is waiting for your approval.\n\nPlease log in to the GESM Leave Management System to approve or reject:\nhttp://127.0.0.1:8000/dashboard/\n\nGESM Leave Management',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[hr.email],
                )
            return render(request, 'accounts/email_verified.html')

        except User.DoesNotExist:
            messages.error(request, 'Invalid verification link.')
            return redirect('register')


class ApproveUserView(LoginRequiredMixin, View):
    def get(self, request, user_id):
        if request.user.role != 'hr':
            return redirect('dashboard')
        try:
            user = User.objects.get(id=user_id)
            user.is_active = True
            user.is_approved = True
            user.save()

            if user.role == 'admin':
                defaults = {
                    'vacation_leave': 15,
                    'sick_leave': 15,
                    'bereavement_leave': 5,
                    'emergency_leave': 3,
                    'maternity_paternity_leave': 0,
                    'others': 0,
                }
                for leave_type, total in defaults.items():
                    LeaveBalance.objects.get_or_create(
                        user=user,
                        leave_type=leave_type,
                        defaults={
                            'total_days': total,
                            'days_used': 0,
                            'days_remaining': total,
                            'carried_over': 0,
                        }
                    )

            elif user.role in ['teacher', 'head_of_department', 'head_of_school']:
                # une seule balance globale de 30j
                LeaveBalance.objects.get_or_create(
                    user=user,
                    leave_type='vacation_leave',
                    defaults={
                        'total_days': 30,
                        'days_used': 0,
                        'days_remaining': 30,
                        'carried_over': 0,
                    }
                )

            send_mail(
                subject='Account Approved — GESM Leave Management',
                message=f'Hello {user.first_name},\n\nYour account has been approved! You can now log in at:\nhttp://127.0.0.1:8000/login/\n\nGESM Leave Management',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
            return redirect('dashboard')

        except User.DoesNotExist:
            return HttpResponse("User not found.")

class RejectUserView(LoginRequiredMixin, View):
    def get(self, request, user_id):
        if request.user.role != 'hr':
            return redirect('dashboard')
        try:
            user = User.objects.get(id=user_id)
            email = user.email
            first_name = user.first_name
            user.delete()

            send_mail(
                subject='Account Rejected — GESM Leave Management',
                message=f'Hello {first_name},\n\nUnfortunately your account request has been rejected.\nPlease contact HR for more information.\n\nGESM Leave Management',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
            )
            return redirect('dashboard')

        except User.DoesNotExist:
            return HttpResponse("User not found.")
        

from django.contrib.auth import update_session_auth_hash

class ChangePasswordView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'accounts/change_password.html')

    def post(self, request):
        current_password = request.POST.get('current_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')

        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return render(request, 'accounts/change_password.html')

        if new_password1 != new_password2:
            messages.error(request, 'New passwords do not match.')
            return render(request, 'accounts/change_password.html')

        if len(new_password1) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return render(request, 'accounts/change_password.html')

        request.user.set_password(new_password1)
        request.user.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, 'Password changed successfully!')
        return redirect('dashboard')