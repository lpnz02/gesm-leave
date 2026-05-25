# dashboard/test_dashboard.py
from django.test import TestCase, Client
from django.urls import reverse
from datetime import date, timedelta
from accounts.models import User, Department
from leaves.models import Leave, LeaveBalance
from dashboard.models import BackToWork, PaySlipRequest, CertificateRequest


def make_user(username, role, dept=None, superior=None, active=True):
   u = User.objects.create_user(
       username=username, email=f'{username}@gesm.org',
       password='TestPass1234!', role=role,
       is_active=active, is_approved=active, is_email_verified=active,
   )
   if dept: u.department = dept
   if superior: u.superior = superior
   u.save()
   return u


def make_leave(user, status='pending_hod', leave_type='vacation_leave',
              start=None, end=None, half_day='none'):
   if not start: start = date.today() + timedelta(days=10)
   if not end: end = date.today() + timedelta(days=12)
   return Leave.objects.create(
       user=user, leave_type=leave_type, status=status,
       start_leave=start, end_leave=end,
       reason_for_leave='Test reason', half_day=half_day,
   )


# ================================================================
# DASHBOARD ACCESS TESTS
# ================================================================
class DashboardAccessTests(TestCase):
   def setUp(self):
       self.client = Client()
       self.dept = Department.objects.create(name='Mathematics')
       self.hod = make_user('hod01', 'head_of_department', dept=self.dept)
       self.dept.head = self.hod
       self.dept.save()
       self.teacher = make_user('teacher01', 'teacher', dept=self.dept, superior=self.hod)
       self.admin = make_user('admin01', 'admin')
       self.hos = make_user('hos01', 'head_of_school')
       self.hoa = make_user('hoa01', 'head_of_admin')
       self.hr = make_user('hr01', 'hr')
       self.sched = make_user('sched01', 'scheduling_team')
       self.cal = make_user('cal01', 'calendar_access')

       LeaveBalance.objects.create(
           user=self.teacher, leave_type='vacation_leave',
           total_days=30, days_used=0, days_remaining=30, carried_over=0,
       )
       LeaveBalance.objects.create(
           user=self.hod, leave_type='vacation_leave',
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
       for username in [
           'teacher01', 'admin01', 'hod01', 'hos01',
           'hoa01', 'hr01', 'sched01', 'cal01'
       ]:
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
       admin_leave = make_leave(self.admin, status='pending_hoa', leave_type='vacation_leave')
       self.client.login(username='hoa01', password='TestPass1234!')
       response = self.client.get(reverse('dashboard'))
       self.assertIn(admin_leave, response.context['leaves'])

   def test_hoa_sees_hr_leave_in_dashboard(self):
       hr_leave = make_leave(self.hr, status='pending_hoa', leave_type='vacation_leave')
       self.client.login(username='hoa01', password='TestPass1234!')
       response = self.client.get(reverse('dashboard'))
       self.assertIn(hr_leave, response.context['leaves'])

   def test_teacher_balance_shows_2_categories(self):
       self.client.login(username='teacher01', password='TestPass1234!')
       response = self.client.get(reverse('dashboard'))
       leave_summary = response.context['leave_summary']
       self.assertEqual(len(leave_summary), 2)
       categories = [item['category'] for item in leave_summary]
       self.assertIn('sick', categories)
       self.assertIn('special', categories)

   def test_admin_balance_shows_6_categories(self):
       self.client.login(username='admin01', password='TestPass1234!')
       response = self.client.get(reverse('dashboard'))
       leave_summary = response.context['leave_summary']
       self.assertEqual(len(leave_summary), 6)

   def test_scheduling_team_calendar_no_unpaid_color(self):
       """Scheduling team calendar shows no red — unpaid leaves appear blue"""
       Leave.objects.create(
           user=self.teacher, leave_type='vacation_leave',
           reason_for_leave='Test', start_leave=date.today(),
           end_leave=date.today() + timedelta(days=2),
           status='approved', half_day='none', is_unpaid=True,
       )
       self.client.login(username='sched01', password='TestPass1234!')
       response = self.client.get(reverse('calendar'))
       calendar_data = response.context['calendar_data']
       found_red = False
       for week in calendar_data:
           for day in week:
               for absent in day['absents']:
                   if absent['color'] == '#dc3545':
                       found_red = True
       self.assertFalse(found_red)

   def test_calendar_unpaid_red_for_hr(self):
       """HR calendar shows unpaid leave in red"""
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

   def test_calendar_paid_leave_blue(self):
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


   def test_sick_leave_pending_shows_grey_in_calendar(self):
       Leave.objects.create(
           user=self.teacher, leave_type='sick_leave',
           reason_for_leave='Sick', start_leave=date.today(),
           end_leave=date.today() + timedelta(days=1),
           status='pending_hod', half_day='none',
       )
       self.client.login(username='hr01', password='TestPass1234!')
       response = self.client.get(reverse('calendar'))
       calendar_data = response.context['calendar_data']
       found_grey = False
       for week in calendar_data:
           for day in week:
               for absent in day['absents']:
                   if absent['color'] == '#adb5bd':
                       found_grey = True
       self.assertTrue(found_grey)

   def test_hod_can_view_teacher_remaining_in_overview(self):
       """HOD sees remaining days in teacher overview"""
       self.client.login(username='hod01', password='TestPass1234!')
       response = self.client.get(reverse('user_detail', args=[self.teacher.id]))
       self.assertEqual(response.status_code, 200)
       leave_summary = response.context['leave_summary']
       special = next((i for i in leave_summary if i.get('category') == 'special'), None)
       self.assertIsNotNone(special)
       self.assertIn('remaining', special)

   def test_back_to_work_only_teacher_hod(self):
       """Only teacher and HOD can access back_to_work"""
       for username, role, should_access in [
           ('teacher01', 'teacher', True),
           ('hod01', 'head_of_department', True),
           ('admin01', 'admin', False),
           ('hr01', 'hr', False),
       ]:
           self.client.login(username=username, password='TestPass1234!')
           response = self.client.get(reverse('back_to_work'))
           if should_access:
               self.assertEqual(response.status_code, 200,
                   f'{username} should access back_to_work')
           else:
               self.assertEqual(response.status_code, 302,
                   f'{username} should NOT access back_to_work')

   def test_certificate_not_for_hr(self):
       """HR cannot access certificate of employment"""
       self.client.login(username='hr01', password='TestPass1234!')
       response = self.client.get(reverse('certificate'))
       self.assertRedirects(response, reverse('dashboard'))

   def test_certificate_accessible_for_teacher_hod_hos(self):
       """Teacher, HOD, HOS can access certificate"""
       for username in ['teacher01', 'hod01', 'hos01']:
           self.client.login(username=username, password='TestPass1234!')
           response = self.client.get(reverse('certificate'))
           self.assertEqual(response.status_code, 200, f'{username} should access certificate')

   def test_pay_slip_accessible_for_teacher_hod_hos_admin_hr(self):
       """Teacher, HOD, HOS, Admin, HR can access pay_slip"""
       for username in ['teacher01', 'hod01', 'hos01', 'admin01', 'hr01']:
           self.client.login(username=username, password='TestPass1234!')
           response = self.client.get(reverse('pay_slip'))
           self.assertEqual(response.status_code, 200, f'{username} should access pay_slip')


# ================================================================
# HR FEATURES TESTS
# ================================================================
class HRFeaturesTests(TestCase):
   def setUp(self):
       self.client = Client()
       self.dept = Department.objects.create(name='Mathematics')
       self.hr = make_user('hr01', 'hr')
       self.hr2 = make_user('hr02', 'hr')
       self.hoa = make_user('hoa01', 'head_of_admin')
       self.teacher = make_user('teacher01', 'teacher', dept=self.dept)
       self.admin = make_user('admin01', 'admin')
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

   def test_hr_edit_teacher_to_admin_creates_6_balances(self):
       self.client.post(reverse('edit_user', args=[self.teacher.id]), {
           'first_name': self.teacher.first_name or 'Test',
           'last_name': self.teacher.last_name or 'Test',
           'email': self.teacher.email,
           'role': 'admin', 'department': '',
       })
       self.teacher.refresh_from_db()
       self.assertEqual(self.teacher.role, 'admin')
       self.assertEqual(LeaveBalance.objects.filter(user=self.teacher).count(), 6)

   def test_hr_edit_admin_to_teacher_creates_1_balance(self):
       self.client.post(reverse('edit_user', args=[self.admin.id]), {
           'first_name': self.admin.first_name or 'Test',
           'last_name': self.admin.last_name or 'Test',
           'email': self.admin.email,
           'role': 'teacher', 'department': self.dept.id,
       })
       self.admin.refresh_from_db()
       self.assertEqual(self.admin.role, 'teacher')
       balances = LeaveBalance.objects.filter(user=self.admin)
       self.assertEqual(balances.count(), 1)
       self.assertEqual(balances.first().total_days, 30)

   def test_hr_promote_teacher_to_hod_sets_dept_head(self):
       self.client.post(reverse('edit_user', args=[self.teacher.id]), {
           'first_name': self.teacher.first_name or 'Test',
           'last_name': self.teacher.last_name or 'Test',
           'email': self.teacher.email,
           'role': 'head_of_department', 'department': self.dept.id,
       })
       self.dept.refresh_from_db()
       self.teacher.refresh_from_db()
       self.assertEqual(self.teacher.role, 'head_of_department')
       self.assertEqual(self.dept.head, self.teacher)

   def test_hr_downgrade_hod_to_teacher_clears_dept_head(self):
       hod = make_user('hod01', 'head_of_department', dept=self.dept)
       self.dept.head = hod
       self.dept.save()
       self.client.post(reverse('edit_user', args=[hod.id]), {
           'first_name': hod.first_name or 'Test',
           'last_name': hod.last_name or 'Test',
           'email': hod.email,
           'role': 'teacher',
       })
       self.dept.refresh_from_db()
       hod.refresh_from_db()
       self.assertEqual(hod.role, 'teacher')
       self.assertNotEqual(self.dept.head, hod)

   def test_hr_downgrade_hod_clears_teachers_superior(self):
       hod = make_user('hod01', 'head_of_department', dept=self.dept)
       self.dept.head = hod
       self.dept.save()
       teacher2 = make_user('teacher02', 'teacher', dept=self.dept, superior=hod)
       self.client.post(reverse('edit_user', args=[hod.id]), {
           'first_name': hod.first_name or 'Test',
           'last_name': hod.last_name or 'Test',
           'email': hod.email,
           'role': 'teacher',
       })
       teacher2.refresh_from_db()
       self.assertIsNone(teacher2.superior)

   def test_hr_promote_teacher_to_hos_changes_dashboard(self):
       self.client.post(reverse('edit_user', args=[self.teacher.id]), {
           'first_name': self.teacher.first_name or 'Test',
           'last_name': self.teacher.last_name or 'Test',
           'email': self.teacher.email,
           'role': 'head_of_school',
       })
       self.teacher.refresh_from_db()
       self.assertEqual(self.teacher.role, 'head_of_school')
       self.client.login(username='teacher01', password='TestPass1234!')
       response = self.client.get(reverse('dashboard'))
       self.assertEqual(response.status_code, 200)
       self.assertTemplateUsed(response, 'dashboard/hos_dashboard.html')

   def test_hr_can_delete_user(self):
       admin_id = self.admin.id
       self.client.post(reverse('delete_user', args=[admin_id]))
       self.assertFalse(User.objects.filter(id=admin_id).exists())

   def test_hr_can_delete_any_leave(self):
       leave = make_leave(self.admin, status='approved', leave_type='vacation_leave')
       self.client.post(reverse('delete_leave', args=[leave.id]))
       self.assertFalse(Leave.objects.filter(id=leave.id).exists())

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

   def test_non_hr_cannot_view_user_detail_of_others(self):
       self.client.login(username='teacher01', password='TestPass1234!')
       response = self.client.get(reverse('user_detail', args=[self.admin.id]))
       self.assertEqual(response.status_code, 302)

   def test_hod_can_view_teacher_detail(self):
       hod = make_user('hod01', 'head_of_department', dept=self.dept)
       self.dept.head = hod
       self.dept.save()
       self.client.login(username='hod01', password='TestPass1234!')
       response = self.client.get(reverse('user_detail', args=[self.teacher.id]))
       self.assertEqual(response.status_code, 200)

   def test_hos_can_view_teacher_detail(self):
       hos = make_user('hos01', 'head_of_school')
       self.client.login(username='hos01', password='TestPass1234!')
       response = self.client.get(reverse('user_detail', args=[self.teacher.id]))
       self.assertEqual(response.status_code, 200)

   def test_hoa_can_view_admin_detail(self):
       self.client.login(username='hoa01', password='TestPass1234!')
       response = self.client.get(reverse('user_detail', args=[self.admin.id]))
       self.assertEqual(response.status_code, 200)

   def test_hr_dashboard_no_hos_alert(self):
       response = self.client.get(reverse('dashboard'))
       self.assertTrue(response.context['no_hos'])

   def test_hr_dashboard_no_hoa_alert(self):
       self.hoa.delete()
       response = self.client.get(reverse('dashboard'))
       self.assertTrue(response.context['no_hoa'])

   def test_hr_dashboard_shows_hods_without_dept(self):
       hod_no_dept = make_user('hod_nodept', 'head_of_department')
       response = self.client.get(reverse('dashboard'))
       self.assertIn(hod_no_dept, response.context['hods_no_dept'])

   def test_hr_dashboard_shows_teachers_without_superior(self):
       teacher_no_sup = make_user('t_nosup', 'teacher')
       response = self.client.get(reverse('dashboard'))
       self.assertIn(teacher_no_sup, response.context['teachers_no_superior'])

   def test_user_detail_teacher_shows_sick_and_special(self):
       response = self.client.get(reverse('user_detail', args=[self.teacher.id]))
       leave_summary = response.context['leave_summary']
       self.assertEqual(len(leave_summary), 2)
       categories = [item['category'] for item in leave_summary]
       self.assertIn('sick', categories)
       self.assertIn('special', categories)

   def test_user_detail_shows_remaining_days_for_teacher(self):
       """HR/HOD/HOS see remaining days in teacher overview"""
       response = self.client.get(reverse('user_detail', args=[self.teacher.id]))
       leave_summary = response.context['leave_summary']
       special = next((i for i in leave_summary if i.get('category') == 'special'), None)
       self.assertIsNotNone(special)
       self.assertIn('remaining', special)
       self.assertEqual(special['remaining'], 30.0)

   def test_user_detail_hos_shows_no_balance(self):
       hos = make_user('hos01', 'head_of_school')
       response = self.client.get(reverse('user_detail', args=[hos.id]))
       leave_summary = response.context['leave_summary']
       self.assertEqual(len(leave_summary), 0)

   def test_user_detail_hoa_shows_no_balance(self):
       response = self.client.get(reverse('user_detail', args=[self.hoa.id]))
       leave_summary = response.context['leave_summary']
       self.assertEqual(len(leave_summary), 0)

   def test_hr_can_adjust_admin_balance(self):
       self.client.post(reverse('adjust_balance'), {
           'user_id': self.admin.id,
           'balance_type': 'admin',
           'leave_type': 'vacation_leave',
           'days_remaining': 10,
       })
       balance = LeaveBalance.objects.get(user=self.admin, leave_type='vacation_leave')
       self.assertEqual(float(balance.days_remaining), 10.0)

   def test_hr_can_adjust_teacher_remaining_days(self):
       """HR can set remaining days for teachers — key feature"""
       self.client.post(reverse('adjust_balance'), {
           'user_id': self.teacher.id,
           'balance_type': 'teacher',
           'days_remaining': 20,
       })
       balance = LeaveBalance.objects.get(user=self.teacher, leave_type='vacation_leave')
       self.assertEqual(float(balance.days_remaining), 20.0)

   def test_reset_balances_resets_teacher_to_30(self):
       balance = LeaveBalance.objects.get(user=self.teacher, leave_type='vacation_leave')
       balance.days_used = 10
       balance.days_remaining = 20
       balance.save()
       self.client.post(reverse('reset_balances'))
       balance.refresh_from_db()
       self.assertEqual(balance.total_days, 30)
       self.assertEqual(balance.days_used, 0)
       self.assertEqual(balance.days_remaining, 30)

   def test_reset_balances_carries_over_admin_vacation(self):
       vacation = LeaveBalance.objects.get(user=self.admin, leave_type='vacation_leave')
       vacation.days_remaining = 10
       vacation.save()
       self.client.post(reverse('reset_balances'))
       vacation.refresh_from_db()
       self.assertEqual(vacation.carried_over, 10)
       self.assertEqual(vacation.total_days, 25)

   def test_reset_balances_does_not_carry_over_sick(self):
       sick = LeaveBalance.objects.get(user=self.admin, leave_type='sick_leave')
       sick.days_remaining = 5
       sick.save()
       self.client.post(reverse('reset_balances'))
       sick.refresh_from_db()
       self.assertEqual(sick.carried_over, 0)
       self.assertEqual(sick.total_days, 15)

   def test_reset_clears_back_to_work_history(self):
       BackToWork.objects.create(
           user=self.teacher, full_name='Teacher One',
           return_date=date.today(), message='',
       )
       self.client.post(reverse('reset_balances'))
       self.assertEqual(BackToWork.objects.count(), 0)

   def test_reset_clears_pay_slip_history(self):
       PaySlipRequest.objects.create(
           user=self.teacher, full_name='Teacher One', month='May 2026',
       )
       self.client.post(reverse('reset_balances'))
       self.assertEqual(PaySlipRequest.objects.count(), 0)

   def test_reset_clears_certificate_history(self):
       CertificateRequest.objects.create(
           user=self.teacher, full_name='Teacher One',
           purpose='Visa', with_salary=False,
       )
       self.client.post(reverse('reset_balances'))
       self.assertEqual(CertificateRequest.objects.count(), 0)

   def test_hr_can_file_leave_for_teacher(self):
       response = self.client.post(reverse('hr_file_leave'), {
           'user_id': self.teacher.id,
           'leave_type': 'vacation_leave',
           'start_leave': '2026-06-01',
           'end_leave': '2026-06-05',
           'half_day': 'none',
           'reason_for_leave': 'Filed by HR',
       })
       leave = Leave.objects.filter(user=self.teacher).first()
       self.assertIsNotNone(leave)
       self.assertEqual(leave.status, 'approved')

   def test_hr_file_leave_updates_teacher_balance(self):
       """HR-filed leave correctly deducts from teacher balance"""
       self.client.post(reverse('hr_file_leave'), {
           'user_id': self.teacher.id,
           'leave_type': 'vacation_leave',
           'start_leave': '2026-06-02',
           'end_leave': '2026-06-06',
           'half_day': 'none',
           'reason_for_leave': 'Filed by HR',
       })
       balance = LeaveBalance.objects.get(user=self.teacher, leave_type='vacation_leave')
       self.assertGreater(balance.days_used, 0)
       self.assertLess(balance.days_remaining, 30)

   def test_non_hr_cannot_access_hr_file_leave(self):
       self.client.login(username='teacher01', password='TestPass1234!')
       response = self.client.get(reverse('hr_file_leave'))
       self.assertRedirects(response, reverse('dashboard'))


# ================================================================
# SECURITY TESTS
# ================================================================
class SecurityTests(TestCase):
   def setUp(self):
       self.client = Client()
       self.teacher = make_user('teacher01', 'teacher')
       self.admin = make_user('admin01', 'admin')

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

   def test_teacher_redirected_from_hr_file_leave(self):
       """Teacher cannot access HR file leave page"""
       self.client.login(username='teacher01', password='TestPass1234!')
       response = self.client.get(reverse('hr_file_leave'))
       self.assertEqual(response.status_code, 302)

   def test_change_password_requires_login(self):
       response = self.client.get(reverse('change_password'))
       self.assertEqual(response.status_code, 302)
       self.assertIn('login', response.url)

   def test_scheduling_team_cannot_access_adjust_balance(self):
       sched = make_user('sched01', 'scheduling_team')
       self.client.login(username='sched01', password='TestPass1234!')
       response = self.client.post(reverse('adjust_balance'), {
           'user_id': self.admin.id, 'balance_type': 'admin',
           'leave_type': 'vacation_leave', 'days_remaining': 10,
       })
       self.assertEqual(response.status_code, 302)

   def test_calendar_access_cannot_submit_leave(self):
       cal = make_user('cal01', 'calendar_access')
       self.client.login(username='cal01', password='TestPass1234!')
       self.client.post(reverse('submit_leave'), {
           'leave_type': 'vacation_leave', 'reason_for_leave': 'Test',
           'start_leave': date.today() + timedelta(days=10),
           'end_leave': date.today() + timedelta(days=15),
           'half_day': 'none',
       })
       self.assertEqual(Leave.objects.filter(user=cal).count(), 0)

   def test_password_reset_accessible_without_login(self):
       response = self.client.get(reverse('password_reset'))
       self.assertEqual(response.status_code, 200)

   def test_sidebar_hidden_when_not_logged_in(self):
       response = self.client.get(reverse('login'))
       self.assertEqual(response.status_code, 200)
       self.assertNotContains(response, reverse('archives'))

   def test_session_cleared_after_logout(self):
       """After logout dashboard is inaccessible"""
       self.client.login(username='teacher01', password='TestPass1234!')
       self.client.get(reverse('logout'))
       response = self.client.get(reverse('dashboard'))
       self.assertEqual(response.status_code, 302)
       self.assertIn('login', response.url)

   def test_back_to_work_blocked_for_admin(self):
       """Admin cannot access back_to_work URL directly"""
       make_user('admin01x', 'admin')
       self.client.login(username='admin01x', password='TestPass1234!')
       response = self.client.get(reverse('back_to_work'))
       self.assertEqual(response.status_code, 302)

   def test_back_to_work_blocked_for_hr(self):
       """HR cannot access back_to_work URL directly"""
       make_user('hr01x', 'hr')
       self.client.login(username='hr01x', password='TestPass1234!')
       response = self.client.get(reverse('back_to_work'))
       self.assertEqual(response.status_code, 302)

   def test_certificate_blocked_for_hr(self):
       """HR cannot access certificate URL directly"""
       make_user('hr02x', 'hr')
       self.client.login(username='hr02x', password='TestPass1234!')
       response = self.client.get(reverse('certificate'))
       self.assertEqual(response.status_code, 302)