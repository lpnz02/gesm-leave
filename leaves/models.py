from django.db import models
from django.conf import settings
from datetime import timedelta
import uuid

# ==============================================================================================
# Leave Models (ApprovalToken unused : leaves approved on the dashboard can be reused if needed)
# ==============================================================================================

class Leave(models.Model):
    LEAVE_CHOICES = [
        ('vacation_leave', 'Vacation Leave'),
        ('sick_leave', 'Sick Leave'),
        ('emergency_leave', 'Emergency Leave'),
        ('maternity_paternity_leave', 'Maternity / Paternity Leave'),
        ('bereavement_leave', 'Bereavement Leave'),
        ('others', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending_hod', 'Pending Head of Department Approval'),
        ('pending_hos', 'Pending Head of School Approval'),
        ('pending_hoa', 'Pending Head of Administration Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    HALF_DAY_CHOICES = [
        ('none', 'Full Day'),
        ('morning', 'Morning only'),
        ('afternoon', 'Afternoon only'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
    )
    leave_type = models.CharField(max_length=30, choices=LEAVE_CHOICES)
    reason_for_leave = models.TextField()
    start_leave = models.DateField()
    end_leave = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_hod')
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    pdf_attachment = models.FileField(upload_to='leave_pdfs/', null=True, blank=True)
    half_day = models.CharField(max_length=10, choices=HALF_DAY_CHOICES, default='none')
    is_unpaid = models.BooleanField(default=False)  

    def __str__(self):
        return f"{self.user} - {self.leave_type} - {self.status}"

    def working_days(self):
        count = 0
        current = self.start_leave
        while current <= self.end_leave:
            if current.weekday() < 5:
                count += 1
            current += timedelta(days=1)
        if self.half_day in ['morning', 'afternoon'] and self.start_leave == self.end_leave:
            return 0.5
        return count


class LeaveBalance(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    leave_type = models.CharField(max_length=30, choices=Leave.LEAVE_CHOICES)
    total_days = models.FloatField(default=0)
    days_used = models.FloatField(default=0)
    days_remaining = models.FloatField(default=0)
    carried_over = models.FloatField(default=0)

    def __str__(self):
        return f"{self.user} - {self.leave_type}"


class ApprovalToken(models.Model):
    ACTION_CHOICES = [
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ]

    leave = models.ForeignKey(Leave, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.token} - {self.action} - used: {self.is_used}"

class LeaveBalance(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    leave_type = models.CharField(max_length=30, choices=Leave.LEAVE_CHOICES)  # ← manquait !
    total_days = models.FloatField(default=0)
    days_used = models.FloatField(default=0)
    days_remaining = models.FloatField(default=0)
    carried_over = models.FloatField(default=0)
    is_unpaid = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} - {self.leave_type}"


class ApprovalToken(models.Model):
    ACTION_CHOICES = [
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ]

    leave = models.ForeignKey(Leave, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.token} - {self.action} - used: {self.is_used}"
    
