from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_system', 'user_count', 'updated_at')
    list_filter = ('is_system',)
    search_fields = ('name', 'code', 'description')
    ordering = ('-is_system', 'name')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'phone', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone')
    ordering = ('username',)

    fieldsets = BaseUserAdmin.fieldsets + (
        ('RBAC Role & Profile', {
            'fields': ('role', 'phone'),
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('RBAC Role & Profile', {
            'fields': ('role', 'phone', 'first_name', 'last_name', 'email'),
        }),
    )
