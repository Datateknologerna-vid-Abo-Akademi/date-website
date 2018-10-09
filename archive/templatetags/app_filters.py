from math import floor

from django import template


register = template.Library()


@register.filter(name='divide')
def divide(value, arg):
    try:
        result = int(value) / int(arg)

        return floor(result)
    except (ValueError, ZeroDivisionError):
        return None


@register.filter(name="arrangePictures")
def modulo(value, arg):

    try:
        columnsize = divide(arg+4, 4)
        print("Value: ", value, " Columnsize: ", columnsize)
        print(bool(value % columnsize))
        return bool(value % columnsize)
    except (ValueError, ZeroDivisionError):
        return None
