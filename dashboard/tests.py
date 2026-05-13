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
            username='hod01', email='hod@gesm.fr', password='TestPass1234!',
            role='head_of_department', department=self.dept,
            is_active=True, is_approved=True, is_email_verified=True,
        )
        self.dept.head = self.hod
        self.dept.save()
        self.teacher = User.objects.create_user(
            username='teacher01', email='t@gesm.fr', password='TestPass1234!',
            role='teacher', department=self.dept, superior=self.hod,
            is_active=True, is_approved=True, is_email_verified=True,
        )
        self.employee = User.objects.create_user(
            username='emp01', email='emp@gesm.fr', password='TestPass1234!',
            role='employee', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.hos = User.objects.create_user(
            username='hos01', email='hos@gesm.fr', password='TestPass1234!',
            role='head_of_school', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.hoa = User.objects.create_user(
            username='hoa01', email='hoa@gesm.fr', password='TestPass1234!',
            role='head_of_admin', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.hr = User.objects.create_user(
            username='hr01', email='hr@gesm.fr', password='TestPass1234!',
            role='hr', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.scheduling = User.objects.create_user(
            username='sched01', email='sched@gesm.fr', password='TestPass1234!',
            role='scheduling_team', is_active=True, is_approved=True, is_email_verified=True,
        )

    def test_unauthenticated_redirected_to_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_all_dashboards_load_200(self):
        """Every role dashboard returns 200"""
        roles = [
            ('teacher01', 200), ('emp01', 200), ('hod01', 200),
            ('hos01', 200), ('hoa01', 200), ('hr01', 200), ('sched01', 200),
        ]
        for username, expected in roles:
            self.client.login(username=username, password='TestPass1234!')
            response = self.client.get(reverse('dashboard'))
            self.assertEqual(response.status_code, expected, f'Failed for {username}')

    def test_teacher_cannot_access_calendar(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 302)

    def test_employee_cannot_access_calendar(self):
        self.client.login(username='emp01', password='TestPass1234!')
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 302)

    def test_scheduling_team_can_access_calendar(self):
        self.client.login(username='sched01', password='TestPass1234!')
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

    def test_hoa_sees_hr_leave_in_dashboard(self):
        hr_leave = Leave.objects.create(
            user=self.hr, leave_type='vacation_leave',
            reason_for_leave='Test',
            start_leave=date.today() + timedelta(days=10),
            end_leave=date.today() + timedelta(days=15),
            status='pending_hoa',
        )
        self.client.login(username='hoa01', password='TestPass1234!')
        response = self.client.get(reverse('dashboard'))
        self.assertIn(hr_leave, response.context['leaves'])

    def test_hoa_calendar_includes_hr_leaves(self):
        Leave.objects.create(
            user=self.hr, leave_type='vacation_leave',
            reason_for_leave='Test', start_leave=date.today(),
            end_leave=date.today() + timedelta(days=5), status='approved',
        )
        self.client.login(username='hoa01', password='TestPass1234!')
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 200)


class HRFeaturesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.dept = Department.objects.create(name='Mathematics')
        self.hr = User.objects.create_user(
            username='hr01', email='hr@gesm.fr', password='TestPass1234!',
            role='hr', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.hr2 = User.objects.create_user(
            username='hr02', email='hr2@gesm.fr', password='TestPass1234!',
            role='hr', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.hoa = User.objects.create_user(
            username='hoa01', email='hoa@gesm.fr', password='TestPass1234!',
            role='head_of_admin', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.teacher = User.objects.create_user(
            username='teacher01', email='t@gesm.fr', password='TestPass1234!',
            role='teacher', department=self.dept,
            is_active=True, is_approved=True, is_email_verified=True,
        )
        self.employee = User.objects.create_user(
            username='emp01', email='emp@gesm.fr', password='TestPass1234!',
            role='employee', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.client.login(username='hr01', password='TestPass1234!')

    def test_hr_can_promote_teacher_to_hod(self):
        self.client.post(reverse('promote_user', args=[self.teacher.id]), {
            'new_role': 'head_of_department',
        })
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.role, 'head_of_department')

    def test_hr_can_promote_teacher_to_hos(self):
        self.client.post(reverse('promote_user', args=[self.teacher.id]), {
            'new_role': 'head_of_school',
        })
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.role, 'head_of_school')

    def test_hr_can_demote_hod_to_teacher(self):
        hod = User.objects.create_user(
            username='hod01', email='hod@gesm.fr', password='TestPass1234!',
            role='head_of_department', is_active=True,
        )
        self.client.post(reverse('promote_user', args=[hod.id]), {'new_role': 'teacher'})
        hod.refresh_from_db()
        self.assertEqual(hod.role, 'teacher')

    def test_hr_cannot_promote_employee(self):
        self.client.post(reverse('promote_user', args=[self.employee.id]), {
            'new_role': 'head_of_department',
        })
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, 'employee')

    def test_hr_can_edit_user_name(self):
        self.client.post(reverse('edit_user', args=[self.teacher.id]), {
            'first_name': 'NewName',
            'last_name': self.teacher.last_name or 'Test',
            'email': self.teacher.email,
            'role': 'teacher', 'department': '',
        })
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.first_name, 'NewName')

    def test_hr_can_edit_user_role_updates_balance(self):
        """Changing role via edit_user creates correct new balances"""
        LeaveBalance.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            total_days=30, days_used=0, days_remaining=30, carried_over=0,
        )
        self.client.post(reverse('edit_user', args=[self.teacher.id]), {
            'first_name': self.teacher.first_name or 'Test',
            'last_name': self.teacher.last_name or 'Test',
            'email': self.teacher.email,
            'role': 'employee', 'department': '',
        })
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.role, 'employee')
        balances = LeaveBalance.objects.filter(user=self.teacher)
        self.assertEqual(balances.count(), 6)

    def test_hr_can_delete_employee(self):
        emp_id = self.employee.id
        self.client.post(reverse('delete_user', args=[emp_id]))
        self.assertFalse(User.objects.filter(id=emp_id).exists())

    def test_hr_can_delete_hod_without_reassigning(self):
        hod = User.objects.create_user(
            username='hod01', email='hod@gesm.fr', password='TestPass1234!',
            role='head_of_department', department=self.dept, is_active=True,
        )
        hod_id = hod.id
        self.client.post(reverse('delete_user', args=[hod_id]))
        self.assertFalse(User.objects.filter(id=hod_id).exists())

    def test_hr_cannot_delete_last_hos(self):
        hos = User.objects.create_user(
            username='hos01', email='hos@gesm.fr', password='TestPass1234!',
            role='head_of_school', is_active=True,
        )
        self.client.post(reverse('delete_user', args=[hos.id]))
        self.assertTrue(User.objects.filter(id=hos.id).exists())

    def test_hr_can_delete_any_leave(self):
        """HR can delete past AND future leaves"""
        past_leave = Leave.objects.create(
            user=self.employee, leave_type='sick_leave',
            reason_for_leave='Test',
            start_leave=date.today() - timedelta(days=10),
            end_leave=date.today() - timedelta(days=5),
            status='approved',
        )
        future_leave = Leave.objects.create(
            user=self.employee, leave_type='vacation_leave',
            reason_for_leave='Test',
            start_leave=date.today() + timedelta(days=10),
            end_leave=date.today() + timedelta(days=15),
            status='approved',
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
        response = self.client.get(reverse('user_detail', args=[self.employee.id]))
        self.assertEqual(response.status_code, 200)

    def test_non_hr_cannot_view_user_detail(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.get(reverse('user_detail', args=[self.employee.id]))
        self.assertEqual(response.status_code, 302)

    def test_hr_dashboard_shows_alert_when_no_hos(self):
        """HR dashboard shows alert when no HOS exists"""
        response = self.client.get(reverse('dashboard'))
        self.assertTrue(response.context['no_hos'])

    def test_hr_dashboard_shows_alert_when_no_hoa(self):
        """HR dashboard shows alert when no HOA exists"""
        self.hoa.delete()
        response = self.client.get(reverse('dashboard'))
        self.assertTrue(response.context['no_hoa'])

    def test_hr_dashboard_shows_hods_without_dept(self):
        """HR dashboard detects HOD with no department"""
        hod_no_dept = User.objects.create_user(
            username='hod_nodept', email='hn@gesm.fr', password='TestPass1234!',
            role='head_of_department', department=None, is_active=True,
        )
        response = self.client.get(reverse('dashboard'))
        self.assertIn(hod_no_dept, response.context['hods_no_dept'])

    def test_hr_dashboard_shows_teachers_without_superior(self):
        """HR dashboard detects teachers with no superior"""
        teacher_no_sup = User.objects.create_user(
            username='t_nosup', email='tns@gesm.fr', password='TestPass1234!',
            role='teacher', superior=None, is_active=True,
        )
        response = self.client.get(reverse('dashboard'))
        self.assertIn(teacher_no_sup, response.context['teachers_no_superior'])


class SecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher01', email='t@gesm.fr', password='TestPass1234!',
            role='teacher', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.employee = User.objects.create_user(
            username='emp01', email='emp@gesm.fr', password='TestPass1234!',
            role='employee', is_active=True, is_approved=True, is_email_verified=True,
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
        response = self.client.get(reverse('user_detail', args=[self.employee.id]))
        self.assertEqual(response.status_code, 302)

    def test_teacher_redirected_from_department_create(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.post(reverse('department_create'), {'name': 'Fake'})
        self.assertEqual(response.status_code, 302)

    def test_sidebar_hidden_when_not_logged_in(self):
        """Login page should not show sidebar links"""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        # la sidebar ne doit pas contenir de liens de navigation
        self.assertNotContains(response, 'fas fa-tachometer-alt')  # Dashboard icon
        self.assertNotContains(response, reverse('submit_leave'))
        self.assertNotContains(response, reverse('archives'))

    def test_password_reset_accessible_without_login(self):
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)

    def test_change_password_requires_login(self):
        """Unauthenticated user cannot access change password page"""
        response = self.client.get(reverse('change_password'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_change_password_page_loads(self):
        """Authenticated user can access change password page"""
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.get(reverse('change_password'))
        self.assertEqual(response.status_code, 200)

    def test_change_password_success(self):
        """User can successfully change their password"""
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.post(reverse('change_password'), {
            'current_password': 'TestPass1234!',
            'new_password1': 'NewPass5678!',
            'new_password2': 'NewPass5678!',
        })
        self.assertRedirects(response, reverse('dashboard'))
        # vérifie que le nouveau mot de passe fonctionne
        self.teacher.refresh_from_db()
        self.assertTrue(self.teacher.check_password('NewPass5678!'))

    def test_change_password_wrong_current_password(self):
        """Wrong current password is rejected"""
        self.client.login(username='teacher01', password='TestPass1234!')
        self.client.post(reverse('change_password'), {
            'current_password': 'WrongPass!',
            'new_password1': 'NewPass5678!',
            'new_password2': 'NewPass5678!',
        })
        self.teacher.refresh_from_db()
        self.assertTrue(self.teacher.check_password('TestPass1234!'))

    def test_change_password_mismatch(self):
        """Mismatched new passwords are rejected"""
        self.client.login(username='teacher01', password='TestPass1234!')
        self.client.post(reverse('change_password'), {
            'current_password': 'TestPass1234!',
            'new_password1': 'NewPass5678!',
            'new_password2': 'DifferentPass!',
        })
        self.teacher.refresh_from_db()
        self.assertTrue(self.teacher.check_password('TestPass1234!'))

    def test_change_password_too_short(self):
        """Password shorter than 8 characters is rejected"""
        self.client.login(username='teacher01', password='TestPass1234!')
        self.client.post(reverse('change_password'), {
            'current_password': 'TestPass1234!',
            'new_password1': 'short',
            'new_password2': 'short',
        })
        self.teacher.refresh_from_db()
        self.assertTrue(self.teacher.check_password('TestPass1234!'))

    def test_change_password_stays_logged_in(self):
        """User stays logged in after changing password"""
        self.client.login(username='teacher01', password='TestPass1234!')
        self.client.post(reverse('change_password'), {
            'current_password': 'TestPass1234!',
            'new_password1': 'NewPass5678!',
            'new_password2': 'NewPass5678!',
        })
        # doit toujours pouvoir accéder au dashboard
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)