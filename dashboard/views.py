from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from leaves.models import Leave, LeaveBalance
from accounts.models import User
from django.contrib.auth.hashers import make_password
from datetime import date, timedelta
import calendar as cal
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.core.mail import EmailMessage, send_mail
from django.conf import settings


class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user

        if user.role == 'teacher':
            leaves = Leave.objects.filter(user=user)
            days_used = 0
            for leave in leaves.filter(status='approved'):
                current = leave.start_leave
                while current <= leave.end_leave:
                    if current.weekday() < 5:
                        days_used += 1
                    current += timedelta(days=1)

            total = 30
            leave_summary = [{
                'type': 'Total Leave (All Types)',
                'used': days_used,
                'total': total,
                'remaining': total - days_used,
                'unpaid': (total - days_used) < 0,
            }]

            return render(request, 'dashboard/employee_dashboard.html', {
                'leaves': leaves,
                'total_days_used': days_used,
                'leave_summary': leave_summary,
                'user_role': user.role,
            })

        elif user.role == 'employee':
            leaves = Leave.objects.filter(user=user)
            balances = LeaveBalance.objects.filter(user=user)
            leave_summary = []
            total_days_used = 0

            for balance in balances:
                # calculer days_used seulement
                days_used = 0
                for leave in leaves.filter(status='approved', leave_type=balance.leave_type):
                    current = leave.start_leave
                    while current <= leave.end_leave:
                        if current.weekday() < 5:
                            days_used += 1
                        current += timedelta(days=1)

                # mettre à jour days_used seulement — pas days_remaining !
                balance.days_used = days_used
                balance.save()

                total_days_used += days_used
                is_maternity = balance.leave_type == 'maternity_paternity_leave'

                leave_summary.append({
                    'type': balance.leave_type.replace('_', ' ').title(),
                    'used': days_used,
                    'total': None if is_maternity else balance.total_days,
                    'remaining': None if is_maternity else balance.days_remaining,
                    'carried_over': balance.carried_over,
                    'unpaid': False if is_maternity else balance.days_remaining < 0,
                })

            return render(request, 'dashboard/employee_dashboard.html', {
                'leaves': leaves,
                'total_days_used': total_days_used,
                'leave_summary': leave_summary,
                'user_role': user.role,
            })

        elif user.role == 'head_of_department':
            subordinates = User.objects.filter(superior=user, role='teacher')
            leaves = Leave.objects.filter(user__in=subordinates)
            return render(request, 'dashboard/hod_dashboard.html', {
                'subordinates': subordinates,
                'leaves': leaves,
            })

        elif user.role == 'head_of_school':
            hods = User.objects.filter(role='head_of_department')
            teachers = User.objects.filter(role='teacher')
            leaves = Leave.objects.filter(user__in=teachers)
            hod_teams = []
            for hod in hods:
                hod_teachers = teachers.filter(superior=hod)
                hod_teams.append({
                    'hod': hod,
                    'teachers': hod_teachers,
                })
            return render(request, 'dashboard/hos_dashboard.html', {
                'hod_teams': hod_teams,
                'leaves': leaves,
            })

        elif user.role == 'head_of_admin':
            employees = User.objects.filter(role='employee')
            leaves = Leave.objects.filter(user__in=employees)
            return render(request, 'dashboard/hoa_dashboard.html', {
                'employees': employees,
                'leaves': leaves,
            })

        elif user.role == 'hr':
            all_leaves = Leave.objects.exclude(user__role='head_of_admin')
            all_users = User.objects.exclude(role__in=['hr', 'head_of_admin'])
            pending_users = User.objects.filter(is_active=False, is_email_verified=True)
            return render(request, 'dashboard/hr_dashboard.html', {
                'all_leaves': all_leaves,
                'all_users': all_users,
                'pending_users': pending_users,
                'today': date.today(),
            })

        else:
            return render(request, 'dashboard/employee_dashboard.html', {
                'leaves': [],
                'total_days_used': 0,
            })


class AdjustBalanceView(LoginRequiredMixin, View):
    def post(self, request):
        if request.user.role != 'hr':
            return redirect('dashboard')
        user_id = request.POST.get('user_id')
        leave_type = request.POST.get('leave_type')
        days_remaining = request.POST.get('days_remaining')
        user = User.objects.get(id=user_id)
        balance, created = LeaveBalance.objects.get_or_create(
            user=user,
            leave_type=leave_type,
            defaults={'total_days': 0, 'days_used': 0, 'days_remaining': 0, 'carried_over': 0}
        )
        balance.days_remaining = int(days_remaining)
        balance.save()
        return redirect('dashboard')


class CreateAdminUserView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.role != 'hr':
            return redirect('dashboard')
        return render(request, 'dashboard/create_admin_user.html')

    def post(self, request):
        if request.user.role != 'hr':
            return redirect('dashboard')
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        role = request.POST.get('role')
        password = request.POST.get('password')
        User.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            role=role,
            password=make_password(password),
            is_active=True,
            is_approved=True,
            is_email_verified=True,
        )
        return redirect('dashboard')


class DeleteOwnAccountView(LoginRequiredMixin, View):
    def post(self, request):
        user = request.user
        other_hr = User.objects.filter(role='hr', is_active=True).exclude(id=user.id)
        if other_hr.count() == 0:
            return HttpResponse("Cannot delete account — you are the only HR. Create another HR first!")
        user.delete()
        return redirect('login')


class CalendarView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user

        allowed_roles = ['hr', 'head_of_department', 'head_of_school', 'head_of_admin']
        if user.role not in allowed_roles:
            return redirect('dashboard')

        month = int(request.GET.get('month', date.today().month))
        year = int(request.GET.get('year', date.today().year))
        filter_type = request.GET.get('type', 'all')
        filter_department = request.GET.get('department', 'all')

        leaves = Leave.objects.filter(
            status='approved',
            start_leave__lte=date(year, month, cal.monthrange(year, month)[1]),
            end_leave__gte=date(year, month, 1),
        )

        if user.role == 'head_of_department':
            leaves = leaves.filter(user__superior=user, user__role='teacher')

        elif user.role == 'head_of_school':
            leaves = leaves.filter(user__role__in=['teacher', 'head_of_department'])
            if filter_department != 'all':
                leaves = leaves.filter(user__superior__id=filter_department)

        elif user.role == 'head_of_admin':
            leaves = leaves.filter(user__role='employee')

        elif user.role == 'hr':
            if filter_type == 'teacher':
                leaves = leaves.filter(user__role='teacher')
            elif filter_type == 'employee':
                leaves = leaves.filter(user__role='employee')
            if filter_department != 'all':
                leaves = leaves.filter(user__superior__id=filter_department)

        colors = [
            '#e74c3c', '#3498db', '#2ecc71', '#9b59b6',
            '#e67e22', '#1abc9c', '#e91e63', '#ff5722',
            '#607d8b', '#795548'
        ]

        user_colors = {}
        color_index = 0
        for leave in leaves:
            if leave.user.id not in user_colors:
                user_colors[leave.user.id] = colors[color_index % len(colors)]
                color_index += 1

        cal_matrix = cal.monthcalendar(year, month)
        calendar_data = []
        for week in cal_matrix:
            week_data = []
            for day_index, day in enumerate(week):
                if day == 0:
                    week_data.append({'day': 0, 'absents': [], 'is_weekend': False})
                else:
                    is_weekend = day_index >= 5
                    current_date = date(year, month, day)
                    absents = []
                    if not is_weekend:
                        for leave in leaves:
                            if leave.start_leave <= current_date <= leave.end_leave:
                                absents.append({
                                    'name': f"{leave.user.first_name} {leave.user.last_name}",
                                    'color': user_colors.get(leave.user.id, '#3498db')
                                })
                    week_data.append({
                        'day': day,
                        'absents': absents,
                        'is_weekend': is_weekend
                    })
            calendar_data.append(week_data)

        departments = User.objects.filter(role='head_of_department')

        if month == 1:
            prev_month, prev_year = 12, year - 1
        else:
            prev_month, prev_year = month - 1, year

        if month == 12:
            next_month, next_year = 1, year + 1
        else:
            next_month, next_year = month + 1, year

        month_name = cal.month_name[month]

        return render(request, 'dashboard/calendar.html', {
            'calendar_data': calendar_data,
            'month': month,
            'year': year,
            'month_name': month_name,
            'prev_month': prev_month,
            'prev_year': prev_year,
            'next_month': next_month,
            'next_year': next_year,
            'filter_type': filter_type,
            'filter_department': filter_department,
            'departments': departments,
            'user_role': user.role,
        })


class PromoteUserView(LoginRequiredMixin, View):
    def post(self, request, user_id):
        if request.user.role != 'hr':
            return redirect('dashboard')

        target_user = User.objects.get(id=user_id)
        new_role = request.POST.get('new_role')

        allowed_transitions = {
            'teacher': ['head_of_department', 'head_of_school'],
            'head_of_department': ['teacher', 'head_of_school'],
            'head_of_school': ['teacher', 'head_of_department'],
        }

        if target_user.role not in allowed_transitions:
            return HttpResponse("Role change not allowed for this user type.")

        if new_role not in allowed_transitions.get(target_user.role, []):
            return HttpResponse("Invalid role transition.")

        if new_role in ['head_of_department', 'head_of_school']:
            hos = User.objects.filter(role='head_of_school').first()
            target_user.superior = hos
        elif new_role == 'teacher':
            hod = User.objects.filter(role='head_of_department').first()
            target_user.superior = hod

        target_user.role = new_role
        target_user.save()
        return redirect('dashboard')


class DeleteUserView(LoginRequiredMixin, View):
    def post(self, request, user_id):
        if request.user.role != 'hr':
            return redirect('dashboard')

        target_user = User.objects.get(id=user_id)

        if target_user.role == 'head_of_school':
            other_hos = User.objects.filter(role='head_of_school').exclude(id=user_id)
            if not other_hos.exists():
                return HttpResponse("Please reassign a new Head of School before deleting this one.")

        if target_user.role == 'head_of_department':
            other_hod = User.objects.filter(
                role='head_of_department',
                department=target_user.department
            ).exclude(id=user_id)
            if not other_hod.exists():
                return HttpResponse("Please reassign a new Head of Department before deleting this one.")

        target_user.delete()
        return redirect('dashboard')


class DeleteLeaveView(LoginRequiredMixin, View):
    def post(self, request, leave_id):
        if request.user.role != 'hr':
            return redirect('dashboard')

        leave = Leave.objects.get(id=leave_id)

        if leave.start_leave < date.today():
            return HttpResponse("Cannot delete a leave request that has already started or passed.")

        if leave.status not in ['pending_hod', 'pending_hos', 'pending_hoa', 'approved']:
            return HttpResponse("Cannot delete this leave request.")

        leave.delete()
        return redirect('dashboard')


class UserDetailView(LoginRequiredMixin, View):
    def get(self, request, user_id):
        if request.user.role != 'hr':
            return redirect('dashboard')

        target_user = User.objects.get(id=user_id)
        leaves = Leave.objects.filter(user=target_user)
        balances = LeaveBalance.objects.filter(user=target_user)

        leave_summary = []
        total_days_used = 0

        if target_user.role == 'teacher':
            days_used = 0
            for leave in leaves.filter(status='approved'):
                current = leave.start_leave
                while current <= leave.end_leave:
                    if current.weekday() < 5:
                        days_used += 1
                    current += timedelta(days=1)
            total_days_used = days_used
            leave_summary.append({
                'type': 'Total Leave (All Types)',
                'used': days_used,
                'total': 30,
                'remaining': 30 - days_used,
                'unpaid': (30 - days_used) < 0,
            })
        else:
            for balance in balances:
                days_used = 0
                for leave in leaves.filter(status='approved', leave_type=balance.leave_type):
                    current = leave.start_leave
                    while current <= leave.end_leave:
                        if current.weekday() < 5:
                            days_used += 1
                        current += timedelta(days=1)

                total_days_used += days_used
                is_maternity = balance.leave_type == 'maternity_paternity_leave'

                leave_summary.append({
                    'type': balance.leave_type.replace('_', ' ').title(),
                    'used': days_used,
                    'total': None if is_maternity else balance.total_days,
                    'remaining': None if is_maternity else balance.days_remaining,
                    'unpaid': False if is_maternity else balance.days_remaining < 0,
                })

        return render(request, 'dashboard/user_detail.html', {
            'target_user': target_user,
            'leaves': leaves,
            'leave_summary': leave_summary,
            'total_days_used': total_days_used,
        })


class ExportLeavesView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.role != 'hr':
            return redirect('dashboard')

        wb = Workbook()
        ws = wb.active
        ws.title = "Leave Requests"

        blue = "1a3a6b"
        light_blue = "e8eef8"

        header_font = Font(name='Arial', bold=True, color='FFFFFF', size=11)
        header_fill = PatternFill('solid', start_color=blue, end_color=blue)
        header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
        title_font = Font(name='Arial', bold=True, color=blue, size=14)
        date_font = Font(name='Arial', italic=True, color='666666', size=10)
        cell_align = Alignment(horizontal='left', vertical='center', wrap_text=True)
        center_align = Alignment(horizontal='center', vertical='center')

        thin_border = Border(
            left=Side(style='thin', color='CCCCCC'),
            right=Side(style='thin', color='CCCCCC'),
            top=Side(style='thin', color='CCCCCC'),
            bottom=Side(style='thin', color='CCCCCC'),
        )

        alt_fill = PatternFill('solid', start_color=light_blue, end_color=light_blue)
        approved_fill = PatternFill('solid', start_color='d4edda', end_color='d4edda')
        rejected_fill = PatternFill('solid', start_color='f8d7da', end_color='f8d7da')
        pending_fill = PatternFill('solid', start_color='fff3cd', end_color='fff3cd')

        ws.merge_cells('A1:G1')
        ws['A1'] = 'GESM Leave Management — Leave Requests Report'
        ws['A1'].font = title_font
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 30

        ws.merge_cells('A2:G2')
        ws['A2'] = f'Generated on: {date.today().strftime("%d/%m/%Y")}'
        ws['A2'].font = date_font
        ws['A2'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[2].height = 20
        ws.row_dimensions[3].height = 10

        headers = ['Person', 'Role', 'Start Date', 'End Date', 'Leave Type', 'Reason', 'Status']
        for col, header in enumerate(headers, 1):
            c = ws.cell(row=4, column=col, value=header)
            c.font = header_font
            c.fill = header_fill
            c.alignment = header_align
            c.border = thin_border
        ws.row_dimensions[4].height = 30

        leaves = Leave.objects.exclude(user__role='head_of_admin').order_by('-created_at')

        for row_idx, leave in enumerate(leaves, 5):
            is_alt = (row_idx % 2 == 0)
            name = f"{leave.user.first_name} {leave.user.last_name}" if leave.user else "Deleted User"
            role = leave.user.role if leave.user else "—"

            data = [
                name,
                role.replace('_', ' ').title(),
                leave.start_leave.strftime('%d/%m/%Y'),
                leave.end_leave.strftime('%d/%m/%Y'),
                leave.leave_type.replace('_', ' ').title(),
                leave.reason_for_leave,
                leave.status.replace('_', ' ').title(),
            ]

            for col, value in enumerate(data, 1):
                c = ws.cell(row=row_idx, column=col, value=value)
                c.font = Font(name='Arial', size=10)
                c.border = thin_border
                c.alignment = cell_align if col in [1, 6] else center_align

                if col == 7:
                    if leave.status == 'approved':
                        c.fill = approved_fill
                        c.font = Font(name='Arial', size=10, bold=True, color='155724')
                    elif leave.status == 'rejected':
                        c.fill = rejected_fill
                        c.font = Font(name='Arial', size=10, bold=True, color='721c24')
                    else:
                        c.fill = pending_fill
                        c.font = Font(name='Arial', size=10, bold=True, color='856404')
                elif is_alt:
                    c.fill = alt_fill

            ws.row_dimensions[row_idx].height = 20

        col_widths = [25, 20, 15, 15, 25, 40, 20]
        for col, width in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(col)].width = width

        ws.freeze_panes = 'A5'

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="GESM_Leave_Report_{date.today().strftime("%Y%m%d")}.xlsx"'
        wb.save(response)
        return response


class EditUserView(LoginRequiredMixin, View):
    def get(self, request, user_id):
        if request.user.role != 'hr':
            return redirect('dashboard')
        target_user = User.objects.get(id=user_id)
        all_users = User.objects.exclude(id=user_id)
        return render(request, 'dashboard/edit_user.html', {
            'target_user': target_user,
            'all_users': all_users,
            'roles': [
                ('teacher', 'Teacher'),
                ('employee', 'Employee'),
                ('head_of_department', 'Head of Department'),
                ('head_of_school', 'Head of School'),
                ('head_of_admin', 'Head of Administration'),
                ('hr', 'HR'),
            ]
        })

    def post(self, request, user_id):
        if request.user.role != 'hr':
            return redirect('dashboard')
        target_user = User.objects.get(id=user_id)
        target_user.first_name = request.POST.get('first_name')
        target_user.last_name = request.POST.get('last_name')
        target_user.email = request.POST.get('email')
        target_user.role = request.POST.get('role')
        superior_id = request.POST.get('superior')
        if superior_id:
            target_user.superior = User.objects.get(id=superior_id)
        else:
            target_user.superior = None
        target_user.save()
        return redirect('dashboard')


class ResetBalancesView(LoginRequiredMixin, View):
    def post(self, request):
        if request.user.role != 'hr':
            return redirect('dashboard')

        employee_defaults = {
            'vacation_leave': 15,
            'sick_leave': 15,
            'bereavement_leave': 5,
            'emergency_leave': 3,
            'maternity_paternity_leave': 0,
            'others': 0,
        }

        for user in User.objects.filter(role='employee'):
            for leave_type, default_total in employee_defaults.items():
                balance, created = LeaveBalance.objects.get_or_create(
                    user=user,
                    leave_type=leave_type,
                    defaults={
                        'total_days': default_total,
                        'days_used': 0,
                        'days_remaining': default_total,
                        'carried_over': 0,
                    }
                )
                if not created and default_total > 0:
                    # reporter les days_remaining actuels (modifiables par HR)
                    unused = max(0, balance.days_remaining)
                    new_total = default_total + unused
                    balance.total_days = new_total
                    balance.days_used = 0
                    balance.days_remaining = new_total
                    balance.carried_over = unused
                    balance.save()
                elif not created and default_total == 0:
                    # maternity/others — pas de reset
                    balance.days_used = 0
                    balance.carried_over = 0
                    balance.save()

        # reset profs — 30j fixe, pas de report
        for user in User.objects.filter(role='teacher'):
            balance = LeaveBalance.objects.filter(
                user=user, leave_type='vacation_leave'
            ).first()
            if balance:
                balance.total_days = 30
                balance.days_used = 0
                balance.days_remaining = 30
                balance.carried_over = 0
                balance.save()

        Leave.objects.all().delete()
        return redirect('dashboard')


class ApproveLeaveDashboardView(LoginRequiredMixin, View):
    def post(self, request, leave_id):
        leave = Leave.objects.get(id=leave_id)
        user = leave.user

        if request.user.role == 'head_of_department' and leave.status == 'pending_hod':
            leave.status = 'pending_hos'
            leave.save()
            hos_users = User.objects.filter(role='head_of_school')
            for hos in hos_users:
                self._send_email(
                    to=hos.email,
                    subject=f'Leave Request Pending Your Approval — {user.first_name} {user.last_name}',
                    body=f'''{user.first_name} {user.last_name} has requested {leave.leave_type} leave from {leave.start_leave} to {leave.end_leave}.

Approved by Head of Department. Please log in to approve or reject:
http://127.0.0.1:8000/dashboard/

Reason: {leave.reason_for_leave}''',
                    leave=leave,
                )

        elif request.user.role == 'head_of_school' and leave.status == 'pending_hos':
            leave.status = 'approved'
            leave.save()
            self._update_balance(leave)
            self._send_email(
                to=user.email,
                subject='Your Leave Request Has Been Approved',
                body=f'Hello {user.first_name}, your {leave.leave_type} leave request from {leave.start_leave} to {leave.end_leave} has been fully approved!',
            )

        elif request.user.role == 'head_of_admin' and leave.status == 'pending_hoa':
            leave.status = 'approved'
            leave.save()
            self._update_balance(leave)
            self._send_email(
                to=user.email,
                subject='Your Leave Request Has Been Approved',
                body=f'Hello {user.first_name}, your {leave.leave_type} leave request from {leave.start_leave} to {leave.end_leave} has been approved!',
            )

        elif request.user.role == 'hr':
            leave.status = 'approved'
            leave.save()
            self._update_balance(leave)
            self._send_email(
                to=user.email,
                subject='Your Leave Request Has Been Approved',
                body=f'Hello {user.first_name}, your {leave.leave_type} leave request from {leave.start_leave} to {leave.end_leave} has been approved by HR!',
            )

        return redirect('dashboard')

    def _send_email(self, to, subject, body, leave=None):
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
        )
        if leave and leave.pdf_attachment:
            leave.pdf_attachment.seek(0)
            email.attach(
                leave.pdf_attachment.name,
                leave.pdf_attachment.read(),
                'application/pdf'
            )
        email.send()

    def _update_balance(self, leave):
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


class RejectLeaveDashboardView(LoginRequiredMixin, View):
    def post(self, request, leave_id):
        leave = Leave.objects.get(id=leave_id)
        user = leave.user

        allowed_roles = ['head_of_department', 'head_of_school', 'head_of_admin', 'hr']
        if request.user.role not in allowed_roles:
            return redirect('dashboard')

        leave.status = 'rejected'
        leave.save()

        send_mail(
            subject='Your Leave Request Has Been Rejected',
            message=f'Hello {user.first_name}, your {leave.leave_type} leave request from {leave.start_leave} to {leave.end_leave} has been rejected.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )

        return redirect('dashboard')
    
import os
from django.http import FileResponse

class ArchivesView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.role != 'hr':
            return redirect('dashboard')
        
        # tous les congés avec PDF
        leaves_with_pdf = Leave.objects.exclude(
            pdf_attachment=''
        ).exclude(
            pdf_attachment=None
        ).order_by('-created_at')
        
        return render(request, 'dashboard/archives.html', {
            'leaves_with_pdf': leaves_with_pdf,
        })


class DownloadPDFView(LoginRequiredMixin, View):
    def get(self, request, leave_id):
        if request.user.role != 'hr':
            return redirect('dashboard')
        
        leave = Leave.objects.get(id=leave_id)
        
        if not leave.pdf_attachment:
            return HttpResponse("No PDF found for this leave request.")
        
        leave.pdf_attachment.seek(0)
        response = FileResponse(
            leave.pdf_attachment,
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="{leave.pdf_attachment.name}"'
        return response


class DeleteArchivesView(LoginRequiredMixin, View):
    def post(self, request):
        if request.user.role != 'hr':
            return redirect('dashboard')
        
        leaves_with_pdf = Leave.objects.exclude(
            pdf_attachment=''
        ).exclude(
            pdf_attachment=None
        )
        
        for leave in leaves_with_pdf:
            if leave.pdf_attachment:
                # supprimer le fichier physique
                if os.path.exists(leave.pdf_attachment.path):
                    os.remove(leave.pdf_attachment.path)
                leave.pdf_attachment = None
                leave.save()
        
        return redirect('archives')