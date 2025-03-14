from django import template
import calendar

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def to_int(value):
    try:
        return int(value)
    except ValueError:
        return 0
    
@register.filter
def to(value, arg):
    """Returns a range from value to arg (inclusive)"""
    try:
        return range(int(value), int(arg) + 1)
    except (ValueError, TypeError):
        return range(0)

@register.filter
def range_filter(value):
    return range(value)

@register.filter
def month_name(month_number):
    try:
        return calendar.month_name[int(month_number)]
    except (ValueError, IndexError):
        return ''


@register.filter
def split(value, delimiter=','):
    """Split a string into a list using the specified delimiter"""
    return value.split(delimiter)

@register.filter
def between(value, args):
    """
    Check if a value is between two numbers (inclusive)
    Usage: {{ value|between:start:end }}
    """
    try:
        start, end = args.split(':')
        value = int(value)
        start = int(start)
        end = int(end)
        if start <= end:
            return start <= value <= end
        else:
            return start >= value >= end
    except (ValueError, AttributeError):
        return False
    
@register.simple_tag
def continuous_number(counter):
    return counter + 1




