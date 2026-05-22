# leaves/test_leaves.py
from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail
from datetime import date, timedelta
from accounts.models import User, Department
from leaves.models import Leave, LeaveBalance
import io


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


class LeaveSubmissionTests(TestCase):
   def setUp(self):
       self.client = Client()
       self.dept = Department.objects.create(name='Mathematics')
       self.hod = make_user('hod01', 'head_of_department', dept=self.dept)
       self.dept.head = self.hod
       self.dept.save()
       self.hos = make_user('hos01', 'head_of_school')
       self.hoa = make_user('hoa01', 'head_of_admin')
       self.hr = make_user('hr01', 'hr')
       self.teacher = make_user('teacher01', 'teacher', dept=self.dept, superior=self.hod)
       self.admin = make_user('admin01', 'admin')

   def test_teacher_leave_pending_hod(self):
       """Teacher leave goes to pending_hod"""
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
       """Admin leave goes to pending_hoa"""
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
       """HOD leave goes to pending_hos"""
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
       """HR leave goes to pending_hoa"""
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
       self.client.login(username='teacher01', password='TestPass1234!')
       today = date.today() + timedelta(days=10)
       self.client.post(reverse('submit_leave'), {
           'leave_type': 'vacation_leave', 'reason_for_leave': 'Half day',
           'start_leave': today, 'end_leave': today, 'half_day': 'morning',
       })
       leave = Leave.objects.filter(user=self.teacher).first()
       self.assertIsNotNone(leave)
       self.assertEqual(leave.half_day, 'morning')

   def test_half_day_afternoon_saved(self):
       self.client.login(username='teacher01', password='TestPass1234!')
       today = date.today() + timedelta(days=10)
       self.client.post(reverse('submit_leave'), {
           'leave_type': 'vacation_leave', 'reason_for_leave': 'Half day',
           'start_leave': today, 'end_leave': today, 'half_day': 'afternoon',
       })
       leave = Leave.objects.filter(user=self.teacher).first()
       self.assertEqual(leave.half_day, 'afternoon')

   def test_half_day_working_days_is_05(self):
       monday = date(2026, 5, 4)
       leave = Leave.objects.create(
           user=self.teacher, leave_type='vacation_leave',
           reason_for_leave='Test', start_leave=monday,
           end_leave=monday, status='approved', half_day='morning',
       )
       self.assertEqual(leave.working_days(), 0.5)

   def test_full_day_working_days(self):
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
       sched = make_user('sched01', 'scheduling_team')
       self.client.login(username='sched01', password='TestPass1234!')
       self.client.post(reverse('submit_leave'), {
           'leave_type': 'vacation_leave', 'reason_for_leave': 'Test',
           'start_leave': date.today() + timedelta(days=10),
           'end_leave': date.today() + timedelta(days=15),
           'half_day': 'none',
       })
       self.assertEqual(Leave.objects.filter(user=sched).count(), 0)

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

   def test_leave_deleted_when_user_deleted_cascade(self):
       leave = make_leave(self.teacher, status='pending_hod')
       leave_id = leave.id
       self.teacher.delete()
       self.assertFalse(Leave.objects.filter(id=leave_id).exists())

   def test_leave_appears_in_teacher_dashboard_after_submission(self):
       """Submitted leave appears in teacher dashboard"""
       self.client.login(username='teacher01', password='TestPass1234!')
       self.client.post(reverse('submit_leave'), {
           'leave_type': 'vacation_leave', 'reason_for_leave': 'Vacation',
           'start_leave': date.today() + timedelta(days=10),
           'end_leave': date.today() + timedelta(days=15),
           'half_day': 'none',
       })
       response = self.client.get(reverse('dashboard'))
       self.assertEqual(response.status_code, 200)
       self.assertIn('leaves', response.context)
       self.assertEqual(response.context['leaves'].count(), 1)

   def test_approved_leave_appears_in_hoa_dashboard(self):
       """HOA-approved leave appears in admin dashboard"""
       LeaveBalance.objects.create(
           user=self.admin, leave_type='sick_leave',
           total_days=15, days_used=0, days_remaining=15, carried_over=0,
       )
       leave = make_leave(self.admin, status='pending_hoa', leave_type='sick_leave')
       self.client.login(username='hoa01', password='TestPass1234!')
       self.client.post(reverse('approve_leave', args=[leave.id]))
       self.client.login(username='admin01', password='TestPass1234!')
       response = self.client.get(reverse('dashboard'))
       self.assertEqual(response.status_code, 200)
       leaves = response.context['leaves']
       approved = [l for l in leaves if l.status == 'approved']
       self.assertEqual(len(approved), 1)


class LeaveApprovalTests(TestCase):
   def setUp(self):
       self.client = Client()
       self.dept = Department.objects.create(name='Mathematics')
       self.hod = make_user('hod01', 'head_of_department', dept=self.dept)
       self.dept.head = self.hod
       self.dept.save()
       self.hos = make_user('hos01', 'head_of_school')
       self.hoa = make_user('hoa01', 'head_of_admin')
       self.hr = make_user('hr01', 'hr')
       self.teacher = make_user('teacher01', 'teacher', dept=self.dept, superior=self.hod)
       self.admin = make_user('admin01', 'admin')
       LeaveBalance.objects.create(
           user=self.admin, leave_type='sick_leave',
           total_days=15, days_used=0, days_remaining=15, carried_over=0,
       )
       LeaveBalance.objects.create(
           user=self.teacher, leave_type='vacation_leave',
           total_days=30, days_used=0, days_remaining=30, carried_over=0,
       )
       self.teacher_leave = make_leave(self.teacher, status='pending_hod')
       self.admin_leave = make_leave(self.admin, status='pending_hoa', leave_type='sick_leave')
       self.hod_leave = make_leave(self.hod, status='pending_hos')

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
       self.teacher_leave.status = 'pending_hos'
       self.teacher_leave.save()
       self.client.login(username='hos01', password='TestPass1234!')
       self.client.post(reverse('approve_leave', args=[self.teacher_leave.id]), {
           'is_unpaid': '1',
       })
       self.teacher_leave.refresh_from_db()
       self.assertTrue(self.teacher_leave.is_unpaid)

   def test_hos_approve_hod_leave(self):
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
       self.client.login(username='hoa01', password='TestPass1234!')
       self.client.post(reverse('approve_leave', args=[self.admin_leave.id]), {
           'is_unpaid': '1',
       })
       self.admin_leave.refresh_from_db()
       self.assertTrue(self.admin_leave.is_unpaid)

   def test_hod_reject_with_reason(self):
       """HOD can reject with a reason message"""
       self.client.login(username='hod01', password='TestPass1234!')
       self.client.post(reverse('reject_leave', args=[self.teacher_leave.id]), {
           'rejection_reason': 'Not enough staff available',
       })
       self.teacher_leave.refresh_from_db()
       self.assertEqual(self.teacher_leave.status, 'rejected')
       self.assertEqual(self.teacher_leave.rejection_reason, 'Not enough staff available')

   def test_hos_reject_with_reason(self):
       """HOS can reject with a reason message"""
       self.teacher_leave.status = 'pending_hos'
       self.teacher_leave.save()
       self.client.login(username='hos01', password='TestPass1234!')
       self.client.post(reverse('reject_leave', args=[self.teacher_leave.id]), {
           'rejection_reason': 'School event conflict',
       })
       self.teacher_leave.refresh_from_db()
       self.assertEqual(self.teacher_leave.rejection_reason, 'School event conflict')

   def test_hoa_reject_with_reason(self):
       """HOA can reject with a reason message"""
       self.client.login(username='hoa01', password='TestPass1234!')
       self.client.post(reverse('reject_leave', args=[self.admin_leave.id]), {
           'rejection_reason': 'No replacement available',
       })
       self.admin_leave.refresh_from_db()
       self.assertEqual(self.admin_leave.rejection_reason, 'No replacement available')

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
       other_teacher = make_user('teacher02', 'teacher')
       self.client.login(username='teacher02', password='TestPass1234!')
       self.client.post(reverse('approve_leave', args=[self.teacher_leave.id]))
       self.teacher_leave.refresh_from_db()
       self.assertEqual(self.teacher_leave.status, 'pending_hod')

   def test_admin_balance_updated_after_approval(self):
       self.client.login(username='hoa01', password='TestPass1234!')
       self.client.post(reverse('approve_leave', args=[self.admin_leave.id]))
       balance = LeaveBalance.objects.get(user=self.admin, leave_type='sick_leave')
       self.assertGreater(balance.days_used, 0)
       self.assertLess(balance.days_remaining, 15)

   def test_half_day_balance_deducted_05(self):
       today = date.today() + timedelta(days=10)
       half_leave = Leave.objects.create(
           user=self.admin, leave_type='sick_leave',
           reason_for_leave='Half day sick',
           start_leave=today, end_leave=today,
           status='pending_hoa', half_day='morning',
       )
       self.client.login(username='hoa01', password='TestPass1234!')
       self.client.post(reverse('approve_leave', args=[half_leave.id]))
       balance = LeaveBalance.objects.get(user=self.admin, leave_type='sick_leave')
       self.assertEqual(float(balance.days_used), 0.5)
       self.assertEqual(float(balance.days_remaining), 14.5)


class LeaveEmailTests(TestCase):
   def setUp(self):
       self.client = Client()
       self.dept = Department.objects.create(name='Mathematics')
       self.hod = make_user('hod01', 'head_of_department', dept=self.dept)
       self.dept.head = self.hod
       self.dept.save()
       self.hos = make_user('hos01', 'head_of_school')
       self.hoa = make_user('hoa01', 'head_of_admin')
       self.hr = make_user('hr01', 'hr')
       self.sched = make_user('sched01', 'scheduling_team')
       self.teacher = make_user('teacher01', 'teacher', dept=self.dept, superior=self.hod)
       self.admin = make_user('admin01', 'admin')
       LeaveBalance.objects.create(
           user=self.admin, leave_type='sick_leave',
           total_days=15, days_used=0, days_remaining=15, carried_over=0,
       )
       LeaveBalance.objects.create(
           user=self.teacher, leave_type='vacation_leave',
           total_days=30, days_used=0, days_remaining=30, carried_over=0,
       )

   def test_hod_receives_email_on_teacher_submission(self):
       """HOD receives email when teacher submits leave"""
       self.client.login(username='teacher01', password='TestPass1234!')
       self.client.post(reverse('submit_leave'), {
           'leave_type': 'vacation_leave', 'reason_for_leave': 'Vacation',
           'start_leave': date.today() + timedelta(days=10),
           'end_leave': date.today() + timedelta(days=15),
           'half_day': 'none',
       })
       emails_to = [m.to[0] for m in mail.outbox]
       self.assertIn('hod01@gesm.org', emails_to)

   def test_hoa_receives_email_on_admin_submission(self):
       """HOA receives email when admin submits leave"""
       self.client.login(username='admin01', password='TestPass1234!')
       self.client.post(reverse('submit_leave'), {
           'leave_type': 'sick_leave', 'reason_for_leave': 'Sick',
           'start_leave': date.today() + timedelta(days=5),
           'end_leave': date.today() + timedelta(days=7),
           'half_day': 'none',
       })
       emails_to = [m.to[0] for m in mail.outbox]
       self.assertIn('hoa01@gesm.org', emails_to)

   def test_hos_receives_email_after_hod_approval(self):
       """HOS receives email after HOD approves teacher leave"""
       leave = make_leave(self.teacher, status='pending_hod')
       self.client.login(username='hod01', password='TestPass1234!')
       self.client.post(reverse('approve_leave', args=[leave.id]))
       emails_to = [m.to[0] for m in mail.outbox]
       self.assertIn('hos01@gesm.org', emails_to)

   def test_teacher_receives_email_after_hos_approval(self):
       """Teacher receives email after HOS fully approves leave"""
       leave = make_leave(self.teacher, status='pending_hos')
       self.client.login(username='hos01', password='TestPass1234!')
       self.client.post(reverse('approve_leave', args=[leave.id]))
       emails_to = [m.to[0] for m in mail.outbox]
       self.assertIn('teacher01@gesm.org', emails_to)

   def test_scheduling_team_receives_email_after_hos_approval(self):
       """Scheduling team receives email after HOS approves teacher leave"""
       leave = make_leave(self.teacher, status='pending_hos')
       self.client.login(username='hos01', password='TestPass1234!')
       self.client.post(reverse('approve_leave', args=[leave.id]))
       emails_to = [m.to[0] for m in mail.outbox]
       self.assertIn('sched01@gesm.org', emails_to)

   def test_rejection_email_sent_to_teacher(self):
       """Teacher receives email when their leave is rejected"""
       leave = make_leave(self.teacher, status='pending_hod')
       self.client.login(username='hod01', password='TestPass1234!')
       self.client.post(reverse('reject_leave', args=[leave.id]), {
           'rejection_reason': 'Not available',
       })
       emails_to = [m.to[0] for m in mail.outbox]
       self.assertIn('teacher01@gesm.org', emails_to)

   def test_rejection_reason_in_email(self):
       """Rejection reason appears in the email body"""
       leave = make_leave(self.teacher, status='pending_hod')
       self.client.login(username='hod01', password='TestPass1234!')
       self.client.post(reverse('reject_leave', args=[leave.id]), {
           'rejection_reason': 'Too many absences',
       })
       bodies = [m.body for m in mail.outbox]
       self.assertTrue(any('Too many absences' in b for b in bodies))

   def test_admin_receives_email_after_hoa_approval(self):
       """Admin receives email after HOA approves their leave"""
       leave = make_leave(self.admin, status='pending_hoa', leave_type='sick_leave')
       self.client.login(username='hoa01', password='TestPass1234!')
       self.client.post(reverse('approve_leave', args=[leave.id]))
       emails_to = [m.to[0] for m in mail.outbox]
       self.assertIn('admin01@gesm.org', emails_to)


class LeaveBalanceTests(TestCase):
   def setUp(self):
       self.client = Client()
       self.hr = make_user('hr01', 'hr')
       self.admin = make_user('admin01', 'admin')
       self.teacher = make_user('teacher01', 'teacher')
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
       self.client.login(username='hr01', password='TestPass1234!')
       self.client.post(reverse('adjust_balance'), {
           'user_id': self.admin.id,
           'balance_type': 'admin',
           'leave_type': 'vacation_leave',
           'days_remaining': 20,
       })
       balance = LeaveBalance.objects.get(user=self.admin, leave_type='vacation_leave')
       self.assertEqual(float(balance.days_remaining), 20.0)

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
       self.client.login(username='hr01', password='TestPass1234!')
       self.client.post(reverse('reset_balances'))
       vacation = LeaveBalance.objects.get(user=self.admin, leave_type='vacation_leave')
       self.assertEqual(vacation.carried_over, 15)
       self.assertEqual(vacation.days_used, 0)
       sick = LeaveBalance.objects.get(user=self.admin, leave_type='sick_leave')
       self.assertEqual(sick.carried_over, 0)

   def test_reset_does_not_carry_over_for_teachers(self):
       self.client.login(username='hr01', password='TestPass1234!')
       self.client.post(reverse('reset_balances'))
       balance = LeaveBalance.objects.get(user=self.teacher, leave_type='vacation_leave')
       self.assertEqual(balance.total_days, 30)
       self.assertEqual(balance.carried_over, 0)
       self.assertEqual(balance.days_used, 0)

   def test_reset_clears_all_leaves(self):
       make_leave(self.admin, status='approved', leave_type='vacation_leave')
       self.client.login(username='hr01', password='TestPass1234!')
       self.client.post(reverse('reset_balances'))
       self.assertEqual(Leave.objects.count(), 0)

   def test_non_hr_cannot_reset_balances(self):
       self.client.login(username='teacher01', password='TestPass1234!')
       self.client.post(reverse('reset_balances'))
       balance = LeaveBalance.objects.get(user=self.admin, leave_type='vacation_leave')
       self.assertEqual(float(balance.total_days), 15.0)

   def test_delete_approved_leave_restores_teacher_balance(self):
       balance = LeaveBalance.objects.get(user=self.teacher, leave_type='vacation_leave')
       balance.days_used = 5
       balance.days_remaining = 25
       balance.save()
       leave = Leave.objects.create(
           user=self.teacher, leave_type='vacation_leave',
           reason_for_leave='Test',
           start_leave=date(2026, 5, 4),
           end_leave=date(2026, 5, 8),
           status='approved', half_day='none',
       )
       self.client.login(username='hr01', password='TestPass1234!')
       self.client.post(reverse('delete_leave', args=[leave.id]))
       balance.refresh_from_db()
       self.assertEqual(float(balance.days_used), 0.0)
       self.assertEqual(float(balance.days_remaining), 30.0)

   def test_delete_approved_leave_restores_admin_balance(self):
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

   def test_delete_pending_leave_does_not_change_balance(self):
       leave = make_leave(self.admin, status='pending_hoa', leave_type='vacation_leave')
       self.client.login(username='hr01', password='TestPass1234!')
       self.client.post(reverse('delete_leave', args=[leave.id]))
       balance = LeaveBalance.objects.get(user=self.admin, leave_type='vacation_leave')
       self.assertEqual(float(balance.days_remaining), 15.0)

   def test_non_hr_cannot_delete_leave(self):
       leave = make_leave(self.teacher, status='approved')
       self.client.login(username='teacher01', password='TestPass1234!')
       self.client.post(reverse('delete_leave', args=[leave.id]))
       self.assertTrue(Leave.objects.filter(id=leave.id).exists())