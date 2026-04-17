from django import forms
from .models import Leave

class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = Leave
        fields = [
            'leave_type',
            'reason_for_leave',
            'start_leave',
            'end_leave',
        ]
        widgets = {
            'start_leave': forms.DateInput(attrs={'type': 'date'}),
            'end_leave': forms.DateInput(attrs={'type': 'date'}),
        }

class LeaveRequestForm(forms.ModelForm):
    pdf_attachment = forms.FileField(required=False, label='Attach Leave Form (PDF)')
    
    class Meta:
        model = Leave
        fields = [
            'leave_type',
            'reason_for_leave',
            'start_leave',
            'end_leave',
        ]
        widgets = {
            'start_leave': forms.DateInput(attrs={'type': 'date'}),
            'end_leave': forms.DateInput(attrs={'type': 'date'}),
        }