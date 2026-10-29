from django import template
from django.utils.translation import get_language

register = template.Library()


@register.filter
def ordinal(value):
    """
    Convert an integer to its ordinal form in the active language.
    English: 1st, 2nd, 3rd, 4th, 11th, 21st, etc.
    French: 1er, 2e, 3e, 21e, etc.
    """
    try:
        num = int(value)
    except (ValueError, TypeError):
        return value
    if (get_language() or "").split("-")[0] == "fr":
        return f"{num}er" if num == 1 else f"{num}e"
    j = num % 10
    k = num % 100
    if j == 1 and k != 11:
        return f"{num}st"
    if j == 2 and k != 12:
        return f"{num}nd"
    if j == 3 and k != 13:
        return f"{num}rd"
    return f"{num}th"
