from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Department


# =================================================================================
#  DIFFEERENT FORMS : RegisterFrom, LoginForm and DepartmentForm
# =================================================================================


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
                # assigns department head as superior 
                if dept.head:
                    user.superior = dept.head

            elif user.role == 'head_of_department':
                # HOD becomes automatically head of department when account activated
                if commit:
                    user.save()
                    dept.head = user
                    dept.save()
                    # if HOD registers after teachers : he is set as superior
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