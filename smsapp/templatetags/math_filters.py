# smsapp/templatetags/math_filters.py
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key"""
    if dictionary is None:
        return None
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None

@register.filter
def mul(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """Divide the value by the argument"""
    try:
        if float(arg) != 0:
            return float(value) / float(arg)
        return 0
    except (ValueError, TypeError):
        return 0

@register.filter
def sub(value, arg):
    """Subtract the argument from the value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add(value, arg):
    """Add the argument to the value"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def percentage(value, total):
    """Calculate percentage"""
    try:
        if total:
            return (float(value) / float(total)) * 100
        return 0
    except (ValueError, TypeError):
        return 0

@register.filter
def floatformat(value, arg=-1):
    """Format a float with the specified number of decimal places"""
    try:
        if value is None:
            return ''
        value = float(value)
        if arg == -1:
            # Default: show decimals only if needed
            return ('%f' % value).rstrip('0').rstrip('.') if '.' in ('%f' % value) else ('%f' % value)
        else:
            return ('%.*f' % (int(arg), value)).rstrip('0').rstrip('.') if '.' in ('%.*f' % (int(arg), value)) else ('%.*f' % (int(arg), value))
    except (ValueError, TypeError):
        return value