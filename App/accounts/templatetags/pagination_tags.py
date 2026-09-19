from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """
    Preserves all current GET query parameters while updating/replacing
    specified keyword arguments (such as page=...).
    Usage:
        href="?{% url_replace page=2 %}"
    """
    request = context.get('request')
    if not request or not hasattr(request, 'GET'):
        return '&'.join(f"{k}={v}" for k, v in kwargs.items())

    query = request.GET.copy()
    for key, value in kwargs.items():
        if value is None or value == '':
            query.pop(key, None)
        else:
            query[key] = str(value)
    return query.urlencode()


@register.simple_tag
def get_elided_page_range(paginator, number, on_each_side=2, on_ends=1):
    """
    Returns an elided page range (containing page numbers and '…')
    for clean, responsive pagination without overflowing.
    Usage:
        {% get_elided_page_range page_obj.paginator page_obj.number as elided_pages %}
    """
    try:
        return paginator.get_elided_page_range(
            number=int(number),
            on_each_side=int(on_each_side),
            on_ends=int(on_ends)
        )
    except Exception:
        return paginator.page_range
