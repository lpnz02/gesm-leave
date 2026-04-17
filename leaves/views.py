from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from django.http import HttpResponse
from .forms import LeaveRequestForm
from .models import Leave, ApprovalToken, LeaveBalance
from accounts.models import User
from datetime import date, timedelta

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
                    self.send_approval_email(leave, superior, pdf_file)

            elif request.user.role == 'employee':
                leave.status = 'pending_hoa'
                if pdf_file:
                    leave.pdf_attachment = pdf_file
                leave.save()
                hoa_users = User.objects.filter(role='head_of_admin')
                for hoa in hoa_users:
                    self.send_approval_email(leave, hoa, pdf_file)

            return redirect('leave_submitted')
        return render(request, 'leaves/submit_leave.html', {'form': form})

    def send_approval_email(self, leave, recipient, pdf_file=None):
        approve_token = ApprovalToken.objects.create(leave=leave, action='approve')
        reject_token = ApprovalToken.objects.create(leave=leave, action='reject')
        approve_link = f"http://127.0.0.1:8000/leaves/action/{approve_token.token}/"
        reject_link = f"http://127.0.0.1:8000/leaves/action/{reject_token.token}/"

        email = EmailMessage(
            subject=f'Leave Request from {leave.user.first_name} {leave.user.last_name}',
            body=f'''{leave.user.first_name} {leave.user.last_name} has requested {leave.leave_type} from {leave.start_leave} to {leave.end_leave}.

Reason: {leave.reason_for_leave}

Approve: {approve_link}
Reject: {reject_link}''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient.email],
        )

        if pdf_file:
            email.attach(pdf_file.name, pdf_file.read(), 'application/pdf')
        elif leave.pdf_attachment:
            leave.pdf_attachment.seek(0)
            email.attach(
                leave.pdf_attachment.name,
                leave.pdf_attachment.read(),
                'application/pdf'
            )

        email.send()


class LeaveActionView(View):
    def get(self, request, token):
        try:
            approval_token = ApprovalToken.objects.get(token=token)

            if approval_token.is_used:
                return HttpResponse("This link has already been used.")

            leave = approval_token.leave
            user = leave.user
            approval_token.is_used = True
            approval_token.save()

            if approval_token.action == 'approve':

                if leave.status == 'pending_hod':
                    leave.status = 'pending_hos'
                    leave.save()
                    hos_users = User.objects.filter(role='head_of_school')
                    for hos in hos_users:
                        SubmitLeaveView().send_approval_email(leave, hos)
                    return HttpResponse("Approved by Head of Department! Head of School has been notified.")

                elif leave.status == 'pending_hos':
                    leave.status = 'approved'
                    leave.save()
                    self.update_balance(leave)
                    send_mail(
                        subject='Leave Request Approved',
                        message=f'Hello {user.first_name}, your {leave.leave_type} request has been fully approved!',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                    )
                    return HttpResponse("Leave fully approved!")

                elif leave.status == 'pending_hoa':
                    leave.status = 'approved'
                    leave.save()
                    self.update_balance(leave)
                    send_mail(
                        subject='Leave Request Approved',
                        message=f'Hello {user.first_name}, your {leave.leave_type} request has been approved!',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                    )
                    return HttpResponse("Leave approved!")

            elif approval_token.action == 'reject':
                leave.status = 'rejected'
                leave.save()
                send_mail(
                    subject='Leave Request Rejected',
                    message=f'Hello {user.first_name}, your {leave.leave_type} request has been rejected.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                )
                return HttpResponse("Leave rejected.")

        except ApprovalToken.DoesNotExist:
            return HttpResponse("Invalid link.")

    def update_balance(self, leave):
        count = 0
        current = leave.start_leave
        while current <= leave.end_leave:
            if current.weekday() < 5:
                count += 1
            current += timedelta(days=1)
        
        balance, created = LeaveBalance.objects.get_or_create(
            user=leave.user,
            leave_type=leave.leave_type,
            defaults={'total_days': 0, 'days_used': 0, 'days_remaining': 0}
        )
        balance.days_used += count
        balance.days_remaining -= count
        balance.save()


class LeaveSubmittedView(View):
    def get(self, request):
        return render(request, 'leaves/leave_submitted.html')