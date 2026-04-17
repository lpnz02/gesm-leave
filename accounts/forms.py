from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Department

# Formulaire d'inscription pour tous les utilisateurs
class RegisterForm(UserCreationForm):
    ALLOWED_ROLES = [
        ('teacher', 'Teacher'),
        ('employee', 'Employee'),
        ('head_of_department', 'Head of Department'),
        ('head_of_school', 'Head of School'),
        ('scheduling_team', 'Scheduling Team'),
    ]
    
    role = forms.ChoiceField(choices=ALLOWED_ROLES)
    new_department = forms.CharField(
        max_length=200, 
        required=False,
        label='Department Name (only if Head of Department)'
    )

    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'role',
            'department',
            'superior',
            'new_department',
            'password1',
            'password2'
        ]
# Formulaire de login
class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

# Formulaire département
class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'head']

