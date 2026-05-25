from django.db import models
from django.db import models
from django.conf import settings


# ============================================================================================
# MODELS for the DASHBOARD : New tabs (notifications sent) do migrate/makemigration if changes
#   BackToWork : sends notification to schedulingTeam when HOD/Teacher come back to work
#   PaySlipRequest : sends notification to accounting@gesm.org requesting payslip details
#   CertificateRequest : sends notification to HR to request a certificate of employment
# ============================================================================================
 
class BackToWork(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200)
    return_date = models.DateField()
    message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
 
    def __str__(self):
        return f'{self.user} returns {self.return_date}'
    
class PaySlipRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200)
    month = models.CharField(max_length=50)
    sent_at = models.DateTimeField(auto_now_add=True)
 
    def __str__(self):
        return f'{self.user} - {self.month}'
    

class CertificateRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200)
    purpose = models.TextField()
    with_salary = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)
 
    def __str__(self):
        return f'{self.user} - {self.purpose[:30]}'
