from django.db import models
from django.conf import settings
from datetime import timedelta

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

    user = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.SET_NULL,
    null=True,
    blank=True
    )
    leave_type = models.CharField(max_length=30, choices=LEAVE_CHOICES)
    reason_for_leave = models.TextField()
    start_leave = models.DateField()
    end_leave = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_hos')
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    pdf_attachment = models.FileField(upload_to='leave_pdfs/', null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.leave_type} - {self.status}"
    
    def working_days(self):
        count = 0
        current = self.start_leave
        while current <= self.end_leave:
            if current.weekday() < 5:  # 0=Lundi, 4=Vendredi
                count += 1
            current += timedelta(days=1)
        return count
    
    
class LeaveBalance(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    leave_type = models.CharField(max_length=30, choices=Leave.LEAVE_CHOICES)
    total_days = models.IntegerField(default=0)      # jours alloués
    days_used = models.IntegerField(default=0)       # jours utilisés
    days_remaining = models.IntegerField(default=0)  # jours restants

    def __str__(self):
        return f"{self.user} - {self.leave_type} - {self.days_remaining} days left"
    

import uuid

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

