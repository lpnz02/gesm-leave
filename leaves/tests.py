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
            username='hod01', email='hod@gesm.org', password='TestPass1234!',
            role='head_of_department', department=self.dept,
            is_active=True, is_approved=True, is_email_verified=True,
        )
        self.dept.head = self.hod
        self.dept.save()
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
        self.teacher = User.objects.create_user(
            username='teacher01', email='teacher@gesm.org', password='TestPass1234!',
            role='teacher', department=self.dept, superior=self.hod,
            is_active=True, is_approved=True, is_email_verified=True,
        )
        self.admin = User.objects.create_user(
            username='admin01', email='admin@gesm.org', password='TestPass1234!',
            role='admin', is_active=True, is_approved=True, is_email_verified=True,
        )

    def test_teacher_leave_pending_hod(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Vacation',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
            'half_day': 'none',
        })
        leave = Leave.objects.filter(user=self.teacher).first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.status, 'pending_hod')

    def test_admin_leave_pending_hoa(self):
        """Admin leave goes to pending_hoa (not employee anymore)"""
        self.client.login(username='admin01', password='TestPass1234!')
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'sick_leave', 'reason_for_leave': 'Sick',
            'start_leave': date.today() + timedelta(days=5),
            'end_leave': date.today() + timedelta(days=7),
            'half_day': 'none',
        })
        leave = Leave.objects.filter(user=self.admin).first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.status, 'pending_hoa')

    def test_hod_leave_pending_hos(self):
        self.client.login(username='hod01', password='TestPass1234!')
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Vacation',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
            'half_day': 'none',
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
            'half_day': 'none',
        })
        leave = Leave.objects.filter(user=self.hr).first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.status, 'pending_hoa')

    def test_half_day_morning_saved(self):
        """Half day morning is saved correctly"""
        self.client.login(username='teacher01', password='TestPass1234!')
        today = date.today() + timedelta(days=10)
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Half day',
            'start_leave': today, 'end_leave': today,
            'half_day': 'morning',
        })
        leave = Leave.objects.filter(user=self.teacher).first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.half_day, 'morning')

    def test_half_day_afternoon_saved(self):
        """Half day afternoon is saved correctly"""
        self.client.login(username='teacher01', password='TestPass1234!')
        today = date.today() + timedelta(days=10)
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Half day',
            'start_leave': today, 'end_leave': today,
            'half_day': 'afternoon',
        })
        leave = Leave.objects.filter(user=self.teacher).first()
        self.assertEqual(leave.half_day, 'afternoon')

    def test_half_day_working_days_is_05(self):
        """Half day on a single day = 0.5 working days"""
        monday = date(2026, 5, 4)
        leave = Leave.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            reason_for_leave='Test', start_leave=monday,
            end_leave=monday, status='approved', half_day='morning',
        )
        self.assertEqual(leave.working_days(), 0.5)

    def test_full_day_working_days(self):
        """Full day leave = 1 working day"""
        monday = date(2026, 5, 4)
        leave = Leave.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            reason_for_leave='Test', start_leave=monday,
            end_leave=monday, status='approved', half_day='none',
        )
        self.assertEqual(leave.working_days(), 1)

    def test_working_days_excludes_weekends(self):
        monday = date(2026, 5, 4)
        friday = date(2026, 5, 8)
        leave = Leave.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            reason_for_leave='Test', start_leave=monday,
            end_leave=friday, status='approved', half_day='none',
        )
        self.assertEqual(leave.working_days(), 5)

    def test_full_week_is_5_working_days(self):
        monday = date(2026, 5, 4)
        sunday = date(2026, 5, 10)
        leave = Leave.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            reason_for_leave='Test', start_leave=monday,
            end_leave=sunday, status='approved', half_day='none',
        )
        self.assertEqual(leave.working_days(), 5)

    def test_is_unpaid_default_false(self):
        """Leave is paid by default"""
        self.client.login(username='teacher01', password='TestPass1234!')
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Test',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
            'half_day': 'none',
        })
        leave = Leave.objects.filter(user=self.teacher).first()
        self.assertFalse(leave.is_unpaid)

    def test_unauthenticated_cannot_submit_leave(self):
        response = self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Test',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
            'half_day': 'none',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_scheduling_team_cannot_submit_leave(self):
        sched = User.objects.create_user(
            username='sched01', email='sched@gesm.org', password='TestPass1234!',
            role='scheduling_team', is_active=True,
        )
        self.client.login(username='sched01', password='TestPass1234!')
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Test',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
            'half_day': 'none',
        })
        self.assertEqual(Leave.objects.filter(user=sched).count(), 0)

    def test_calendar_access_cannot_submit_leave(self):
        """Calendar access role cannot submit leaves"""
        cal = User.objects.create_user(
            username='cal01', email='cal@gesm.org', password='TestPass1234!',
            role='calendar_access', is_active=True,
        )
        self.client.login(username='cal01', password='TestPass1234!')
        self.client.post(reverse('submit_leave'), {
            'leave_type': 'vacation_leave', 'reason_for_leave': 'Test',
            'start_leave': date.today() + timedelta(days=10),
            'end_leave': date.today() + timedelta(days=15),
            'half_day': 'none',
        })
        self.assertEqual(Leave.objects.filter(user=cal).count(), 0)

    def test_leave_deleted_when_user_deleted_cascade(self):
        """CASCADE: deleting user deletes their leaves"""
        leave = Leave.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            reason_for_leave='Test',
            start_leave=date.today() + timedelta(days=10),
            end_leave=date.today() + timedelta(days=15),
            status='pending_hod', half_day='none',
        )
        leave_id = leave.id
        self.teacher.delete()
        self.assertFalse(Leave.objects.filter(id=leave_id).exists())


class LeaveApprovalTests(TestCase):
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
        self.teacher = User.objects.create_user(
            username='teacher01', email='teacher@gesm.org', password='TestPass1234!',
            role='teacher', department=self.dept, superior=self.hod,
            is_active=True, is_approved=True, is_email_verified=True,
        )
        self.admin = User.objects.create_user(
            username='admin01', email='admin@gesm.org', password='TestPass1234!',
            role='admin', is_active=True, is_approved=True, is_email_verified=True,
        )
        LeaveBalance.objects.create(
            user=self.admin, leave_type='sick_leave',
            total_days=15, days_used=0, days_remaining=15, carried_over=0,
        )
        LeaveBalance.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            total_days=30, days_used=0, days_remaining=30, carried_over=0,
        )
        self.teacher_leave = Leave.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            reason_for_leave='Vacation',
            start_leave=date.today() + timedelta(days=10),
            end_leave=date.today() + timedelta(days=14),
            status='pending_hod', half_day='none',
        )
        self.admin_leave = Leave.objects.create(
            user=self.admin, leave_type='sick_leave',
            reason_for_leave='Sick',
            start_leave=date.today() + timedelta(days=5),
            end_leave=date.today() + timedelta(days=7),
            status='pending_hoa', half_day='none',
        )
        self.hr_leave = Leave.objects.create(
            user=self.hr, leave_type='vacation_leave',
            reason_for_leave='Vacation',
            start_leave=date.today() + timedelta(days=10),
            end_leave=date.today() + timedelta(days=15),
            status='pending_hoa', half_day='none',
        )
        self.hod_leave = Leave.objects.create(
            user=self.hod, leave_type='vacation_leave',
            reason_for_leave='Vacation',
            start_leave=date.today() + timedelta(days=10),
            end_leave=date.today() + timedelta(days=15),
            status='pending_hos', half_day='none',
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

    def test_hos_can_mark_leave_as_unpaid(self):
        """HOS can mark teacher leave as unpaid when approving"""
        self.teacher_leave.status = 'pending_hos'
        self.teacher_leave.save()
        self.client.login(username='hos01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.teacher_leave.id]), {
            'is_unpaid': '1',
        })
        self.teacher_leave.refresh_from_db()
        self.assertEqual(self.teacher_leave.status, 'approved')
        self.assertTrue(self.teacher_leave.is_unpaid)

    def test_hos_approve_paid_by_default(self):
        """Leave is paid by default when HOS approves without checking unpaid"""
        self.teacher_leave.status = 'pending_hos'
        self.teacher_leave.save()
        self.client.login(username='hos01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.teacher_leave.id]))
        self.teacher_leave.refresh_from_db()
        self.assertFalse(self.teacher_leave.is_unpaid)

    def test_hos_approve_hod_leave(self):
        """HOS can approve HOD leave"""
        self.client.login(username='hos01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.hod_leave.id]))
        self.hod_leave.refresh_from_db()
        self.assertEqual(self.hod_leave.status, 'approved')

    def test_hoa_approve_admin_leave(self):
        self.client.login(username='hoa01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.admin_leave.id]))
        self.admin_leave.refresh_from_db()
        self.assertEqual(self.admin_leave.status, 'approved')

    def test_hoa_can_mark_leave_as_unpaid(self):
        """HOA can mark admin leave as unpaid when approving"""
        self.client.login(username='hoa01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.admin_leave.id]), {
            'is_unpaid': '1',
        })
        self.admin_leave.refresh_from_db()
        self.assertEqual(self.admin_leave.status, 'approved')
        self.assertTrue(self.admin_leave.is_unpaid)

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

    def test_hoa_reject_admin_leave(self):
        self.client.login(username='hoa01', password='TestPass1234!')
        self.client.post(reverse('reject_leave', args=[self.admin_leave.id]))
        self.admin_leave.refresh_from_db()
        self.assertEqual(self.admin_leave.status, 'rejected')

    def test_hos_cannot_approve_pending_hod_leave(self):
        """HOS cannot approve leave still at pending_hod"""
        self.client.login(username='hos01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.teacher_leave.id]))
        self.teacher_leave.refresh_from_db()
        self.assertEqual(self.teacher_leave.status, 'pending_hod')

    def test_hod_cannot_approve_admin_leave(self):
        self.client.login(username='hod01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.admin_leave.id]))
        self.admin_leave.refresh_from_db()
        self.assertEqual(self.admin_leave.status, 'pending_hoa')

    def test_teacher_cannot_approve_leave(self):
        other_teacher = User.objects.create_user(
            username='teacher02', email='t2@gesm.org', password='TestPass1234!',
            role='teacher', is_active=True,
        )
        self.client.login(username='teacher02', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.teacher_leave.id]))
        self.teacher_leave.refresh_from_db()
        self.assertEqual(self.teacher_leave.status, 'pending_hod')

    def test_admin_balance_updated_after_approval(self):
        """Admin balance days_used increases after HOA approval"""
        self.client.login(username='hoa01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[self.admin_leave.id]))
        balance = LeaveBalance.objects.get(user=self.admin, leave_type='sick_leave')
        self.assertGreater(balance.days_used, 0)
        self.assertLess(balance.days_remaining, 15)

    def test_half_day_balance_deducted_05(self):
        """Half day approval deducts 0.5 from balance"""
        today = date.today() + timedelta(days=10)
        half_day_leave = Leave.objects.create(
            user=self.admin, leave_type='sick_leave',
            reason_for_leave='Half day sick',
            start_leave=today, end_leave=today,
            status='pending_hoa', half_day='morning',
        )
        self.client.login(username='hoa01', password='TestPass1234!')
        self.client.post(reverse('approve_leave', args=[half_day_leave.id]))
        balance = LeaveBalance.objects.get(user=self.admin, leave_type='sick_leave')
        self.assertEqual(float(balance.days_used), 0.5)
        self.assertEqual(float(balance.days_remaining), 14.5)


class LeaveBalanceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.hr = User.objects.create_user(
            username='hr01', email='hr@gesm.org', password='TestPass1234!',
            role='hr', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.admin = User.objects.create_user(
            username='admin01', email='admin@gesm.org', password='TestPass1234!',
            role='admin', is_active=True, is_approved=True, is_email_verified=True,
        )
        self.teacher = User.objects.create_user(
            username='teacher01', email='teacher@gesm.org', password='TestPass1234!',
            role='teacher', is_active=True, is_approved=True, is_email_verified=True,
        )
        LeaveBalance.objects.create(
            user=self.admin, leave_type='vacation_leave',
            total_days=15, days_used=0, days_remaining=15, carried_over=0,
        )
        LeaveBalance.objects.create(
            user=self.admin, leave_type='sick_leave',
            total_days=15, days_used=5, days_remaining=10, carried_over=0,
        )
        LeaveBalance.objects.create(
            user=self.teacher, leave_type='vacation_leave',
            total_days=30, days_used=0, days_remaining=30, carried_over=0,
        )

    def test_hr_can_adjust_admin_balance(self):
        """HR can adjust admin balance by category"""
        self.client.login(username='hr01', password='TestPass1234!')
        self.client.post(reverse('adjust_balance'), {
            'user_id': self.admin.id,
            'balance_type': 'admin',
            'leave_type': 'vacation_leave',
            'days_remaining': 20,
        })
        balance = LeaveBalance.objects.get(user=self.admin, leave_type='vacation_leave')
        self.assertEqual(float(balance.days_remaining), 20.0)

    def test_hr_can_adjust_teacher_total(self):
        """HR can adjust teacher total days"""
        self.client.login(username='hr01', password='TestPass1234!')
        self.client.post(reverse('adjust_balance'), {
            'user_id': self.teacher.id,
            'balance_type': 'teacher',
            'total_days': 25,
        })
        balance = LeaveBalance.objects.get(user=self.teacher, leave_type='vacation_leave')
        self.assertEqual(float(balance.days_remaining), 25.0)

    def test_non_hr_cannot_adjust_balance(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        self.client.post(reverse('adjust_balance'), {
            'user_id': self.admin.id,
            'balance_type': 'admin',
            'leave_type': 'vacation_leave',
            'days_remaining': 5,
        })
        balance = LeaveBalance.objects.get(user=self.admin, leave_type='vacation_leave')
        self.assertEqual(float(balance.days_remaining), 15.0)

    def test_reset_carries_over_vacation_only_for_admin(self):
        """Only vacation_leave is carried over for admins at reset"""
        self.client.login(username='hr01', password='TestPass1234!')
        self.client.post(reverse('reset_balances'))
        vacation = LeaveBalance.objects.get(user=self.admin, leave_type='vacation_leave')
        self.assertEqual(vacation.carried_over, 15)
        self.assertEqual(vacation.days_used, 0)
        sick = LeaveBalance.objects.get(user=self.admin, leave_type='sick_leave')
        self.assertEqual(sick.carried_over, 0)

    def test_reset_does_not_carry_over_for_teachers(self):
        """Teachers have no carry over at reset"""
        self.client.login(username='hr01', password='TestPass1234!')
        self.client.post(reverse('reset_balances'))
        balance = LeaveBalance.objects.get(user=self.teacher, leave_type='vacation_leave')
        self.assertEqual(balance.total_days, 30)
        self.assertEqual(balance.carried_over, 0)
        self.assertEqual(balance.days_used, 0)

    def test_reset_clears_all_leaves(self):
        """Reset deletes all leave requests"""
        Leave.objects.create(
            user=self.admin, leave_type='vacation_leave',
            reason_for_leave='Test', start_leave=date.today(),
            end_leave=date.today() + timedelta(days=5),
            status='approved', half_day='none',
        )
        self.client.login(username='hr01', password='TestPass1234!')
        self.client.post(reverse('reset_balances'))
        self.assertEqual(Leave.objects.count(), 0)

    def test_non_hr_cannot_reset_balances(self):
        self.client.login(username='teacher01', password='TestPass1234!')
        self.client.post(reverse('reset_balances'))
        balance = LeaveBalance.objects.get(user=self.admin, leave_type='vacation_leave')
        self.assertEqual(float(balance.total_days), 15.0)

    def test_delete_approved_leave_restores_teacher_balance(self):
            """Deleting an approved leave restores the teacher's days"""
            balance = LeaveBalance.objects.get(user=self.teacher, leave_type='vacation_leave')
            balance.days_used = 5
            balance.days_remaining = 25
            balance.save()

            # leave de 5 jours ouvrés (lun-ven)
            leave = Leave.objects.create(
                user=self.teacher, leave_type='vacation_leave',
                reason_for_leave='Test',
                start_leave=date(2026, 5, 4),  # lundi
                end_leave=date(2026, 5, 8),    # vendredi
                status='approved', half_day='none',
            )
            self.client.login(username='hr01', password='TestPass1234!')
            self.client.post(reverse('delete_leave', args=[leave.id]))
            balance.refresh_from_db()
            self.assertEqual(float(balance.days_used), 0.0)
            self.assertEqual(float(balance.days_remaining), 30.0)

    def test_delete_approved_leave_restores_admin_balance(self):
        """Deleting an approved admin leave restores their category balance"""
        balance = LeaveBalance.objects.get(user=self.admin, leave_type='vacation_leave')
        balance.days_used = 3
        balance.days_remaining = 12
        balance.save()
        leave = Leave.objects.create(
            user=self.admin, leave_type='vacation_leave',
            reason_for_leave='Test',
            start_leave=date.today() - timedelta(days=5),
            end_leave=date.today() - timedelta(days=3),
            status='approved', half_day='none',
        )
        self.client.login(username='hr01', password='TestPass1234!')
        self.client.post(reverse('delete_leave', args=[leave.id]))
        balance.refresh_from_db()
        self.assertGreater(float(balance.days_remaining), 12.0)
