# accounts/tests.py
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, Department
from leaves.models import LeaveBalance


class RegistrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.dept = Department.objects.create(name='Mathematics')

    def test_teacher_can_register(self):
        """Teacher can register — account inactive until HR approves"""
        self.client.post(reverse('register'), {
            'username': 'teacher01', 'first_name': 'Marine',
            'last_name': 'Dubois', 'email': 'marine@gesm.fr',
            'role': 'teacher', 'department': self.dept.id,
            'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
        })
        user = User.objects.get(username='teacher01')
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_email_verified)
        self.assertFalse(user.is_approved)

    def test_employee_can_register(self):
        """Employee can register — no department needed"""
        self.client.post(reverse('register'), {
            'username': 'emp01', 'first_name': 'Rory',
            'last_name': 'Gilmore', 'email': 'rory@gesm.fr',
            'role': 'employee', 'password1': 'TestPass1234!',
            'password2': 'TestPass1234!',
        })
        user = User.objects.get(username='emp01')
        self.assertFalse(user.is_active)

    def test_hod_can_register(self):
        """HOD can register with a department"""
        self.client.post(reverse('register'), {
            'username': 'hod01', 'first_name': 'Jean',
            'last_name': 'Martin', 'email': 'hod@gesm.fr',
            'role': 'head_of_department', 'department': self.dept.id,
            'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
        })
        self.assertTrue(User.objects.filter(username='hod01').exists())

    def test_hos_can_register(self):
        """HOS can register"""
        self.client.post(reverse('register'), {
            'username': 'hos01', 'first_name': 'Pierre',
            'last_name': 'Dupont', 'email': 'hos@gesm.fr',
            'role': 'head_of_school', 'password1': 'TestPass1234!',
            'password2': 'TestPass1234!',
        })
        self.assertTrue(User.objects.filter(username='hos01').exists())

    def test_scheduling_team_can_register(self):
        """Scheduling team can register"""
        self.client.post(reverse('register'), {
            'username': 'sched01', 'first_name': 'Kirk',
            'last_name': 'Gleason', 'email': 'sched@gesm.fr',
            'role': 'scheduling_team', 'password1': 'TestPass1234!',
            'password2': 'TestPass1234!',
        })
        self.assertTrue(User.objects.filter(username='sched01').exists())

    def test_cannot_register_as_hr(self):
        """HR role blocked from public registration"""
        self.client.post(reverse('register'), {
            'username': 'fake_hr', 'email': 'fake@gesm.fr',
            'role': 'hr', 'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
        })
        self.assertFalse(User.objects.filter(username='fake_hr').exists())

    def test_cannot_register_as_hoa(self):
        """HOA role blocked from public registration"""
        self.client.post(reverse('register'), {
            'username': 'fake_hoa', 'email': 'hoa@gesm.fr',
            'role': 'head_of_admin', 'password1': 'TestPass1234!',
            'password2': 'TestPass1234!',
        })
        self.assertFalse(User.objects.filter(username='fake_hoa').exists())

    def test_hod_register_becomes_dept_head(self):
        """HOD who registers becomes head of their department automatically"""
        self.client.post(reverse('register'), {
            'username': 'hod01', 'first_name': 'Jean',
            'last_name': 'Martin', 'email': 'hod@gesm.fr',
            'role': 'head_of_department', 'department': self.dept.id,
            'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
        })
        hod = User.objects.get(username='hod01')
        self.dept.refresh_from_db()
        self.assertEqual(self.dept.head, hod)

    def test_hod_register_assigns_superior_to_existing_teachers(self):
        """HOD who registers becomes superior of existing teachers in dept"""
        teacher = User.objects.create_user(
            username='teacher01', email='t@gesm.fr', password='TestPass1234!',
            role='teacher', department=self.dept,
            is_active=True, is_approved=True, is_email_verified=True,
        )
        self.client.post(reverse('register'), {
            'username': 'hod01', 'first_name': 'Jean',
            'last_name': 'Martin', 'email': 'hod@gesm.fr',
            'role': 'head_of_department', 'department': self.dept.id,
            'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
        })
        hod = User.objects.get(username='hod01')
        teacher.refresh_from_db()
        self.assertEqual(teacher.superior, hod)

    def test_teacher_register_assigned_to_dept_hod(self):
        """Teacher who registers gets dept HOD as superior automatically"""
        hod = User.objects.create_user(
            username='hod01', email='hod@gesm.fr', password='TestPass1234!',
            role='head_of_department', department=self.dept,
            is_active=True, is_approved=True, is_email_verified=True,
        )
        self.dept.head = hod
        self.dept.save()
        self.client.post(reverse('register'), {
            'username': 'teacher01', 'first_name': 'Marine',
            'last_name': 'Dubois', 'email': 'marine@gesm.fr',
            'role': 'teacher', 'department': self.dept.id,
            'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
        })
        teacher = User.objects.get(username='teacher01')
        self.assertEqual(teacher.superior, hod)

    def test_email_verification_token_created(self):
        """Registration creates email verification token"""
        self.client.post(reverse('register'), {
            'username': 'teacher02', 'first_name': 'Paris',
            'last_name': 'Geller', 'email': 'paris@gesm.fr',
            'role': 'teacher', 'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
        })
        user = User.objects.get(username='teacher02')
        self.assertIsNotNone(user.email_verification_token)

    def test_email_verification_activates_flag(self):
        """Clicking verification link sets is_email_verified to True"""
        self.client.post(reverse('register'), {
            'username': 'teacher03', 'first_name': 'Lane',
            'last_name': 'Kim', 'email': 'lane@gesm.fr',
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
            'last_name': 'Gerard', 'email': 'michel@gesm.fr',
            'role': 'teacher', 'password1': 'TestPass1234!', 'password2': 'TestPass1234!',
        })
        response = self.client.post(reverse('login'), {
            'username': 'teacher04', 'password': 'TestPass1234!',
        })
        self.assertNotEqual(response.status_code, 302)


class LoginTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.active_user = User.objects.create_user(
            username='active', email='active@gesm.fr', password='TestPass1234!',
            role='teacher', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.inactive_user = User.objects.create_user(
            username='inactive', email='inactive@gesm.fr', password='TestPass1234!',
            role='teacher', is_active=False,
        )

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

    def test_already_logged_in_redirects_to_dashboard(self):
        self.client.login(username='active', password='TestPass1234!')
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 302)

    def test_password_reset_page_accessible(self):
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)

    def test_logout_redirects_to_login(self):
        self.client.login(username='active', password='TestPass1234!')
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('login'))


class HRApprovalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.hr = User.objects.create_user(
            username='hr01', email='hr@gesm.fr', password='TestPass1234!',
            role='hr', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.pending_employee = User.objects.create_user(
            username='pending_emp', email='pending@gesm.fr', password='TestPass1234!',
            role='employee', is_active=False, is_approved=False, is_email_verified=True,
        )
        self.pending_teacher = User.objects.create_user(
            username='pending_teacher', email='pt@gesm.fr', password='TestPass1234!',
            role='teacher', is_active=False, is_approved=False, is_email_verified=True,
        )
        self.pending_hod = User.objects.create_user(
            username='pending_hod', email='phod@gesm.fr', password='TestPass1234!',
            role='head_of_department', is_active=False, is_approved=False, is_email_verified=True,
        )
        self.client.login(username='hr01', password='TestPass1234!')

    def test_hr_can_approve_employee(self):
        self.client.get(reverse('approve_user', args=[self.pending_employee.id]))
        self.pending_employee.refresh_from_db()
        self.assertTrue(self.pending_employee.is_active)
        self.assertTrue(self.pending_employee.is_approved)

    def test_employee_gets_6_balances_on_approval(self):
        self.client.get(reverse('approve_user', args=[self.pending_employee.id]))
        balances = LeaveBalance.objects.filter(user=self.pending_employee)
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
        """Teacher gets ONE balance of 30 days — not 6 categories"""
        self.client.get(reverse('approve_user', args=[self.pending_teacher.id]))
        balances = LeaveBalance.objects.filter(user=self.pending_teacher)
        self.assertEqual(balances.count(), 1)
        self.assertEqual(balances.first().leave_type, 'vacation_leave')
        self.assertEqual(balances.first().total_days, 30)

    def test_hod_gets_single_30day_balance(self):
        """HOD gets ONE balance of 30 days"""
        self.client.get(reverse('approve_user', args=[self.pending_hod.id]))
        balances = LeaveBalance.objects.filter(user=self.pending_hod)
        self.assertEqual(balances.count(), 1)
        self.assertEqual(balances.first().total_days, 30)

    def test_hr_can_reject_user(self):
        user_id = self.pending_employee.id
        self.client.get(reverse('reject_user', args=[user_id]))
        self.assertFalse(User.objects.filter(id=user_id).exists())

    def test_non_hr_cannot_approve(self):
        teacher = User.objects.create_user(
            username='t_nohr', email='t@gesm.fr', password='TestPass1234!',
            role='teacher', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.client.login(username='t_nohr', password='TestPass1234!')
        response = self.client.get(reverse('approve_user', args=[self.pending_employee.id]))
        self.assertEqual(response.status_code, 302)
        self.pending_employee.refresh_from_db()
        self.assertFalse(self.pending_employee.is_active)

    def test_unauthenticated_cannot_approve(self):
        """Unauthenticated user cannot access approve URL"""
        self.client.logout()
        response = self.client.get(reverse('approve_user', args=[self.pending_employee.id]))
        self.assertEqual(response.status_code, 302)


class HRCreateAdminTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.hr = User.objects.create_user(
            username='hr01', email='hr@gesm.fr', password='TestPass1234!',
            role='hr', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.client.login(username='hr01', password='TestPass1234!')

    def test_hr_can_create_hoa(self):
        self.client.post(reverse('create_admin_user'), {
            'username': 'hoa01', 'first_name': 'Francois',
            'last_name': 'Mercier', 'email': 'hoa@gesm.fr',
            'role': 'head_of_admin', 'password': 'TestPass1234!',
        })
        user = User.objects.get(username='hoa01')
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_approved)
        self.assertEqual(user.role, 'head_of_admin')

    def test_hr_can_create_another_hr(self):
        self.client.post(reverse('create_admin_user'), {
            'username': 'hr02', 'first_name': 'Sookie',
            'last_name': 'James', 'email': 'sookie@gesm.fr',
            'role': 'hr', 'password': 'TestPass1234!',
        })
        self.assertTrue(User.objects.filter(username='hr02', role='hr').exists())

    def test_non_hr_cannot_access_create_admin(self):
        teacher = User.objects.create_user(
            username='t01', email='t@gesm.fr', password='TestPass1234!',
            role='teacher', is_active=True,
        )
        self.client.login(username='t01', password='TestPass1234!')
        response = self.client.get(reverse('create_admin_user'))
        self.assertEqual(response.status_code, 302)

    def test_scheduling_team_cannot_access_create_admin(self):
        sched = User.objects.create_user(
            username='sched01', email='s@gesm.fr', password='TestPass1234!',
            role='scheduling_team', is_active=True,
        )
        self.client.login(username='sched01', password='TestPass1234!')
        response = self.client.get(reverse('create_admin_user'))
        self.assertEqual(response.status_code, 302)


class DepartmentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.hr = User.objects.create_user(
            username='hr01', email='hr@gesm.fr', password='TestPass1234!',
            role='hr', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.dept = Department.objects.create(name='Mathematics')
        self.client.login(username='hr01', password='TestPass1234!')

    def test_hr_can_create_department(self):
        self.client.post(reverse('department_create'), {'name': 'Sciences'})
        self.assertTrue(Department.objects.filter(name='Sciences').exists())

    def test_hr_can_delete_empty_department(self):
        dept_id = self.dept.id
        self.client.post(reverse('department_delete', args=[dept_id]))
        self.assertFalse(Department.objects.filter(id=dept_id).exists())

    def test_department_delete_warns_if_hod_assigned(self):
        """Deleting dept with HOD triggers warning message"""
        User.objects.create_user(
            username='hod01', email='hod@gesm.fr', password='TestPass1234!',
            role='head_of_department', department=self.dept, is_active=True,
        )
        response = self.client.post(
            reverse('department_delete', args=[self.dept.id]),
            follow=True
        )
        messages = list(response.context['messages'])
        self.assertTrue(any('Warning' in str(m) or 'HOD' in str(m) for m in messages))

    def test_department_deleted_despite_warning(self):
        """Department is still deleted even with HOD"""
        User.objects.create_user(
            username='hod01', email='hod@gesm.fr', password='TestPass1234!',
            role='head_of_department', department=self.dept, is_active=True,
        )
        dept_id = self.dept.id
        self.client.post(reverse('department_delete', args=[dept_id]))
        self.assertFalse(Department.objects.filter(id=dept_id).exists())

    def test_hod_has_no_dept_after_dept_deleted(self):
        """HOD has department=None after their dept is deleted"""
        hod = User.objects.create_user(
            username='hod01', email='hod@gesm.fr', password='TestPass1234!',
            role='head_of_department', department=self.dept, is_active=True,
        )
        self.client.post(reverse('department_delete', args=[self.dept.id]))
        hod.refresh_from_db()
        self.assertIsNone(hod.department)

    def test_assigning_hod_updates_teacher_superiors(self):
        teacher = User.objects.create_user(
            username='teacher01', email='t@gesm.fr', password='TestPass1234!',
            role='teacher', department=self.dept, is_active=True,
        )
        hod = User.objects.create_user(
            username='hod01', email='hod@gesm.fr', password='TestPass1234!',
            role='head_of_department', is_active=True,
        )
        self.client.post(reverse('department_list'), {
            'dept_id': self.dept.id, 'hod_id': hod.id,
        })
        teacher.refresh_from_db()
        self.assertEqual(teacher.superior, hod)

    def test_non_hr_cannot_create_department(self):
        teacher = User.objects.create_user(
            username='t01', email='t@gesm.fr', password='TestPass1234!',
            role='teacher', is_active=True,
        )
        self.client.login(username='t01', password='TestPass1234!')
        self.client.post(reverse('department_create'), {'name': 'Fake'})
        self.assertFalse(Department.objects.filter(name='Fake').exists())