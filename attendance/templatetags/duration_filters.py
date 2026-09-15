from django import template

register = template.Library()


@register.filter
def duration_to_hours(duration):
    """Convert timedelta to hours with 2 decimal places"""
    if duration is None:
        return "0.00"
    total_seconds = duration.total_seconds()
    hours = total_seconds / 3600
    return f"{hours:.2f}"


@register.filter
def duration_to_hours_label(duration):
    """Convert timedelta to HH:MM format with 'hrs' label"""
    if duration is None or duration.total_seconds() == 0:
        return "-"
    total_seconds = duration.total_seconds()
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    return f"{hours}:{minutes:02d} hrs"
