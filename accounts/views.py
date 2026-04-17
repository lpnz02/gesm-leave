from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .forms import RegisterForm
from .models import User
from django.contrib.auth import authenticate, login, logout
from .forms import RegisterForm, LoginForm
from django.http import HttpResponse
from leaves.models import LeaveBalance



class Welcome(View):
    def get(self, request):
        return render(request, 'accounts/welcome.html')

class RegisterView(View):
    def get(self, request):
        form = RegisterForm()
        return render(request, 'accounts/register.html', {'form': form})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.is_approved = False
            user.is_email_verified = False

            # si HoD et nouveau département
            if form.cleaned_data['role'] == 'head_of_department':
                new_dept_name = form.cleaned_data.get('new_department')
                if new_dept_name:
                    from .models import Department
                    department = Department.objects.create(name=new_dept_name)
                    user.department = department

            user.save()

            verification_link = f"http://127.0.0.1:8000/verify-email/{user.email_verification_token}/"
            send_mail(
                subject='Verify your email',
                message=f'Click here to verify your email: {verification_link}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
            return redirect('pending')
        return render(request, 'accounts/register.html', {'form': form})


class LoginView(View):
    def get(self, request):
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
                return redirect('welcome')
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

            # debug — affiche les HR trouvés
            hr_users = User.objects.filter(role='hr')
            print(f"HR users found: {hr_users.count()}")
            for hr in hr_users:
                print(f"Sending to HR: {hr.email}")
                send_mail(
                    subject='New account pending approval',
                    message=f'{user.first_name} {user.last_name} ({user.role}) is waiting for approval.\n\nApprove: http://127.0.0.1:8000/approve-user/{user.id}/\nReject: http://127.0.0.1:8000/reject-user/{user.id}/',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[hr.email],
                )
            return render(request, 'accounts/email_verified.html')
        
        except User.DoesNotExist:
            messages.error(request, 'Invalid verification link.')
            return redirect('register')
            
 
class ApproveUserView(View):
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            user.is_active = True
            user.is_approved = True
            user.save()

            # créer les balances par défaut
            if user.role == 'employee':
                defaults = {
                    'vacation_leave': 15,
                    'sick_leave': 15,
                    'bereavement_leave': 5,
                    'emergency_leave': 3,
                    'maternity_paternity_leave': 0,
                    'others': 0,
                }
            elif user.role == 'teacher':
                defaults = {
                    'vacation_leave': 30,
                    'sick_leave': 0,
                    'bereavement_leave': 0,
                    'emergency_leave': 0,
                    'maternity_paternity_leave': 0,
                    'others': 0,
                }
            else:
                defaults = {}

            for leave_type, total in defaults.items():
                LeaveBalance.objects.get_or_create(
                    user=user,
                    leave_type=leave_type,
                    defaults={
                        'total_days': total,
                        'days_used': 0,
                        'days_remaining': total,
                    }
                )

            send_mail(
                subject='Account Approved',
                message=f'Hello {user.first_name}, your account has been approved! You can now login at http://127.0.0.1:8000/login/',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
            return HttpResponse("User approved successfully.")
        
        except User.DoesNotExist:
            return HttpResponse("User not found.")

class RejectUserView(View):
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            user.delete()

            send_mail(
                subject='Account Rejected',
                message=f'Hello {user.first_name}, unfortunately your account request has been rejected. Please contact HR for more information.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
            return HttpResponse("User rejected and deleted.")
        
        except User.DoesNotExist:
            return HttpResponse("User not found.")