from django import template
from django.contrib.auth.models import Group

register = template.Library()


@register.filter(name='divide')
def divide(value, arg):
    try:
        result = int(value) / int(arg)
        return int(result)
    except (ValueError, ZeroDivisionError):
        return None


@register.filter(name="arrangePictures")
def arrangepictures(value, arg):
    try:
        column_size = divide(arg+3, 4)  # args + 4 to ensure not 5 columns are created.
        print(column_size)
        return bool(value % column_size) is False
    except (ValueError, ZeroDivisionError):
        return None


@register.filter(name='in_group')
def in_group(user, group_name):
    try:
        group = Group.objects.get(name=group_name)
        return group in user.groups.all()
    except Group.DoesNotExist:
        print("ERROR, No group", group_name)  # should not happen if server setup right.
        return False
