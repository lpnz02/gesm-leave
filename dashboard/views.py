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
from django.utils import timezone
from django.contrib import messages


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

            return render(request, 'dashboard/admin_dashboard.html', {
                'leaves': leaves,
                'total_days_used': days_used,
                'leave_summary': leave_summary,
                'user_role': user.role,
            })

        elif user.role == 'admin':
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

            return render(request, 'dashboard/admin_dashboard.html', {
                'leaves': leaves,
                'total_days_used': total_days_used,
                'leave_summary': leave_summary,
                'user_role': user.role,
            })

        elif user.role == 'head_of_department':
            dept = user.department
            if dept:
                subordinates = User.objects.filter(department=dept, role='teacher')
            else:
                subordinates = User.objects.filter(superior=user, role='teacher')

            teacher_leaves = Leave.objects.filter(user__in=subordinates)
            own_leaves = Leave.objects.filter(user=user)

            # calcul global comme les profs — ignore les balances par catégorie
            days_used = 0
            for leave in own_leaves.filter(status='approved'):
                current = leave.start_leave
                while current <= leave.end_leave:
                    if current.weekday() < 5:
                        days_used += 1
                    current += timedelta(days=1)

            leave_summary = [{
                'type': 'Total Leave (All Types)',
                'used': days_used,
                'total': 30,
                'remaining': 30 - days_used,
                'unpaid': (30 - days_used) < 0,
            }]

            return render(request, 'dashboard/hod_dashboard.html', {
                'subordinates': subordinates,
                'leaves': teacher_leaves,
                'own_leaves': own_leaves,
                'leave_summary': leave_summary,
                'total_days_used': days_used,
                'user_role': user.role,
            })

        elif user.role == 'head_of_school':
            hods = User.objects.filter(role='head_of_department')
            hod_teams = []
            for hod in hods:
                dept = hod.department
                if dept:
                    hod_teachers = User.objects.filter(department=dept, role='teacher')
                else:
                    hod_teachers = User.objects.filter(superior=hod, role='teacher')
                hod_teams.append({
                    'hod': hod,
                    'teachers': hod_teachers,
                })

            # leaves des profs ET des HOD avec status pending_hos
            leaves = Leave.objects.filter(
                user__role__in=['teacher', 'head_of_department'],
                status='pending_hos'
            ) | Leave.objects.filter(
                user__role__in=['teacher', 'head_of_department'],
                status__in=['approved', 'rejected']
            )

            return render(request, 'dashboard/hos_dashboard.html', {
                'hod_teams': hod_teams,
                'leaves': leaves,
            })

        elif user.role == 'head_of_admin':
            admins = User.objects.filter(role__in=['admin', 'hr'])  # ← ajoute 'hr'
            leaves = Leave.objects.filter(user__in=admins)
            return render(request, 'dashboard/hoa_dashboard.html', {
                'admins': admins,
                'leaves': leaves,
            })

        elif user.role == 'hr':
            from accounts.models import Department
            from django.utils import timezone as tz

            all_leaves = Leave.objects.filter(user__isnull=False).exclude(user__role='head_of_admin')
            all_users = User.objects.exclude(role__in=['hr', 'head_of_admin'])
            pending_users = User.objects.filter(is_active=False, is_email_verified=True)

            # alertes
            hods_no_dept = User.objects.filter(role='head_of_department', department=None)
            teachers_no_superior = User.objects.filter(role='teacher', superior=None)
            no_hos = not User.objects.filter(role='head_of_school', is_active=True).exists()
            no_hoa = not User.objects.filter(role='head_of_admin', is_active=True).exists()
            stale_leaves = Leave.objects.filter(
                user__isnull=False,
                status__in=['pending_hod', 'pending_hos', 'pending_hoa'],
                created_at__lt=tz.now() - timedelta(days=7)
            )

            return render(request, 'dashboard/hr_dashboard.html', {
                'all_leaves': all_leaves,
                'all_users': all_users,
                'pending_users': pending_users,
                'today': date.today(),
                'hods_no_dept': hods_no_dept,
                'teachers_no_superior': teachers_no_superior,
                'no_hos': no_hos,
                'no_hoa': no_hoa,
                'stale_leaves': stale_leaves,
            })
        
        elif user.role == 'scheduling_team':
            return render(request, 'dashboard/scheduling_dashboard.html', {})

        else:
            return render(request, 'dashboard/admin_dashboard.html', {
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

        allowed_roles = ['hr', 'head_of_department', 'head_of_school', 'head_of_admin', 'scheduling_team']
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
            leaves = leaves.filter(user__role__in=['admin', 'hr'])

        elif user.role == 'hr':
            if filter_type == 'teacher':
                leaves = leaves.filter(user__role='teacher')
            elif filter_type == 'hod':
                leaves = leaves.filter(user__role='head_of_department')
            elif filter_type == 'admin':
                leaves = leaves.filter(user__role__in=['admin', 'hr'])
            
            # filtre par département
            if filter_department != 'all':
                if filter_type == 'teacher':
                    leaves = leaves.filter(user__department__id=filter_department)
                elif filter_type == 'hod':
                    leaves = leaves.filter(user__department__id=filter_department)
                else:
                    leaves = leaves.filter(user__department__id=filter_department)

        elif user.role == 'scheduling_team':
            leaves = leaves.filter(user__role='teacher')

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

        from accounts.models import Department
        departments = Department.objects.all()  

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

        target_user.delete()
        return redirect('dashboard')


class DeleteLeaveView(LoginRequiredMixin, View):
    def post(self, request, leave_id):
        if request.user.role != 'hr':
            return redirect('dashboard')

        leave = Leave.objects.get(id=leave_id)
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

        ws.merge_cells('A1:H1')
        ws['A1'] = 'GESM Leave Management — Leave Requests Report'
        ws['A1'].font = title_font
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 30

        ws.merge_cells('A2:H2')
        ws['A2'] = f'Generated on: {date.today().strftime("%d/%m/%Y")}'
        ws['A2'].font = date_font
        ws['A2'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[2].height = 20
        ws.row_dimensions[3].height = 10

        headers = ['Person', 'Role', 'Start Date', 'Last Day', 'Leave Type', 'Reason', 'Status', 'Submitted On']
        for col, header in enumerate(headers, 1):
            c = ws.cell(row=4, column=col, value=header)
            c.font = header_font
            c.fill = header_fill
            c.alignment = header_align
            c.border = thin_border
        ws.row_dimensions[4].height = 30

        leaves = Leave.objects.filter(user__isnull=False).exclude(
            user__role='head_of_admin'
        ).order_by('-created_at')

        for row_idx, leave in enumerate(leaves, 5):
            is_alt = (row_idx % 2 == 0)
            name = f"{leave.user.first_name} {leave.user.last_name}" if leave.user else "Deleted User"
            role = leave.user.role if leave.user else "unknown"

            data = [
                name,
                role.replace('_', ' ').title(),
                leave.start_leave.strftime('%d/%m/%Y'),
                leave.end_leave.strftime('%d/%m/%Y'),
                leave.leave_type.replace('_', ' ').title(),
                leave.reason_for_leave,
                leave.status.replace('_', ' ').title(),
                timezone.localtime(leave.created_at).strftime('%d/%m/%Y %H:%M'),
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

        col_widths = [25, 20, 15, 15, 25, 40, 20, 20]
        for col, width in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(col)].width = width

        ws.freeze_panes = 'A5'

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="GESM_Leave_Report_{date.today().strftime("%Y%m%d")}.xlsx"'
        wb.save(response)
        return response


from accounts.models import User, Department

class EditUserView(LoginRequiredMixin, View):
    def get(self, request, user_id):
        if request.user.role != 'hr':
            return redirect('dashboard')
        target_user = User.objects.get(id=user_id)
        departments = Department.objects.all()
        return render(request, 'dashboard/edit_user.html', {
            'target_user': target_user,
            'departments': departments,
            'roles': [
                ('teacher', 'Teacher'),
                ('admin', 'Admin'),
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
        old_role = target_user.role
        old_dept = target_user.department

        target_user.first_name = request.POST.get('first_name')
        target_user.last_name = request.POST.get('last_name')
        target_user.email = request.POST.get('email')
        new_role = request.POST.get('role')
        target_user.role = new_role

        # gérer le département
        dept_id = request.POST.get('department')
        if dept_id:
            new_dept = Department.objects.get(id=dept_id)

            # retirer le HOD de l'ancien département si changement
            if old_dept and old_dept != new_dept:
                if old_dept.head == target_user:
                    old_dept.head = None
                    old_dept.save()
                # les profs de l'ancien dept perdent ce HOD comme supérieur
                if old_role == 'head_of_department':
                    for teacher in User.objects.filter(department=old_dept, role='teacher'):
                        teacher.superior = None
                        teacher.save()

            target_user.department = new_dept

            # si HOD → mettre à jour le head du nouveau département
            if new_role == 'head_of_department':
                new_dept.head = target_user
                new_dept.save()
                # mettre à jour le superior des profs du nouveau département
                for teacher in User.objects.filter(department=new_dept, role='teacher'):
                    teacher.superior = target_user
                    teacher.save()

        else:
            # pas de département → retirer l'ancien
            if old_dept:
                if old_dept.head == target_user:
                    old_dept.head = None
                    old_dept.save()
                if old_role == 'head_of_department':
                    for teacher in User.objects.filter(department=old_dept, role='teacher'):
                        teacher.superior = None
                        teacher.save()
            target_user.department = None

        # assigner le superior selon le rôle
        if new_role == 'head_of_department':
            hos = User.objects.filter(role='head_of_school').first()
            target_user.superior = hos
        elif new_role == 'teacher':
            dept = target_user.department
            if dept and dept.head:
                target_user.superior = dept.head
            else:
                target_user.superior = None
        elif new_role in ['head_of_school', 'head_of_admin', 'hr', 'admin']:
            target_user.superior = None

        target_user.save()

        # mettre à jour les balances si rôle change
        if old_role != new_role:
            if new_role in ['teacher', 'head_of_department', 'head_of_school']:
                LeaveBalance.objects.filter(user=target_user).delete()
                LeaveBalance.objects.create(
                    user=target_user,
                    leave_type='vacation_leave',
                    total_days=30, days_used=0,
                    days_remaining=30, carried_over=0,
                )
            elif new_role == 'admin':
                LeaveBalance.objects.filter(user=target_user).delete()
                defaults = {
                    'vacation_leave': 15,
                    'sick_leave': 15,
                    'bereavement_leave': 5,
                    'emergency_leave': 3,
                    'maternity_paternity_leave': 0,
                    'others': 0,
                }
                for leave_type, total in defaults.items():
                    LeaveBalance.objects.create(
                        user=target_user,
                        leave_type=leave_type,
                        total_days=total, days_used=0,
                        days_remaining=total, carried_over=0,
                    )

        return redirect('dashboard')

class ResetBalancesView(LoginRequiredMixin, View):
    def post(self, request):
        if request.user.role != 'hr':
            return redirect('dashboard')

        admin_defaults = {
            'vacation_leave': 15,
            'sick_leave': 15,
            'bereavement_leave': 5,
            'emergency_leave': 3,
            'maternity_paternity_leave': 0,
            'others': 0,
        }

        # reset admins/admins — carry over SEULEMENT vacation_leave
        for user in User.objects.filter(role__in=['admin']):
            for leave_type, default_total in admin_defaults.items():
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
                if not created:
                    if leave_type == 'vacation_leave':
                        # carry over uniquement les vacation days non utilisés
                        unused = max(0, balance.days_remaining)
                        new_total = default_total + unused
                        balance.total_days = new_total
                        balance.days_used = 0
                        balance.days_remaining = new_total
                        balance.carried_over = unused
                    else:
                        # toutes les autres catégories → remises au défaut
                        balance.total_days = default_total
                        balance.days_used = 0
                        balance.days_remaining = default_total
                        balance.carried_over = 0
                    balance.save()

        # reset profs ET HOD — 30j fixe, pas de report
        for user in User.objects.filter(role__in=['teacher', 'head_of_department', 'head_of_school']):
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

        # HOD approuve → pending_hos + email HOS avec PDF
        if request.user.role == 'head_of_department' and leave.status == 'pending_hod':
            leave.status = 'pending_hos'
            leave.save()
            for hos in User.objects.filter(role='head_of_school'):
                self._send_email(
                    to=hos.email,
                    subject=f'Leave Request Pending Your Approval — {user.first_name} {user.last_name}',
                    body=(
                        f'Hello,\n\n'
                        f'{user.first_name} {user.last_name} has requested {leave.leave_type.replace("_", " ").title()} leave '
                        f'from {leave.start_leave} to {leave.end_leave}.\n\n'
                        f'Reason: {leave.reason_for_leave}\n\n'
                        f'This request has been approved by the Head of Department '
                        f'and is now pending your approval. Please log in to your dashboard to approve or reject.\n\n'
                        f'GESM Leave Management'
                    ),
                    leave=leave,
                )

        # HOS approuve → approved + email prof + HOD + HOS + HR + scheduling
        elif request.user.role == 'head_of_school' and leave.status == 'pending_hos':
            leave.status = 'approved'
            leave.save()
            self._update_balance(leave)

            recipients = set()
            recipients.add(user.email)
            if user.superior:
                recipients.add(user.superior.email)
            for hos in User.objects.filter(role='head_of_school'):
                recipients.add(hos.email)
            for hr in User.objects.filter(role='hr'):
                recipients.add(hr.email)
            for sched in User.objects.filter(role='scheduling_team'):
                recipients.add(sched.email)

            for email_addr in recipients:
                self._send_email(
                    to=email_addr,
                    subject=f'Leave Request Approved — {user.first_name} {user.last_name}',
                    body=(
                        f'Hello,\n\n'
                        f'{user.first_name} {user.last_name} leave request for '
                        f'{leave.leave_type.replace("_", " ").title()} '
                        f'from {leave.start_leave} to {leave.end_leave} '
                        f'has been fully approved.\n\n'
                        f'GESM Leave Management'
                    ),
                )

        # HOA approuve → approved + email admin + HOA + HR
        elif request.user.role == 'head_of_admin' and leave.status == 'pending_hoa':
            leave.status = 'approved'
            leave.save()
            self._update_balance(leave)

            recipients = set()
            recipients.add(user.email)
            for hoa in User.objects.filter(role='head_of_admin'):
                recipients.add(hoa.email)
            for hr in User.objects.filter(role='hr'):
                recipients.add(hr.email)

            for email_addr in recipients:
                self._send_email(
                    to=email_addr,
                    subject=f'Leave Request Approved — {user.first_name} {user.last_name}',
                    body=(
                        f'Hello,\n\n'
                        f'{user.first_name} {user.last_name} leave request for '
                        f'{leave.leave_type.replace("_", " ").title()} '
                        f'from {leave.start_leave} to {leave.end_leave} '
                        f'has been approved by the Head of Administration.\n\n'
                        f'GESM Leave Management'
                    ),
                )

        elif request.user.role == 'hr':
            leave.status = 'approved'
            leave.save()
            self._update_balance(leave)
            self._send_email(
                to=user.email,
                subject=f'Leave Request Approved — {user.first_name} {user.last_name}',
                body=(
                    f'Hello {user.first_name},\n\n'
                    f'Your {leave.leave_type.replace("_", " ").title()} leave request '
                    f'from {leave.start_leave} to {leave.end_leave} '
                    f'has been approved by HR.\n\n'
                    f'GESM Leave Management'
                ),
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

        recipients = set()
        recipients.add(user.email)

        if user.role == 'teacher':
            if user.superior:
                recipients.add(user.superior.email)
            for hos in User.objects.filter(role='head_of_school'):
                recipients.add(hos.email)
            for hr in User.objects.filter(role='hr'):
                recipients.add(hr.email)

        elif user.role in ['admin', 'hr']:
            for hoa in User.objects.filter(role='head_of_admin'):
                recipients.add(hoa.email)
            for hr in User.objects.filter(role='hr'):
                recipients.add(hr.email)

        for email_addr in recipients:
            send_mail(
                subject=f'Leave Request Rejected — {user.first_name} {user.last_name}',
                message=(
                    f'Hello,\n\n'
                    f'{user.first_name} {user.last_name} leave request for '
                    f'{leave.leave_type.replace("_", " ").title()} '
                    f'from {leave.start_leave} to {leave.end_leave} '
                    f'has been rejected.\n\n'
                    f'GESM Leave Management'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email_addr],
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
    

from accounts.models import User, Department

class DepartmentListView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.role != 'hr':
            return redirect('dashboard')
        
        departments = Department.objects.all()
        hods = User.objects.filter(role='head_of_department')

        dept_data = []
        for dept in departments:
            teacher_count = User.objects.filter(
                department=dept, role='teacher'
            ).count()
            
            # si pas de head assigné, cherche un HOD dans le département
            if not dept.head:
                auto_hod = User.objects.filter(
                    department=dept, role='head_of_department'
                ).first()
                if auto_hod:
                    dept.head = auto_hod
                    dept.save()

            dept_data.append({
                'dept': dept,
                'teacher_count': teacher_count,
            })

        return render(request, 'dashboard/department_list.html', {
            'dept_data': dept_data,
            'hods': hods,
        })

    def post(self, request):
        if request.user.role != 'hr':
            return redirect('dashboard')
        dept_id = request.POST.get('dept_id')
        hod_id = request.POST.get('hod_id')
        dept = Department.objects.get(id=dept_id)
        if hod_id:
            hod = User.objects.get(id=hod_id)
            dept.head = hod
            dept.save()
            for teacher in User.objects.filter(department=dept, role='teacher'):
                teacher.superior = hod
                teacher.save()
        return redirect('department_list')


class DepartmentCreateView(LoginRequiredMixin, View):
    def post(self, request):
        if request.user.role != 'hr':
            return redirect('dashboard')
        name = request.POST.get('name')
        if name:
            Department.objects.create(name=name)
        return redirect('department_list')


class DepartmentDeleteView(LoginRequiredMixin, View):
    def post(self, request, dept_id):
        if request.user.role != 'hr':
            return redirect('dashboard')
        dept = Department.objects.get(id=dept_id)
        
        # vérifier si des HOD sont dans ce département
        hods_in_dept = User.objects.filter(department=dept, role='head_of_department')
        teachers_in_dept = User.objects.filter(department=dept, role='teacher')
        
        if hods_in_dept.exists() or teachers_in_dept.exists():
            from django.contrib import messages
            names = ', '.join([f"{u.first_name} {u.last_name}" for u in hods_in_dept])
            messages.warning(request,
                f"Warning: Department '{dept.name}' has been deleted but "
                f"{hods_in_dept.count()} HOD(s) ({names}) and "
                f"{teachers_in_dept.count()} teacher(s) still have it assigned. "
                f"Please reassign them via Edit User."
            )
        
        dept.delete()
        return redirect('department_list')
    

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
        update_session_auth_hash(request, request.user)  # reste connecté
        messages.success(request, 'Password changed successfully!')
        return redirect('dashboard')