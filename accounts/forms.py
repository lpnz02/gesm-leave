from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Department


class RegisterForm(UserCreationForm):
    ALLOWED_ROLES = [
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
        ('head_of_department', 'Head of Department'),
        ('head_of_school', 'Head of School'),
        ('scheduling_team', 'Scheduling Team'),
    ]

    role = forms.ChoiceField(choices=ALLOWED_ROLES)
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="Select your department",
        label='Department'
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
            'password1',
            'password2',
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        dept = self.cleaned_data.get('department')

        if dept:
            user.department = dept

            if user.role == 'teacher':
                # assigner le HOD du département comme supérieur
                if dept.head:
                    user.superior = dept.head

            elif user.role == 'head_of_department':
                # le HOD devient automatiquement le head du département
                if commit:
                    user.save()
                    dept.head = user
                    dept.save()
                    # mettre à jour le supérieur de tous les profs déjà dans ce département
                    for teacher in User.objects.filter(department=dept, role='teacher'):
                        teacher.superior = user
                        teacher.save()
                    return user

        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'head']