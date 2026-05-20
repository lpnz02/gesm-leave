# dashboard/tests.py
from django.test import TestCase, Client
from django.urls import reverse
from datetime import date, timedelta
from accounts.models import User, Department
from leaves.models import Leave, LeaveBalance


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.dept = Department.objects.create(name='Mathematics')
        self.hod = User.objects.create_user(
            username='hod01', email='hod@gesm.org', password='TestPass1234!',
            role='head_of_department', department=self.dept,
            is_active=True, is_approved=True, is_email_verified=True,
        )
        self.dept.head = self.hod
        self.dept.save()
        self.teacher = User.objects.create_user(
            username='teacher01', email='t@gesm.org', password='TestPass1234!',
            role='teacher', department=self.dept, superior=self.hod,
            is_active=True, is_approved=True, is_email_verified=True,
        )
        self.admin = User.objects.create_user(
            username='admin01', email='admin@gesm.org', password='TestPass1234!',
            role='admin', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.hos = User.objects.create_user(
            username='hos01', email='hos@gesm.org', password='TestPass1234!',
            role='head_of_school', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.hoa = User.objects.create_user(
            username='hoa01', email='hoa@gesm.org', password='TestPass1234!',
            role='head_of_admin', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.hr = User.objects.create_user(
            username='hr01', email='hr@gesm.org', password='TestPass1234!',
            role='hr', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.scheduling = User.objects.create_user(
            username='sched01', email='sched@gesm.org', password='TestPass1234!',
            role='scheduling_team', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.calendar_access = User.objects.create_user(
            username='cal01', email='cal@gesm.org', password='TestPass1234!',
            role='calendar_access', is_active=True, is_approved=True, is_email_verified=True,
        )
        # Balances pour teacher et admin
        LeaveBalance.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            total_days=30, days_used=0, days_remaining=30, carried_over=0,
        )
        for lt, total in [
            ('vacation_leave', 15), ('sick_leave', 15), ('bereavement_leave', 5),
            ('emergency_leave', 3), ('maternity_paternity_leave', 1), ('others', 1),
        ]:
            LeaveBalance.objects.create(
                user=self.admin, leave_type=lt,
                total_days=total, days_used=0, days_remaining=total, carried_over=0,
            )

    def test_unauthenticated_redirected_to_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_all_dashboards_load_200(self):
        """Every role dashboard returns 200"""
        roles = [
            'teacher01', 'admin01', 'hod01',
            'hos01', 'hoa01', 'hr01', 'sched01', 'cal01',
        ]
        for username in roles:
            self.client.login(username=username, password='TestPass1234!')
            response = self.client.get(reverse('dashboard'))
            self.assertEqual(response.status_code, 200, f'Failed for {username}')

    def test_teacher_cannot_access_calendar(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 302)

    def test_admin_cannot_access_calendar(self):
        self.client.login(username='admin01', password='TestPass1234!')
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 302)

    def test_scheduling_team_can_access_calendar(self):
        self.client.login(username='sched01', password='TestPass1234!')
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 200)

    def test_calendar_access_can_access_calendar(self):
        """Calendar access role can view the calendar"""
        self.client.login(username='cal01', password='TestPass1234!')
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 200)

    def test_hod_hos_hoa_hr_can_access_calendar(self):
        for username in ['hod01', 'hos01', 'hoa01', 'hr01']:
            self.client.login(username=username, password='TestPass1234!')
            response = self.client.get(reverse('calendar'))
            self.assertEqual(response.status_code, 200, f'Failed for {username}')

    def test_hod_sees_teachers_from_department(self):
        self.client.login(username='hod01', password='TestPass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertIn(self.teacher, response.context['subordinates'])

    def test_hoa_sees_admin_leave_in_dashboard(self):
        admin_leave = Leave.objects.create(
            user=self.admin, leave_type='vacation_leave',
            reason_for_leave='Test',
            start_leave=date.today() + timedelta(days=10),
            end_leave=date.today() + timedelta(days=15),
            status='pending_hoa', half_day='none',
        )
        self.client.login(username='hoa01', password='TestPass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertIn(admin_leave, response.context['leaves'])

    def test_hoa_sees_hr_leave_in_dashboard(self):
        hr_leave = Leave.objects.create(
            user=self.hr, leave_type='vacation_leave',
            reason_for_leave='Test',
            start_leave=date.today() + timedelta(days=10),
            end_leave=date.today() + timedelta(days=15),
            status='pending_hoa', half_day='none',
        )
        self.client.login(username='hoa01', password='TestPass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertIn(hr_leave, response.context['leaves'])

    def test_teacher_balance_shows_30_days(self):
        """Teacher dashboard shows 30 days total"""
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.get(reverse('dashboard'))
        leave_summary = response.context['leave_summary']
        self.assertEqual(len(leave_summary), 1)
        self.assertEqual(leave_summary[0]['total'], 30)

    def test_admin_balance_shows_6_categories(self):
        """Admin dashboard shows 6 leave categories"""
        self.client.login(username='admin01', password='TestPass1234!')
        response = self.client.get(reverse('dashboard'))
        leave_summary = response.context['leave_summary']
        self.assertEqual(len(leave_summary), 6)

    def test_calendar_shows_unpaid_leave_red(self):
        """Unpaid leave appears with red color in calendar data"""
        Leave.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            reason_for_leave='Test', start_leave=date.today(),
            end_leave=date.today() + timedelta(days=2),
            status='approved', half_day='none', is_unpaid=True,
        )
        self.client.login(username='hr01', password='TestPass1234!')
        response = self.client.get(reverse('calendar'))
        calendar_data = response.context['calendar_data']
        found_red = False
        for week in calendar_data:
            for day in week:
                for absent in day['absents']:
                    if absent['color'] == '#dc3545':
                        found_red = True
        self.assertTrue(found_red)

    def test_calendar_shows_paid_leave_blue(self):
        """Paid leave appears with blue GESM color in calendar"""
        Leave.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            reason_for_leave='Test', start_leave=date.today(),
            end_leave=date.today() + timedelta(days=2),
            status='approved', half_day='none', is_unpaid=False,
        )
        self.client.login(username='hr01', password='TestPass1234!')
        response = self.client.get(reverse('calendar'))
        calendar_data = response.context['calendar_data']
        found_blue = False
        for week in calendar_data:
            for day in week:
                for absent in day['absents']:
                    if absent['color'] == '#1a3a6b':
                        found_blue = True
        self.assertTrue(found_blue)

    def test_half_day_morning_shows_am_in_calendar(self):
        """Half day morning shows (AM) in calendar"""
        today = date.today()
        Leave.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            reason_for_leave='Test', start_leave=today,
            end_leave=today, status='approved', half_day='morning',
        )
        self.client.login(username='hr01', password='TestPass1234!')
        month = today.month
        year = today.year
        response = self.client.get(reverse('calendar') + f'?month={month}&year={year}')
        calendar_data = response.context['calendar_data']
        found_am = False
        for week in calendar_data:
            for day in week:
                for absent in day['absents']:
                    if '(AM)' in absent['name']:
                        found_am = True
        self.assertTrue(found_am)


class HRFeaturesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.dept = Department.objects.create(name='Mathematics')
        self.hr = User.objects.create_user(
            username='hr01', email='hr@gesm.org', password='TestPass1234!',
            role='hr', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.hr2 = User.objects.create_user(
            username='hr02', email='hr2@gesm.org', password='TestPass1234!',
            role='hr', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.hoa = User.objects.create_user(
            username='hoa01', email='hoa@gesm.org', password='TestPass1234!',
            role='head_of_admin', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.teacher = User.objects.create_user(
            username='teacher01', email='t@gesm.org', password='TestPass1234!',
            role='teacher', department=self.dept,
            is_active=True, is_approved=True, is_email_verified=True,
        )
        self.admin = User.objects.create_user(
            username='admin01', email='admin@gesm.org', password='TestPass1234!',
            role='admin', is_active=True, is_approved=True, is_email_verified=True,
        )
        LeaveBalance.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            total_days=30, days_used=0, days_remaining=30, carried_over=0,
        )
        self.client.login(username='hr01', password='TestPass1234!')

    def test_hr_can_edit_user_name(self):
        self.client.post(reverse('edit_user', args=[self.teacher.id]), {
            'first_name': 'NewName',
            'last_name': self.teacher.last_name or 'Test',
            'email': self.teacher.email,
            'role': 'teacher', 'department': self.dept.id,
        })
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.first_name, 'NewName')

    def test_hr_can_edit_user_role_teacher_to_admin(self):
        """Changing teacher to admin creates 6 admin balances"""
        self.client.post(reverse('edit_user', args=[self.teacher.id]), {
            'first_name': self.teacher.first_name or 'Test',
            'last_name': self.teacher.last_name or 'Test',
            'email': self.teacher.email,
            'role': 'admin', 'department': '',
        })
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.role, 'admin')
        balances = LeaveBalance.objects.filter(user=self.teacher)
        self.assertEqual(balances.count(), 6)

    def test_hr_can_delete_admin(self):
        admin_id = self.admin.id
        self.client.post(reverse('delete_user', args=[admin_id]))
        self.assertFalse(User.objects.filter(id=admin_id).exists())

    def test_hr_can_delete_any_leave(self):
        """HR can delete leaves — approved leave restores balance"""
        past_leave = Leave.objects.create(
            user=self.admin, leave_type='vacation_leave',
            reason_for_leave='Test',
            start_leave=date.today() - timedelta(days=10),
            end_leave=date.today() - timedelta(days=5),
            status='approved', half_day='none',
        )
        future_leave = Leave.objects.create(
            user=self.admin, leave_type='vacation_leave',
            reason_for_leave='Test',
            start_leave=date.today() + timedelta(days=10),
            end_leave=date.today() + timedelta(days=15),
            status='approved', half_day='none',
        )
        self.client.post(reverse('delete_leave', args=[past_leave.id]))
        self.client.post(reverse('delete_leave', args=[future_leave.id]))
        self.assertFalse(Leave.objects.filter(id=past_leave.id).exists())
        self.assertFalse(Leave.objects.filter(id=future_leave.id).exists())

    def test_hr_can_export_excel(self):
        response = self.client.get(reverse('export_leaves'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    def test_non_hr_cannot_export_excel(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.get(reverse('export_leaves'))
        self.assertEqual(response.status_code, 302)

    def test_last_hr_cannot_delete_itself(self):
        self.hr2.delete()
        self.client.post(reverse('delete_account'))
        self.assertTrue(User.objects.filter(username='hr01').exists())

    def test_hr_can_delete_itself_if_another_exists(self):
        self.client.post(reverse('delete_account'))
        self.assertFalse(User.objects.filter(username='hr01').exists())

    def test_hr_can_access_archives(self):
        response = self.client.get(reverse('archives'))
        self.assertEqual(response.status_code, 200)

    def test_non_hr_cannot_access_archives(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.get(reverse('archives'))
        self.assertEqual(response.status_code, 302)

    def test_hr_can_view_user_detail(self):
        response = self.client.get(reverse('user_detail', args=[self.admin.id]))
        self.assertEqual(response.status_code, 200)

    def test_non_hr_cannot_view_user_detail(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.get(reverse('user_detail', args=[self.admin.id]))
        self.assertEqual(response.status_code, 302)

    def test_hr_dashboard_shows_alert_when_no_hos(self):
        response = self.client.get(reverse('dashboard'))
        self.assertTrue(response.context['no_hos'])

    def test_hr_dashboard_shows_alert_when_no_hoa(self):
        self.hoa.delete()
        response = self.client.get(reverse('dashboard'))
        self.assertTrue(response.context['no_hoa'])

    def test_hr_dashboard_shows_hods_without_dept(self):
        hod_no_dept = User.objects.create_user(
            username='hod_nodept', email='hn@gesm.org', password='TestPass1234!',
            role='head_of_department', department=None, is_active=True,
        )
        response = self.client.get(reverse('dashboard'))
        self.assertIn(hod_no_dept, response.context['hods_no_dept'])

    def test_hr_dashboard_shows_teachers_without_superior(self):
        teacher_no_sup = User.objects.create_user(
            username='t_nosup', email='tns@gesm.org', password='TestPass1234!',
            role='teacher', superior=None, is_active=True,
        )
        response = self.client.get(reverse('dashboard'))
        self.assertIn(teacher_no_sup, response.context['teachers_no_superior'])

    def test_user_detail_teacher_shows_30day_balance(self):
        """HR sees teacher balance as 30 days global"""
        response = self.client.get(reverse('user_detail', args=[self.teacher.id]))
        leave_summary = response.context['leave_summary']
        self.assertEqual(len(leave_summary), 1)
        self.assertEqual(leave_summary[0]['total'], 30)

    def test_user_detail_hos_shows_no_balance(self):
        """HR sees no balance for HOS (doesn't submit leaves)"""
        hos = User.objects.create_user(
            username='hos01', email='hos@gesm.org', password='TestPass1234!',
            role='head_of_school', is_active=True,
        )
        response = self.client.get(reverse('user_detail', args=[hos.id]))
        leave_summary = response.context['leave_summary']
        self.assertEqual(len(leave_summary), 0)

    def test_user_detail_hoa_shows_no_balance(self):
        """HR sees no balance for HOA (doesn't submit leaves)"""
        response = self.client.get(reverse('user_detail', args=[self.hoa.id]))
        leave_summary = response.context['leave_summary']
        self.assertEqual(len(leave_summary), 0)


class SecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher01', email='t@gesm.org', password='TestPass1234!',
            role='teacher', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.admin = User.objects.create_user(
            username='admin01', email='admin@gesm.org', password='TestPass1234!',
            role='admin', is_active=True, is_approved=True, is_email_verified=True,
        )

    def test_csrf_protection(self):
        client_no_csrf = Client(enforce_csrf_checks=True)
        response = client_no_csrf.post(reverse('login'), {
            'username': 'teacher01', 'password': 'TestPass1234!',
        })
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_cannot_submit_leave(self):
        response = self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Test',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
            'half_day': 'none',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_teacher_redirected_from_archives(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.get(reverse('archives'))
        self.assertEqual(response.status_code, 302)

    def test_teacher_redirected_from_reset_balances(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.post(reverse('reset_balances'))
        self.assertEqual(response.status_code, 302)

    def test_teacher_redirected_from_export(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.get(reverse('export_leaves'))
        self.assertEqual(response.status_code, 302)

    def test_teacher_redirected_from_user_detail(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.get(reverse('user_detail', args=[self.admin.id]))
        self.assertEqual(response.status_code, 302)

    def test_teacher_redirected_from_department_create(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.post(reverse('department_create'), {'name': 'Fake'})
        self.assertEqual(response.status_code, 302)

    def test_teacher_redirected_from_adjust_balance(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.post(reverse('adjust_balance'), {
            'user_id': self.admin.id,
            'balance_type': 'admin',
            'leave_type': 'vacation_leave',
            'days_remaining': 10,
        })
        self.assertEqual(response.status_code, 302)

    def test_password_reset_accessible_without_login(self):
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)

    def test_change_password_requires_login(self):
        response = self.client.get(reverse('change_password'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_sidebar_hidden_when_not_logged_in(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'fas fa-tachometer-alt')
        self.assertNotContains(response, reverse('submit_leave'))
        self.assertNotContains(response, reverse('archives'))

    def test_scheduling_team_cannot_access_adjust_balance(self):
        sched = User.objects.create_user(
            username='sched01', email='sched@gesm.org', password='TestPass1234!',
            role='scheduling_team', is_active=True,
        )
        self.client.login(username='sched01', password='TestPass1234!')
        response = self.client.post(reverse('adjust_balance'), {
            'user_id': self.admin.id, 'balance_type': 'admin',
            'leave_type': 'vacation_leave', 'days_remaining': 10,
        })
        self.assertEqual(response.status_code, 302)

    def test_calendar_access_cannot_submit_leave(self):
        """Calendar access role has no submit leave access"""
        cal = User.objects.create_user(
            username='cal01', email='cal@gesm.org', password='TestPass1234!',
            role='calendar_access', is_active=True,
        )
        self.client.login(username='cal01', password='TestPass1234!')
        response = self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Test',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
            'half_day': 'none',
        })
        self.assertEqual(Leave.objects.filter(user=cal).count(), 0)
