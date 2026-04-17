from django.contrib import admin
from accounts.models import User, Department
from leaves.models import Leave, LeaveBalance, ApprovalToken

admin.site.register(Leave)
admin.site.register(LeaveBalance)

admin.site.register(ApprovalToken)