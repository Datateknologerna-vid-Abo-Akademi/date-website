from django import template

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
    if not getattr(user, 'is_authenticated', False):
        return False
    return user.groups.filter(name=group_name).exists()


@register.filter(name='is_photographer')
def is_photographer(user):
    return in_group(user, 'fotograf')


@register.filter(name='is_board')
def is_board(user):
    return in_group(user, 'styrelse')


@register.filter(name='is_admin')
def is_admin(user):
    return in_group(user, 'admin')


@register.filter(name='is_counter')
def is_counter(user):
    return in_group(user, 'rösträknare')
