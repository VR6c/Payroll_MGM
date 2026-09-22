from django import template

register = template.Library()


@register.filter(name='has_perm')
def has_perm(user, perm_name):
    """
    Checks if a user has a specific granular permission code.
    Usage: {% if request.user|has_perm:'attendance.view' %}
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'role', None) == 'super_admin':
        return True
    if hasattr(user, 'has_permission'):
        return user.has_permission(perm_name)
    return False


@register.filter(name='has_module')
def has_module(user, module_name):
    """
    Checks if a user has access to a specific module.
    Usage: {% if request.user|has_module:'attendance' %}
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'role', None) == 'super_admin':
        return True
    if hasattr(user, 'has_module_access'):
        return user.has_module_access(module_name)
    return False


@register.filter(name='has_any_perm')
def has_any_perm(user, perm_list_csv):
    """
    Checks if a user has ANY of the comma-separated permissions.
    Usage: {% if request.user|has_any_perm:'employees.view,employees.positions' %}
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'role', None) == 'super_admin':
        return True
    if not perm_list_csv:
        return False
    perms = [p.strip() for p in perm_list_csv.split(',') if p.strip()]
    if hasattr(user, 'has_permission'):
        return any(user.has_permission(p) for p in perms)
    return False
