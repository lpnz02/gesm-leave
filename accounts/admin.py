from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Department

class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('HR Info', {'fields': ('role', 'department', 'superior', 'is_approved', 'is_email_verified')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('HR Info', {'fields': ('email', 'role', 'department', 'superior')}),
    )

admin.site.register(User, CustomUserAdmin)
admin.site.register(Department)
