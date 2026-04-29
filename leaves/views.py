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
            pdf_file = request.FILES.get('pdf_attachment')

            if request.user.role == 'teacher':
                leave.status = 'pending_hod'
                if pdf_file:
                    leave.pdf_attachment = pdf_file
                leave.save()
                superior = request.user.superior
                if superior:
                    self.send_notification_email(leave, superior, pdf_file)

            elif request.user.role == 'employee':
                leave.status = 'pending_hoa'
                if pdf_file:
                    leave.pdf_attachment = pdf_file
                leave.save()
                hoa_users = User.objects.filter(role='head_of_admin')
                for hoa in hoa_users:
                    self.send_notification_email(leave, hoa, pdf_file)

            return redirect('leave_submitted')
        return render(request, 'leaves/submit_leave.html', {'form': form})

    def send_notification_email(self, leave, recipient, pdf_file=None):
        email = EmailMessage(
            subject=f'New Leave Request from {leave.user.first_name} {leave.user.last_name}',
            body=f'''{leave.user.first_name} {leave.user.last_name} has requested {leave.leave_type} leave from {leave.start_leave} to {leave.end_leave}.

Reason: {leave.reason_for_leave}

Please log in to the GESM Leave Management System to approve or reject this request:
http://127.0.0.1:8000/dashboard/

Thank you.''',
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