# leaves/tests.py
from django.test import TestCase, Client
from django.urls import reverse
from datetime import date, timedelta
from accounts.models import User, Department
from leaves.models import Leave, LeaveBalance


class LeaveSubmissionTests(TestCase):
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
        self.teacher = User.objects.create_user(
            username='teacher01', email='teacher@gesm.fr', password='TestPass1234!',
            role='teacher', department=self.dept, superior=self.hod,
            is_active=True, is_approved=True, is_email_verified=True,
        )
        self.employee = User.objects.create_user(
            username='emp01', email='emp@gesm.fr', password='TestPass1234!',
            role='employee', is_active=True, is_approved=True, is_email_verified=True,
        )

    def test_teacher_leave_pending_hod(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Vacation',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
        })
        leave = Leave.objects.filter(user=self.teacher).first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.status, 'pending_hod')

    def test_employee_leave_pending_hoa(self):
        self.client.login(username='emp01', password='TestPass1234!')
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'sick_leave', 'reason_for_leave': 'Sick',
            'start_leave': date.today() + timedelta(days=5),
            'end_leave': date.today() + timedelta(days=7),
        })
        leave = Leave.objects.filter(user=self.employee).first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.status, 'pending_hoa')

    def test_hod_leave_pending_hos(self):
        self.client.login(username='hod01', password='TestPass1234!')
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Vacation',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
        })
        leave = Leave.objects.filter(user=self.hod).first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.status, 'pending_hos')

    def test_hr_leave_pending_hoa(self):
        self.client.login(username='hr01', password='TestPass1234!')
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Vacation',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
        })
        leave = Leave.objects.filter(user=self.hr).first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.status, 'pending_hoa')

    def test_leave_belongs_to_submitting_user(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Test',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
        })
        leaves = Leave.objects.filter(user=self.teacher)
        self.assertEqual(leaves.count(), 1)
        self.assertEqual(leaves.first().user, self.teacher)

    def test_unauthenticated_cannot_submit_leave(self):
        response = self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Test',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_scheduling_team_cannot_submit_leave(self):
        sched = User.objects.create_user(
            username='sched01', email='sched@gesm.fr', password='TestPass1234!',
            role='scheduling_team', is_active=True,
        )
        self.client.login(username='sched01', password='TestPass1234!')
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Test',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
        })
        self.assertEqual(Leave.objects.filter(user=sched).count(), 0)

    def test_working_days_excludes_weekends(self):
        monday = date(2026, 5, 4)
        friday = date(2026, 5, 8)
        leave = Leave.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            reason_for_leave='Test', start_leave=monday,
            end_leave=friday, status='approved',
        )
        self.assertEqual(leave.working_days(), 5)

    def test_full_week_is_5_working_days(self):
        monday = date(2026, 5, 4)
        sunday = date(2026, 5, 10)
        leave = Leave.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            reason_for_leave='Test', start_leave=monday,
            end_leave=sunday, status='approved',
        )
        self.assertEqual(leave.working_days(), 5)

    def test_single_day_leave(self):
        monday = date(2026, 5, 4)
        leave = Leave.objects.create(
            user=self.teacher, leave_type='sick_leave',
            reason_for_leave='Test', start_leave=monday,
            end_leave=monday, status='approved',
        )
        self.assertEqual(leave.working_days(), 1)

    def test_leave_deleted_when_user_deleted_cascade(self):
        """CASCADE: deleting user deletes their leaves"""
        leave = Leave.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            reason_for_leave='Test',
            start_leave=date.today() + timedelta(days=10),
            end_leave=date.today() + timedelta(days=15),
            status='pending_hod',
        )
        leave_id = leave.id
        self.teacher.delete()
        self.assertFalse(Leave.objects.filter(id=leave_id).exists())


class LeaveApprovalTests(TestCase):
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
        self.teacher = User.objects.create_user(
            username='teacher01', email='teacher@gesm.fr', password='TestPass1234!',
            role='teacher', department=self.dept, superior=self.hod,
            is_active=True, is_approved=True, is_email_verified=True,
        )
        self.employee = User.objects.create_user(
            username='emp01', email='emp@gesm.fr', password='TestPass1234!',
            role='employee', is_active=True, is_approved=True, is_email_verified=True,
        )
        LeaveBalance.objects.create(
            user=self.employee, leave_type='sick_leave',
            total_days=15, days_used=0, days_remaining=15, carried_over=0,
        )
        self.teacher_leave = Leave.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            reason_for_leave='Vacation',
            start_leave=date.today() + timedelta(days=10),
            end_leave=date.today() + timedelta(days=14),
            status='pending_hod',
        )
        self.employee_leave = Leave.objects.create(
            user=self.employee, leave_type='sick_leave',
            reason_for_leave='Sick',
            start_leave=date.today() + timedelta(days=5),
            end_leave=date.today() + timedelta(days=7),
            status='pending_hoa',
        )
        self.hr_leave = Leave.objects.create(
            user=self.hr, leave_type='vacation_leave',
            reason_for_leave='Vacation',
            start_leave=date.today() + timedelta(days=10),
            end_leave=date.today() + timedelta(days=15),
            status='pending_hoa',
        )
        self.hod_leave = Leave.objects.create(
            user=self.hod, leave_type='vacation_leave',
            reason_for_leave='Vacation',
            start_leave=date.today() + timedelta(days=10),
            end_leave=date.today() + timedelta(days=15),
            status='pending_hos',
        )

    def test_hod_approve_changes_to_pending_hos(self):
        self.client.login(username='hod01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.teacher_leave.id]))
        self.teacher_leave.refresh_from_db()
        self.assertEqual(self.teacher_leave.status, 'pending_hos')

    def test_hos_approve_finalizes_teacher_leave(self):
        self.teacher_leave.status = 'pending_hos'
        self.teacher_leave.save()
        self.client.login(username='hos01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.teacher_leave.id]))
        self.teacher_leave.refresh_from_db()
        self.assertEqual(self.teacher_leave.status, 'approved')

    def test_hos_approve_hod_leave(self):
        """HOS can approve HOD leave"""
        self.client.login(username='hos01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.hod_leave.id]))
        self.hod_leave.refresh_from_db()
        self.assertEqual(self.hod_leave.status, 'approved')

    def test_hoa_approve_employee_leave(self):
        self.client.login(username='hoa01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.employee_leave.id]))
        self.employee_leave.refresh_from_db()
        self.assertEqual(self.employee_leave.status, 'approved')

    def test_hoa_approve_hr_leave(self):
        """HOA can approve HR leave"""
        self.client.login(username='hoa01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.hr_leave.id]))
        self.hr_leave.refresh_from_db()
        self.assertEqual(self.hr_leave.status, 'approved')

    def test_hod_reject_sets_rejected(self):
        self.client.login(username='hod01', password='TestPass1234!')
        self.client.post(reverse('reject_leave', args=[self.teacher_leave.id]))
        self.teacher_leave.refresh_from_db()
        self.assertEqual(self.teacher_leave.status, 'rejected')

    def test_hoa_reject_employee_leave(self):
        self.client.login(username='hoa01', password='TestPass1234!')
        self.client.post(reverse('reject_leave', args=[self.employee_leave.id]))
        self.employee_leave.refresh_from_db()
        self.assertEqual(self.employee_leave.status, 'rejected')

    def test_hos_cannot_approve_pending_hod_leave(self):
        """HOS cannot approve leave still at pending_hod"""
        self.client.login(username='hos01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.teacher_leave.id]))
        self.teacher_leave.refresh_from_db()
        self.assertEqual(self.teacher_leave.status, 'pending_hod')

    def test_hod_cannot_approve_employee_leave(self):
        self.client.login(username='hod01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.employee_leave.id]))
        self.employee_leave.refresh_from_db()
        self.assertEqual(self.employee_leave.status, 'pending_hoa')

    def test_teacher_cannot_approve_leave(self):
        other_teacher = User.objects.create_user(
            username='teacher02', email='t2@gesm.fr', password='TestPass1234!',
            role='teacher', is_active=True,
        )
        self.client.login(username='teacher02', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.teacher_leave.id]))
        self.teacher_leave.refresh_from_db()
        self.assertEqual(self.teacher_leave.status, 'pending_hod')

    def test_employee_balance_updated_after_approval(self):
        self.client.login(username='hoa01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.employee_leave.id]))
        balance = LeaveBalance.objects.get(user=self.employee, leave_type='sick_leave')
        self.assertGreater(balance.days_used, 0)
        self.assertLess(balance.days_remaining, 15)


class LeaveBalanceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.hr = User.objects.create_user(
            username='hr01', email='hr@gesm.fr', password='TestPass1234!',
            role='hr', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.employee = User.objects.create_user(
            username='emp01', email='emp@gesm.fr', password='TestPass1234!',
            role='employee', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.teacher = User.objects.create_user(
            username='teacher01', email='teacher@gesm.fr', password='TestPass1234!',
            role='teacher', is_active=True, is_approved=True, is_email_verified=True,
        )
        LeaveBalance.objects.create(
            user=self.employee, leave_type='vacation_leave',
            total_days=15, days_used=0, days_remaining=15, carried_over=0,
        )
        LeaveBalance.objects.create(
            user=self.employee, leave_type='sick_leave',
            total_days=15, days_used=5, days_remaining=10, carried_over=0,
        )
        LeaveBalance.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            total_days=30, days_used=0, days_remaining=30, carried_over=0,
        )

    def test_hr_can_adjust_balance(self):
        self.client.login(username='hr01', password='TestPass1234!')
        self.client.post(reverse('adjust_balance'), {
            'user_id': self.employee.id,
            'leave_type': 'vacation_leave',
            'days_remaining': 20,
        })
        balance = LeaveBalance.objects.get(user=self.employee, leave_type='vacation_leave')
        self.assertEqual(balance.days_remaining, 20)

    def test_non_hr_cannot_adjust_balance(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        self.client.post(reverse('adjust_balance'), {
            'user_id': self.employee.id,
            'leave_type': 'vacation_leave',
            'days_remaining': 5,
        })
        balance = LeaveBalance.objects.get(user=self.employee, leave_type='vacation_leave')
        self.assertEqual(balance.days_remaining, 15)

    def test_reset_carries_over_unused_days_for_employee(self):
        self.client.login(username='hr01', password='TestPass1234!')
        self.client.post(reverse('reset_balances'))
        balance = LeaveBalance.objects.get(user=self.employee, leave_type='vacation_leave')
        self.assertEqual(balance.total_days, 30)
        self.assertEqual(balance.carried_over, 15)
        self.assertEqual(balance.days_used, 0)

    def test_reset_does_not_carry_over_for_teachers(self):
        self.client.login(username='hr01', password='TestPass1234!')
        self.client.post(reverse('reset_balances'))
        balance = LeaveBalance.objects.get(user=self.teacher, leave_type='vacation_leave')
        self.assertEqual(balance.total_days, 30)
        self.assertEqual(balance.carried_over, 0)
        self.assertEqual(balance.days_used, 0)

    def test_reset_clears_all_leaves(self):
        hoa = User.objects.create_user(
            username='hoa01', email='hoa@gesm.fr', password='TestPass1234!',
            role='head_of_admin', is_active=True,
        )
        Leave.objects.create(
            user=self.employee, leave_type='vacation_leave',
            reason_for_leave='Test', start_leave=date.today(),
            end_leave=date.today() + timedelta(days=5), status='approved',
        )
        self.client.login(username='hr01', password='TestPass1234!')
        self.client.post(reverse('reset_balances'))
        self.assertEqual(Leave.objects.count(), 0)

    def test_carried_over_only_from_current_year(self):
        balance = LeaveBalance.objects.get(user=self.employee, leave_type='vacation_leave')
        balance.carried_over = 5
        balance.days_used = 3
        balance.days_remaining = 12
        balance.save()
        self.client.login(username='hr01', password='TestPass1234!')
        self.client.post(reverse('reset_balances'))
        balance.refresh_from_db()
        self.assertEqual(balance.carried_over, 12)
        self.assertEqual(balance.total_days, 27)

    def test_non_hr_cannot_reset_balances(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        response = self.client.post(reverse('reset_balances'))
        self.assertEqual(response.status_code, 302)
        balance = LeaveBalance.objects.get(user=self.employee, leave_type='vacation_leave')
        self.assertEqual(balance.total_days, 15)