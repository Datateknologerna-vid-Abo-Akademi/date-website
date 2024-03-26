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


@register.filter(name='in_group')
def in_group(user, group_name):
    try:
        group = Group.objects.get(name=group_name)
        return group in user.groups.all()
    except Group.DoesNotExist:
        print("ERROR, No group", group_name)  # should not happen if server setup right.
        return False

@register.filter(name='is_photographer')
def is_photographer(user):
    try:
        group = Group.objects.get(name='fotograf')
        return group in user.groups.all()
    except Group.DoesNotExist:
        print("ERROR, No group", 'fotograf')  # should not happen if server setup right.
        return False
    
@register.filter(name='is_board')
def is_board(user):
    try:
        group = Group.objects.get(name='styrelse')
        return group in user.groups.all()
    except Group.DoesNotExist:
        print("ERROR, No group", 'styrelse')  # should not happen if server setup right.
        return False
    
@register.filter(name='is_admin')
def is_admin(user):
    try:
        group = Group.objects.get(name='admin')
        return group in user.groups.all()
    except Group.DoesNotExist:
        print("ERROR, No group", 'admin')  # should not happen if server setup right.
        return False
    
@register.filter(name='is_counter')
def is_counter(user):
    try:
        group = Group.objects.get(name='rösträknare')
        return group in user.groups.all()
    except Group.DoesNotExist:
        print("ERROR, No group", 'rösträknare')  # should not happen if server setup right.
        return False