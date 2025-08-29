from django import template
from django.utils.timesince import timesince, timeuntil
from django.utils import timezone

register = template.Library()

@register.filter
def timesince_single(value):
    """
    Returns only the largest unit from timesince with "ago".
    E.g., "2 days, 3 hours" becomes "2 days ago"
    """
    if not value:
        return ""
    
    time_str = timesince(value)
    largest_unit = time_str.split(',')[0].strip()
    return f"{largest_unit} ago"

@register.filter
def timeuntil_single(value):
    """
    Returns only the largest unit from timeuntil with "in".
    E.g., "2 days, 3 hours" becomes "in 2 days"
    """
    if not value:
        return ""
    
    time_str = timeuntil(value)
    largest_unit = time_str.split(',')[0].strip()
    return f"in {largest_unit}"

@register.filter
def range_filter(value):
    return range(int(value))

@register.filter 
def subtract(value, arg):
    return int(value) - int(arg)

@register.filter
def dict_get(d, key):
    """
    Usage: {{ mydict|dict_get:key }}
    Returns d[key] if key exists, else None.
    """
    try:
        return d.get(key)
    except Exception:
        return None

@register.filter(name='add_class')
def add_class(field, css):
    return field.as_widget(attrs={"class": css})

@register.inclusion_tag('components/forms/render_form_fields.html')
def render_form_fields(form):
    return {"form": form}

@register.filter
def is_past(value):
    """Returns True if the datetime value is in the past."""
    if not value:
        return False
    now = timezone.now()
    return value < now