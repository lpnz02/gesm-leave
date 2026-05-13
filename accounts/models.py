from django.contrib.auth.models import AbstractUser
from django.db import models

import uuid

class User(AbstractUser):
    ROLE_CHOICES = [
    ('teacher', 'Teacher'),
    ('admin', 'Admin'),  # ← était 'admin'
    ('head_of_department', 'Head of Department'),
    ('head_of_school', 'Head of School'),
    ('head_of_admin', 'Head of Administration'),
    ('hr', 'HR'),
    ('scheduling_team', 'Scheduling Team'),
]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members'  
    )
    email = models.EmailField(unique=True)
    superior = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinates'
    )
    is_approved = models.BooleanField(default=False)  # approuvé par HR
    is_email_verified = models.BooleanField(default=False)  # email confirmé
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.role}"
    


class Department(models.Model):
    name = models.CharField(max_length=100)
    head = models.ForeignKey(
        'User', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='department_led'
    )

    def __str__(self):
        return self.name


