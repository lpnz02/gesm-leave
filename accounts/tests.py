# accounts/test_accounts.py
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, Department
from leaves.models import LeaveBalance


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


# ================================================================
# REGISTRATION TESTS
# ================================================================
class RegistrationTests(TestCase):
   def setUp(self):
       self.client = Client()
       self.dept = Department.objects.create(name='Mathematics')

   def test_teacher_can_register(self):
       """Teacher can register — account inactive until HR approves"""
       self.client.post(reverse('register'), {
           'username': 'teacher01', 'first_name': 'Marine',
           'last_name': 'Dubois', 'email': 'marine@gesm.org',
           'role': 'teacher', 'department': self.dept.id,
           'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
       })
       user = User.objects.get(username='teacher01')
       self.assertFalse(user.is_active)
       self.assertFalse(user.is_email_verified)
       self.assertFalse(user.is_approved)

   def test_admin_can_register(self):
       """Admin can register — no department needed"""
       self.client.post(reverse('register'), {
           'username': 'admin01', 'first_name': 'Rory',
           'last_name': 'Gilmore', 'email': 'rory@gesm.org',
           'role': 'admin', 'password1': 'TestPass1234!',
           'password2': 'TestPass1234!',
       })
       user = User.objects.get(username='admin01')
       self.assertFalse(user.is_active)

   def test_hod_can_register(self):
       """HOD can register with a department"""
       self.client.post(reverse('register'), {
           'username': 'hod01', 'first_name': 'Jean',
           'last_name': 'Martin', 'email': 'hod@gesm.org',
           'role': 'head_of_department', 'department': self.dept.id,
           'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
       })
       self.assertTrue(User.objects.filter(username='hod01').exists())

   def test_hos_can_register(self):
       """HOS can register"""
       self.client.post(reverse('register'), {
           'username': 'hos01', 'first_name': 'Pierre',
           'last_name': 'Dupont', 'email': 'hos@gesm.org',
           'role': 'head_of_school', 'password1': 'TestPass1234!',
           'password2': 'TestPass1234!',
       })
       self.assertTrue(User.objects.filter(username='hos01').exists())

   def test_scheduling_team_can_register(self):
       """Scheduling team can register"""
       self.client.post(reverse('register'), {
           'username': 'sched01', 'first_name': 'Kirk',
           'last_name': 'Gleason', 'email': 'sched@gesm.org',
           'role': 'scheduling_team', 'password1': 'TestPass1234!',
           'password2': 'TestPass1234!',
       })
       self.assertTrue(User.objects.filter(username='sched01').exists())

   def test_cannot_register_as_hr(self):
       """HR role blocked from public registration"""
       self.client.post(reverse('register'), {
           'username': 'fake_hr', 'email': 'fake@gesm.org',
           'role': 'hr', 'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
       })
       self.assertFalse(User.objects.filter(username='fake_hr').exists())

   def test_cannot_register_as_hoa(self):
       """HOA role blocked from public registration"""
       self.client.post(reverse('register'), {
           'username': 'fake_hoa', 'email': 'hoa@gesm.org',
           'role': 'head_of_admin', 'password1': 'TestPass1234!',
           'password2': 'TestPass1234!',
       })
       self.assertFalse(User.objects.filter(username='fake_hoa').exists())

   def test_cannot_register_as_calendar_access(self):
       """Calendar access role blocked from public registration"""
       self.client.post(reverse('register'), {
           'username': 'fake_cal', 'email': 'cal@gesm.org',
           'role': 'calendar_access', 'password1': 'TestPass1234!',
           'password2': 'TestPass1234!',
       })
       self.assertFalse(User.objects.filter(username='fake_cal').exists())

   def test_hod_register_becomes_dept_head(self):
       """HOD who registers becomes head of their department automatically"""
       self.client.post(reverse('register'), {
           'username': 'hod01', 'first_name': 'Jean',
           'last_name': 'Martin', 'email': 'hod@gesm.org',
           'role': 'head_of_department', 'department': self.dept.id,
           'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
       })
       hod = User.objects.get(username='hod01')
       self.dept.refresh_from_db()
       self.assertEqual(self.dept.head, hod)

   def test_hod_register_assigns_superior_to_existing_teachers(self):
       """HOD who registers becomes superior of existing teachers in dept"""
       teacher = make_user('teacher01', 'teacher', dept=self.dept)
       self.client.post(reverse('register'), {
           'username': 'hod01', 'first_name': 'Jean',
           'last_name': 'Martin', 'email': 'hod@gesm.org',
           'role': 'head_of_department', 'department': self.dept.id,
           'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
       })
       hod = User.objects.get(username='hod01')
       teacher.refresh_from_db()
       self.assertEqual(teacher.superior, hod)

   def test_teacher_register_assigned_to_dept_hod(self):
       """Teacher who registers gets dept HOD as superior automatically"""
       hod = make_user('hod01', 'head_of_department', dept=self.dept)
       self.dept.head = hod
       self.dept.save()
       self.client.post(reverse('register'), {
           'username': 'teacher01', 'first_name': 'Marine',
           'last_name': 'Dubois', 'email': 'marine@gesm.org',
           'role': 'teacher', 'department': self.dept.id,
           'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
       })
       teacher = User.objects.get(username='teacher01')
       self.assertEqual(teacher.superior, hod)

   def test_email_verification_token_created(self):
       """Registration creates email verification token"""
       self.client.post(reverse('register'), {
           'username': 'teacher02', 'first_name': 'Paris',
           'last_name': 'Geller', 'email': 'paris@gesm.org',
           'role': 'teacher', 'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
       })
       user = User.objects.get(username='teacher02')
       self.assertIsNotNone(user.email_verification_token)

   def test_email_verification_activates_flag(self):
       """Clicking verification link sets is_email_verified to True"""
       self.client.post(reverse('register'), {
           'username': 'teacher03', 'first_name': 'Lane',
           'last_name': 'Kim', 'email': 'lane@gesm.org',
           'role': 'teacher', 'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
       })
       user = User.objects.get(username='teacher03')
       self.client.get(reverse('verify_email', args=[user.email_verification_token]))
       user.refresh_from_db()
       self.assertTrue(user.is_email_verified)

   def test_unverified_user_cannot_login(self):
       """User who hasn't verified email cannot login"""
       self.client.post(reverse('register'), {
           'username': 'teacher04', 'first_name': 'Michel',
           'last_name': 'Gerard', 'email': 'michel@gesm.org',
           'role': 'teacher', 'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
       })
       response = self.client.post(reverse('login'), {
           'username': 'teacher04', 'password': 'TestPass1234!',
       })
       self.assertNotEqual(response.status_code, 302)


# ================================================================
# LOGIN / SECURITY TESTS
# ================================================================
class LoginTests(TestCase):
   def setUp(self):
       self.client = Client()
       self.active_user = make_user('active', 'teacher')
       self.inactive_user = make_user('inactive', 'teacher', active=False)

   def test_active_user_can_login(self):
       response = self.client.post(reverse('login'), {
           'username': 'active', 'password': 'TestPass1234!',
       })
       self.assertEqual(response.status_code, 302)

   def test_login_redirects_to_dashboard(self):
       response = self.client.post(reverse('login'), {
           'username': 'active', 'password': 'TestPass1234!',
       })
       self.assertRedirects(response, reverse('dashboard'))

   def test_inactive_user_cannot_login(self):
       response = self.client.post(reverse('login'), {
           'username': 'inactive', 'password': 'TestPass1234!',
       })
       self.assertNotEqual(response.status_code, 302)

   def test_wrong_password_fails(self):
       response = self.client.post(reverse('login'), {
           'username': 'active', 'password': 'WrongPass!',
       })
       self.assertNotEqual(response.status_code, 302)

   def test_logout_redirects_to_login(self):
       self.client.login(username='active', password='TestPass1234!')
       response = self.client.get(reverse('logout'))
       self.assertRedirects(response, reverse('login'))

   def test_unauthenticated_dashboard_redirects_to_login(self):
       """Knowing the URL is not enough — must be logged in"""
       response = self.client.get(reverse('dashboard'))
       self.assertEqual(response.status_code, 302)
       self.assertIn('login', response.url)

   def test_unauthenticated_cannot_access_calendar(self):
       response = self.client.get(reverse('calendar'))
       self.assertEqual(response.status_code, 302)
       self.assertIn('login', response.url)

   def test_unauthenticated_cannot_access_user_detail(self):
       u = make_user('target', 'teacher')
       response = self.client.get(reverse('user_detail', args=[u.id]))
       self.assertEqual(response.status_code, 302)
       self.assertIn('login', response.url)

   def test_teacher_cannot_access_another_users_detail(self):
       """Teacher cannot view another user's profile via URL"""
       make_user('teacher_spy', 'teacher')
       target = make_user('target_user', 'admin')
       self.client.login(username='teacher_spy', password='TestPass1234!')
       response = self.client.get(reverse('user_detail', args=[target.id]))
       self.assertEqual(response.status_code, 302)

   def test_unauthenticated_cannot_export_excel(self):
       response = self.client.get(reverse('export_leaves'))
       self.assertEqual(response.status_code, 302)
       self.assertIn('login', response.url)

   def test_teacher_cannot_export_excel(self):
       make_user('teacher_excel', 'teacher')
       self.client.login(username='teacher_excel', password='TestPass1234!')
       response = self.client.get(reverse('export_leaves'))
       self.assertEqual(response.status_code, 302)

   def test_teacher_dashboard_does_not_show_hr_content(self):
       """Teacher sees their own dashboard, not HR content"""
       make_user('teacher_x', 'teacher')
       self.client.login(username='teacher_x', password='TestPass1234!')
       response = self.client.get(reverse('dashboard'))
       self.assertEqual(response.status_code, 200)
       self.assertNotContains(response, 'All Leave Requests')


# ================================================================
# CHANGE PASSWORD TESTS
# ================================================================
class ChangePasswordTests(TestCase):
   def setUp(self):
       self.client = Client()
       self.teacher = make_user('teacher01', 'teacher')

   def test_change_password_requires_login(self):
       response = self.client.get(reverse('change_password'))
       self.assertEqual(response.status_code, 302)
       self.assertIn('login', response.url)

   def test_change_password_success(self):
       self.client.login(username='teacher01', password='TestPass1234!')
       response = self.client.post(reverse('change_password'), {
           'current_password': 'TestPass1234!',
           'new_password1': 'NewPass5678!',
           'new_password2': 'NewPass5678!',
       })
       self.assertRedirects(response, reverse('dashboard'))
       self.teacher.refresh_from_db()
       self.assertTrue(self.teacher.check_password('NewPass5678!'))

   def test_change_password_wrong_current(self):
       self.client.login(username='teacher01', password='TestPass1234!')
       self.client.post(reverse('change_password'), {
           'current_password': 'WrongPass!',
           'new_password1': 'NewPass5678!',
           'new_password2': 'NewPass5678!',
       })
       self.teacher.refresh_from_db()
       self.assertTrue(self.teacher.check_password('TestPass1234!'))

   def test_change_password_mismatch(self):
       self.client.login(username='teacher01', password='TestPass1234!')
       self.client.post(reverse('change_password'), {
           'current_password': 'TestPass1234!',
           'new_password1': 'NewPass5678!',
           'new_password2': 'DifferentPass!',
       })
       self.teacher.refresh_from_db()
       self.assertTrue(self.teacher.check_password('TestPass1234!'))

   def test_change_password_too_short(self):
       self.client.login(username='teacher01', password='TestPass1234!')
       self.client.post(reverse('change_password'), {
           'current_password': 'TestPass1234!',
           'new_password1': 'short',
           'new_password2': 'short',
       })
       self.teacher.refresh_from_db()
       self.assertTrue(self.teacher.check_password('TestPass1234!'))

   def test_change_password_stays_logged_in(self):
       self.client.login(username='teacher01', password='TestPass1234!')
       self.client.post(reverse('change_password'), {
           'current_password': 'TestPass1234!',
           'new_password1': 'NewPass5678!',
           'new_password2': 'NewPass5678!',
       })
       response = self.client.get(reverse('dashboard'))
       self.assertEqual(response.status_code, 200)

   def test_change_username_only(self):
       self.client.login(username='teacher01', password='TestPass1234!')
       self.client.post(reverse('change_password'), {
           'new_username': 'teacher_new',
       })
       self.teacher.refresh_from_db()
       self.assertEqual(self.teacher.username, 'teacher_new')
       self.assertTrue(self.teacher.check_password('TestPass1234!'))

   def test_change_username_already_taken(self):
       make_user('taken', 'teacher')
       self.client.login(username='teacher01', password='TestPass1234!')
       self.client.post(reverse('change_password'), {
           'new_username': 'taken',
       })
       self.teacher.refresh_from_db()
       self.assertEqual(self.teacher.username, 'teacher01')


# ================================================================
# HR APPROVAL TESTS
# ================================================================
class HRApprovalTests(TestCase):
   def setUp(self):
       self.client = Client()
       self.hr = make_user('hr01', 'hr')
       self.pending_admin = make_user('pending_admin', 'admin', active=False)
       self.pending_teacher = make_user('pending_teacher', 'teacher', active=False)
       self.pending_hod = make_user('pending_hod', 'head_of_department', active=False)
       self.client.login(username='hr01', password='TestPass1234!')

   def test_hr_can_approve_admin(self):
       self.client.get(reverse('approve_user', args=[self.pending_admin.id]))
       self.pending_admin.refresh_from_db()
       self.assertTrue(self.pending_admin.is_active)
       self.assertTrue(self.pending_admin.is_approved)

   def test_admin_gets_6_balances_on_approval(self):
       self.client.get(reverse('approve_user', args=[self.pending_admin.id]))
       balances = LeaveBalance.objects.filter(user=self.pending_admin)
       self.assertEqual(balances.count(), 6)
       vacation = balances.get(leave_type='vacation_leave')
       self.assertEqual(vacation.total_days, 15)
       sick = balances.get(leave_type='sick_leave')
       self.assertEqual(sick.total_days, 15)
       emergency = balances.get(leave_type='emergency_leave')
       self.assertEqual(emergency.total_days, 3)
       bereavement = balances.get(leave_type='bereavement_leave')
       self.assertEqual(bereavement.total_days, 5)

   def test_teacher_gets_single_30day_balance(self):
       self.client.get(reverse('approve_user', args=[self.pending_teacher.id]))
       balances = LeaveBalance.objects.filter(user=self.pending_teacher)
       self.assertEqual(balances.count(), 1)
       self.assertEqual(balances.first().leave_type, 'vacation_leave')
       self.assertEqual(balances.first().total_days, 30)

   def test_hod_gets_single_30day_balance(self):
       self.client.get(reverse('approve_user', args=[self.pending_hod.id]))
       balances = LeaveBalance.objects.filter(user=self.pending_hod)
       self.assertEqual(balances.count(), 1)
       self.assertEqual(balances.first().total_days, 30)

   def test_hr_can_reject_user(self):
       user_id = self.pending_admin.id
       self.client.get(reverse('reject_user', args=[user_id]))
       self.assertFalse(User.objects.filter(id=user_id).exists())

   def test_non_hr_cannot_approve(self):
       teacher = make_user('t_nohr', 'teacher')
       self.client.login(username='t_nohr', password='TestPass1234!')
       self.client.get(reverse('approve_user', args=[self.pending_admin.id]))
       self.pending_admin.refresh_from_db()
       self.assertFalse(self.pending_admin.is_active)

   def test_unauthenticated_cannot_approve(self):
       self.client.logout()
       response = self.client.get(reverse('approve_user', args=[self.pending_admin.id]))
       self.assertEqual(response.status_code, 302)


# ================================================================
# HR CREATE ADMIN TESTS
# ================================================================
class HRCreateAdminTests(TestCase):
   def setUp(self):
       self.client = Client()
       self.hr = make_user('hr01', 'hr')
       self.client.login(username='hr01', password='TestPass1234!')

   def test_hr_can_create_hoa(self):
       self.client.post(reverse('create_admin_user'), {
           'username': 'hoa01', 'first_name': 'Francois',
           'last_name': 'Mercier', 'email': 'hoa@gesm.org',
           'role': 'head_of_admin', 'password': 'TestPass1234!',
       })
       user = User.objects.get(username='hoa01')
       self.assertTrue(user.is_active)
       self.assertTrue(user.is_approved)
       self.assertEqual(user.role, 'head_of_admin')

   def test_hr_can_create_another_hr(self):
       self.client.post(reverse('create_admin_user'), {
           'username': 'hr02', 'first_name': 'Sookie',
           'last_name': 'James', 'email': 'sookie@gesm.org',
           'role': 'hr', 'password': 'TestPass1234!',
       })
       self.assertTrue(User.objects.filter(username='hr02', role='hr').exists())

   def test_hr_can_create_calendar_access(self):
       self.client.post(reverse('create_admin_user'), {
           'username': 'cal01', 'first_name': 'Lorelai',
           'last_name': 'Gilmore', 'email': 'cal@gesm.org',
           'role': 'calendar_access', 'password': 'TestPass1234!',
       })
       self.assertTrue(User.objects.filter(username='cal01', role='calendar_access').exists())

   def test_hr_can_delete_another_hr(self):
       hr2 = make_user('hr02', 'hr')
       self.client.post(reverse('delete_user', args=[hr2.id]))
       self.assertFalse(User.objects.filter(id=hr2.id).exists())

   def test_last_hr_cannot_delete_themselves(self):
       """Last HR account cannot be deleted"""
       response = self.client.post(reverse('delete_own_account'))
       self.assertTrue(User.objects.filter(username='hr01').exists())

   def test_non_hr_cannot_access_create_admin(self):
       teacher = make_user('t01', 'teacher')
       self.client.login(username='t01', password='TestPass1234!')
       response = self.client.get(reverse('create_admin_user'))
       self.assertEqual(response.status_code, 302)

   def test_scheduling_team_cannot_access_create_admin(self):
       sched = make_user('sched01', 'scheduling_team')
       self.client.login(username='sched01', password='TestPass1234!')
       response = self.client.get(reverse('create_admin_user'))
       self.assertEqual(response.status_code, 302)


# ================================================================
# DEPARTMENT TESTS
# ================================================================
class DepartmentTests(TestCase):
   def setUp(self):
       self.client = Client()
       self.hr = make_user('hr01', 'hr')
       self.dept = Department.objects.create(name='Mathematics')
       self.client.login(username='hr01', password='TestPass1234!')

   def test_hr_can_create_department(self):
       self.client.post(reverse('department_create'), {'name': 'Sciences'})
       self.assertTrue(Department.objects.filter(name='Sciences').exists())

   def test_hr_can_delete_empty_department(self):
       dept_id = self.dept.id
       self.client.post(reverse('department_delete', args=[dept_id]))
       self.assertFalse(Department.objects.filter(id=dept_id).exists())

   def test_department_list_shows_teacher_count(self):
       make_user('teacher01', 'teacher', dept=self.dept)
       make_user('teacher02', 'teacher', dept=self.dept)
       response = self.client.get(reverse('department_list'))
       self.assertEqual(response.status_code, 200)
       dept_data = response.context['dept_data']
       maths = next(d for d in dept_data if d['dept'].name == 'Mathematics')
       self.assertEqual(maths['teacher_count'], 2)

   def test_department_list_shows_hod(self):
       hod = make_user('hod01', 'head_of_department', dept=self.dept)
       self.dept.head = hod
       self.dept.save()
       response = self.client.get(reverse('department_list'))
       self.assertEqual(response.status_code, 200)
       dept_data = response.context['dept_data']
       maths = next(d for d in dept_data if d['dept'].name == 'Mathematics')
       self.assertEqual(maths['dept'].head, hod)

   def test_downgraded_hod_not_shown_in_dept(self):
       """HOD downgraded to teacher no longer shown as HOD in dept"""
       hod = make_user('hod01', 'head_of_department', dept=self.dept)
       self.dept.head = hod
       self.dept.save()
       self.client.post(reverse('edit_user', args=[hod.id]), {
           'first_name': hod.first_name, 'last_name': hod.last_name,
           'email': hod.email, 'role': 'teacher',
       })
       self.dept.refresh_from_db()
       if self.dept.head:
           self.assertNotEqual(self.dept.head.role, 'head_of_department')

   def test_department_delete_warns_if_hod_assigned(self):
       make_user('hod01', 'head_of_department', dept=self.dept)
       response = self.client.post(
           reverse('department_delete', args=[self.dept.id]), follow=True
       )
       messages = list(response.context['messages'])
       self.assertTrue(any('Warning' in str(m) or 'HOD' in str(m) for m in messages))

   def test_non_hr_cannot_create_department(self):
       teacher = make_user('t01', 'teacher')
       self.client.login(username='t01', password='TestPass1234!')
       self.client.post(reverse('department_create'), {'name': 'Fake'})
       self.assertFalse(Department.objects.filter(name='Fake').exists())
