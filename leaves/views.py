from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import EmailMessage
from django.conf import settings
from .forms import LeaveRequestForm
from .models import Leave, LeaveBalance
from accounts.models import User


class SubmitLeaveView(LoginRequiredMixin, View):
    def get(self, request):
        form = LeaveRequestForm()
        return render(request, 'leaves/submit_leave.html', {'form': form})

    def post(self, request):
        form = LeaveRequestForm(request.POST, request.FILES)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.user = request.user
            leave.half_day = request.POST.get('half_day', 'none')
            pdf_file = request.FILES.get('pdf_attachment')

            if request.user.role == 'teacher':
                leave.status = 'pending_hod'
                if pdf_file:
                    leave.pdf_attachment = pdf_file
                leave.save()
                superior = request.user.superior
                if superior:
                    self.send_notification_email(leave, superior, pdf_file)

            elif request.user.role == 'admin':
                leave.status = 'pending_hoa'
                if pdf_file:
                    leave.pdf_attachment = pdf_file
                leave.save()
                for hoa in User.objects.filter(role='head_of_admin'):
                    self.send_notification_email(leave, hoa, pdf_file)

            elif request.user.role == 'hr':
                leave.status = 'pending_hoa'
                if pdf_file:
                    leave.pdf_attachment = pdf_file
                leave.save()
                for hoa in User.objects.filter(role='head_of_admin'):
                    self.send_notification_email(leave, hoa, pdf_file)

            elif request.user.role == 'head_of_department':
                leave.status = 'pending_hos'
                if pdf_file:
                    leave.pdf_attachment = pdf_file
                leave.save()
                for hos in User.objects.filter(role='head_of_school'):
                    self.send_notification_email(leave, hos, pdf_file)

            return redirect('leave_submitted')

        return render(request, 'leaves/submit_leave.html', {'form': form})

    def send_notification_email(self, leave, recipient, pdf_file=None):
        # formatage half day pour l'email
        if leave.half_day == 'morning':
            duration = 'Morning only (half day)'
        elif leave.half_day == 'afternoon':
            duration = 'Afternoon only (half day)'
        else:
            duration = 'Full day(s)'

        email = EmailMessage(
            subject=f'New Leave Request — {leave.user.first_name} {leave.user.last_name}',
            body=(
                f'Hello,\n\n'
                f'{leave.user.first_name} {leave.user.last_name} has submitted a leave request.\n\n'
                f'Leave Type: {leave.leave_type.replace("_", " ").title()}\n'
                f'Duration: {duration}\n'
                f'From: {leave.start_leave}\n'
                f'To: {leave.end_leave}\n'
                f'Reason: {leave.reason_for_leave}\n\n'
                f'Please log in to your dashboard to approve or reject this request.\n\n'
                f'GESM Leave Management'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient.email],
        )

        if pdf_file:
            pdf_file.seek(0)
            email.attach(pdf_file.name, pdf_file.read(), 'application/pdf')
        elif leave.pdf_attachment:
            leave.pdf_attachment.seek(0)
            email.attach(
                leave.pdf_attachment.name,
                leave.pdf_attachment.read(),
                'application/pdf'
            )

        email.send()

class LeaveSubmittedView(View):
    def get(self, request):
        return render(request, 'leaves/leave_submitted.html')