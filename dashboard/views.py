from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from leaves.models import Leave, LeaveBalance
from accounts.models import User
from django.contrib.auth.hashers import make_password
from datetime import date, timedelta
import calendar as cal


class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user

        if user.role in ['teacher', 'employee']:
            leaves = Leave.objects.filter(user=user)
            balances = LeaveBalance.objects.filter(user=user)
            
            leave_summary = []
            total_days_used = 0

            for balance in balances:
                # calculer les jours utilisés sans weekends
                days_used = 0
                for leave in leaves.filter(status='approved', leave_type=balance.leave_type):
                    current = leave.start_leave
                    while current <= leave.end_leave:
                        if current.weekday() < 5:
                            days_used += 1
                        current += timedelta(days=1)
                
                # mettre à jour la balance
                balance.days_used = days_used
                balance.days_remaining = balance.total_days - days_used
                balance.save()
                
                total_days_used += days_used

                is_maternity = balance.leave_type == 'maternity_paternity_leave'
                
                leave_summary.append({
                    'type': balance.leave_type.replace('_', ' ').title(),
                    'used': days_used,
                    'total': None if is_maternity else balance.total_days,
                    'remaining': None if is_maternity else balance.days_remaining,
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
        total_days = request.POST.get('total_days')
        user = User.objects.get(id=user_id)
        balance, created = LeaveBalance.objects.get_or_create(
            user=user,
            leave_type=leave_type,
            defaults={'total_days': 0, 'days_used': 0, 'days_remaining': 0}
        )
        balance.total_days = int(total_days)
        balance.days_remaining = int(total_days) - balance.days_used
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
    
from datetime import date

class PromoteUserView(LoginRequiredMixin, View):
    def post(self, request, user_id):
        if request.user.role != 'hr':
            return redirect('dashboard')
        
        target_user = User.objects.get(id=user_id)
        new_role = request.POST.get('new_role')

        # vérifier les transitions autorisées
        allowed_transitions = {
            'teacher': ['head_of_department', 'head_of_school'],
            'head_of_department': ['teacher', 'head_of_school'],
            'head_of_school': ['teacher', 'head_of_department'],
        }

        if target_user.role not in allowed_transitions:
            return HttpResponse("Role change not allowed for this user type.")
        
        if new_role not in allowed_transitions.get(target_user.role, []):
            return HttpResponse("Invalid role transition.")

        # si promu HoD ou HoS → supérieur devient HoS
        if new_role in ['head_of_department', 'head_of_school']:
            hos = User.objects.filter(role='head_of_school').first()
            target_user.superior = hos

        # si rétrogradé en teacher → supérieur devient HoD
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

        # vérifier si HoS ou HoD — il faut un remplaçant
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

        # vérifier que la date n'est pas passée
        if leave.start_leave < date.today():
            return HttpResponse("Cannot delete a leave request that has already started or passed.")

        # vérifier que le statut est pending ou approved
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
                'remaining': None if is_maternity else balance.total_days - days_used,
                'unpaid': False if is_maternity else (balance.total_days - days_used) < 0,
            })

        return render(request, 'dashboard/user_detail.html', {
            'target_user': target_user,
            'leaves': leaves,
            'leave_summary': leave_summary,
            'total_days_used': total_days_used,
        })