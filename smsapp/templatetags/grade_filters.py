from django import template

register = template.Library()

@register.filter
def get_item(obj, key):
    if obj is None:
        return None
    return obj.get(key)