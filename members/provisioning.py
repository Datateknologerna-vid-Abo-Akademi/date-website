from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group, Permission

from .models import NON_VOTING_MEMBER, ORDINARY_MEMBER, MembershipType, Subscription


def _update_first_or_create(model, name, defaults):
    instance = model.objects.filter(name=name).order_by('pk').first()
    if instance is None:
        return model.objects.create(name=name, **defaults)
    for field, value in defaults.items():
        setattr(instance, field, value)
    instance.save(update_fields=defaults)
    return instance


def provision_membership_access(**kwargs):
    membership_names = getattr(settings, 'MEMBERSHIP_TYPE_NAMES', None)
    role_scopes = getattr(settings, 'SF_ROLE_PERMISSION_SCOPES', None)
    if not membership_names or not role_scopes:
        return

    profiles = {
        'Ordinarie medlem': ORDINARY_MEMBER,
        'Evig SF:are': ORDINARY_MEMBER,
        'Extra medlem': NON_VOTING_MEMBER,
    }
    for name in membership_names:
        _update_first_or_create(MembershipType, name, {'permission_profile': profiles[name]})

    for name, defaults in getattr(settings, 'MEMBERSHIP_SUBSCRIPTIONS', {}).items():
        _update_first_or_create(Subscription, name, defaults)

    base_dir = Path(settings.BASE_DIR).resolve()
    app_labels = [
        app_config.label
        for app_config in apps.get_app_configs()
        if Path(app_config.path).resolve().is_relative_to(base_dir)
    ]
    app_permissions = Permission.objects.filter(content_type__app_label__in=app_labels)
    for group_name, scope in role_scopes.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        permissions = app_permissions
        if scope == 'all_except_members':
            permissions = permissions.exclude(content_type__app_label='members')
        elif scope == 'all_with_lifetime_members':
            permissions = permissions.exclude(content_type__app_label='members') | app_permissions.filter(
                content_type__app_label='members',
                content_type__model='member',
                codename__in=('view_member', 'change_member', 'delete_member'),
            )
        group.permissions.set(permissions)
