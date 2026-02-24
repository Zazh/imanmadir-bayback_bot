from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def query_string(context, **kwargs):
    """Update current query string with new params."""
    request = context['request']
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value is None or value == '':
            params.pop(key, None)
        else:
            params[key] = value
    return '?' + params.urlencode() if params else ''


@register.filter
def status_badge(status):
    """Return Bootstrap badge class for status."""
    mapping = {
        'in_progress': 'primary',
        'on_moderation': 'warning',
        'pending_review': 'info',
        'approved': 'success',
        'rejected': 'danger',
        'cancelled': 'secondary',
        'expired': 'dark',
        'pending': 'warning',
        'auto_approved': 'success',
        'processing': 'info',
        'completed': 'success',
        'failed': 'danger',
    }
    return mapping.get(status, 'secondary')


@register.filter
def dict_get(d, key):
    if isinstance(d, dict):
        return d.get(key)
    return None
